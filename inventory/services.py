from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Sum

from .models import (FactoryControl, Item, OpeningStock, OpeningLine, PurchaseReceipt,
                     PurchaseLine, Posting, StockMovement, UnitConversion)


# Require integer inputs explicitly: bool and float are not business quantities.
def require_integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValidationError("Expected an integer at or above the allowed minimum.")
    return value


# Fractional base units are rejected instead of silently rounded.
def to_base_units(item, unit, quantity):
    if not isinstance(quantity, (int, Decimal, Fraction)) or isinstance(quantity, bool):
        raise ValidationError("Use integer, Decimal or Fraction quantities, never floats.")
    if quantity <= 0:
        raise ValidationError("Quantity must be positive.")
    if unit == item.base_unit:
        result = Fraction(quantity)
    else:
        conversion = UnitConversion.objects.get(item=item, unit=unit)
        result = Fraction(quantity) * Fraction(conversion.numerator, conversion.denominator)
    if result.denominator != 1:
        raise ValidationError("Quantity does not resolve to a whole base unit.")
    return result.numerator


# Round the exact rational at the final paise boundary, including negative halves.
def round_paise(value):
    if not isinstance(value, (int, Decimal, Fraction)) or isinstance(value, bool):
        raise ValidationError("Use exact arithmetic, never floats.")
    value = Fraction(value)
    whole, remainder = divmod(abs(value.numerator), value.denominator)
    with localcontext() as context:
        context.prec = max(28, len(str(whole)) + 3)
        half = Decimal("0.5") if remainder * 2 >= value.denominator else Decimal(0)
        rounded = int((Decimal(whole) + half).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return -rounded if value < 0 else rounded


# Reports aggregate the ledger; unknown valuation must not become zero through SQL SUM.
def stock_summary():
    totals = {r["item_id"]: r for r in StockMovement.objects.values("item_id").annotate(
        quantity=Sum("quantity"), value=Sum("value_paise"), rows=Count("id"), known=Count("value_paise"))}
    result = {}
    for item in Item.objects.all():
        row = totals.get(item.id)
        result[item.code] = {"quantity": row["quantity"] if row else 0,
                             "value_paise": (row["value"] if row["rows"] == row["known"] else None) if row else 0}
        if item.category == "finished":
            result[item.code]["valuation_basis"] = "materials-only"
    return result


# Return exact paise per base unit; missing valuation propagates as unknown.
def weighted_average(item):
    balance = stock_summary()[item.code]
    if not balance["quantity"] or balance["value_paise"] is None:
        return None
    return Fraction(balance["value_paise"], balance["quantity"])


# Create and post one immutable receipt under the single-factory transaction lock.
@transaction.atomic
def post_receipt(*, kind, request_key, document_date, lines, actor, supplier=None, lot_details=None):
    if not actor.is_active or not (actor.is_staff or actor.groups.filter(name__in=["admin", "production"]).exists()):
        raise PermissionDenied("Stock posting requires admin or production access.")
    if kind not in ("opening", "purchase") or not request_key or not lines:
        raise ValidationError("Receipt kind, request key and lines are required.")
    if (kind == "purchase") != (supplier is not None):
        raise ValidationError("Only purchases require a supplier.")
    normalized = []
    for item, quantity, value in lines:
        require_integer(quantity, 1)
        if value is None:
            if kind != "opening" or item.category != "finished":
                raise ValidationError("Only opening finished goods may have unknown cost.")
        else:
            require_integer(value)
        normalized.append((item.pk, quantity, value))
    if len({r[0] for r in normalized}) != len(normalized):
        raise ValidationError("Combine duplicate items into one document line.")
    normalized.sort(key=lambda r: r[0])
    lot_details = lot_details or {}
    if set(lot_details)-{item.code for item,_,_ in lines}:
        raise ValidationError("Batch metadata must refer to receipt items.")
    control = FactoryControl.objects.select_for_update().get(pk=1)
    header, line_model = (OpeningStock, OpeningLine) if kind == "opening" else (PurchaseReceipt, PurchaseLine)
    existing = header.objects.filter(request_key=request_key).first()
    if existing is not None:  # Duplicate-post guard: return the original event, never append again.
        previous = list(existing.lines.order_by("item_id").values_list("item_id", "quantity", "value_paise"))
        if previous != normalized or existing.document_date != document_date or existing.actor_id != actor.pk or (kind == "purchase" and existing.supplier_id != supplier.pk):
            raise ValidationError("Request key already used with different content.")
        if existing.lot_details != lot_details:
            raise ValidationError("Receipt retry changed batch or expiry details.")
        return Posting.objects.get(**{kind: existing})
    if kind == "opening" and Posting.objects.exists():
        raise ValidationError("Opening stock must precede operational postings.")
    fields = {"request_key": request_key, "document_date": document_date, "actor": actor, "lot_details": lot_details}
    if supplier is not None:
        fields["supplier"] = supplier
    source = header.objects.create(**fields)
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting = Posting.objects.create(sequence=control.last_sequence, **{kind: source})
    for item_id, quantity, value in normalized:
        line = line_model.objects.create(document=source, item_id=item_id, quantity=quantity, value_paise=value)
        item=Item.objects.get(pk=item_id)
        record_movement(posting=posting, item=item, quantity=quantity,
                        value_paise=value, incoming_lot=lot_details.get(item.code), **{kind + "_line": line})
    return posting


# Compare independent source expectations with individual movements and reported totals.
@transaction.atomic
def reconcile_stock():
    FactoryControl.objects.select_for_update().get(pk=1)
    from production.models import ProductionEvent
    from sales.models import Dispatch

    expected = {item.code: {"quantity": 0, "value_paise": 0} for item in Item.objects.all()}
    for item in Item.objects.filter(category="finished"):
        expected[item.code]["valuation_basis"] = "materials-only"
    errors = []
    for kind, header in (("opening", OpeningStock), ("purchase", PurchaseReceipt), ("production", ProductionEvent), ("dispatch", Dispatch), ("adjustment", Adjustment)):
        for source in header.objects.all():
            posting = Posting.objects.filter(**{kind: source}).first()
            if posting is None:
                errors.append(f"Unposted source: {kind} {source.pk}")
                continue
            for line in source.lines.select_related("item"):
                movement = StockMovement.objects.filter(**{kind + "_line": line}).first()
                if line.quantity == 0 and line.value_paise == 0 and movement is None:
                    pass
                elif movement is None or (movement.posting_id, movement.item_id, movement.quantity, movement.value_paise) != (posting.pk, line.item_id, line.quantity, line.value_paise):
                    errors.append(f"Source/movement mismatch: {kind} line {line.pk}")
                total = expected[line.item.code]
                total["quantity"] += line.quantity
                total["value_paise"] = None if total["value_paise"] is None or line.value_paise is None else total["value_paise"] + line.value_paise
    reported = stock_summary()
    if expected != reported:
        errors.append("Source totals differ from reported ledger balances.")
    if errors:
        raise ValidationError(errors)
    reconcile_lots()
    return reported


from django.core.exceptions import ValidationError
from django.db import transaction
from access.services import require_role, audit
from .models import Adjustment, AdjustmentLine, FactoryControl, Posting, StockMovement, Item


# Internal writer used only after locked validation; inversion preserves original paise.
def append_adjustment(control, source, lines):
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting=Posting.objects.create(sequence=control.last_sequence,adjustment=source)
    for item,quantity,value in lines:
        line=AdjustmentLine.objects.create(document=source,item=item,quantity=quantity,value_paise=value)
        allocations=None
        if source.reversed_run_id:
            from .models import LotAllocation
            original=LotAllocation.objects.filter(movement__posting__production__run_id=source.reversed_run_id,movement__item=item)
            combined={}
            for allocation in original:
                combined[allocation.lot_id]=combined.get(allocation.lot_id,0)-allocation.quantity
            allocations=combined
        incoming=None
        if "invoice" in source.payload and "quantities" in source.payload and quantity>0:
            from .models import LotAllocation
            dates=LotAllocation.objects.filter(movement__dispatch_line__document__invoice_id=source.payload["invoice"],lot__item=item,lot__expiry_date__isnull=False).values_list("lot__expiry_date",flat=True)
            expiry=min(dates,default=None)
            incoming={"code":f"RETURN-{source.pk}","expiry":expiry.isoformat() if expiry else None}
        record_movement(posting=posting,adjustment_line=line,item=item,quantity=quantity,value_paise=value,
                        explicit_allocations=allocations,allow_expired=True,incoming_lot=incoming)
    audit(source.actor,"stock.adjust",source,{},source.payload)
    return posting


# Quantities are derived from allocation entries, ordered by expiry with unknown dates last.
def lot_balances(item=None):
    from datetime import date
    from django.db.models import Sum
    from .models import StockLot
    lots=StockLot.objects.select_related("item").annotate(on_hand=Sum("allocations__quantity"))
    if item is not None: lots=lots.filter(item=item)
    return sorted(lots,key=lambda lot:(lot.expiry_date is None,lot.expiry_date or date.max,lot.pk))


# Called inside the factory transaction: one movement plus all FEFO allocations commit together.
def record_movement(*, incoming_lot=None, explicit_allocations=None, allow_expired=False, **fields):
    from datetime import date
    from django.utils import timezone
    from .models import StockLot, LotAllocation
    item=fields.get("item") or Item.objects.get(pk=fields["item_id"])
    quantity=fields["quantity"]
    movement=StockMovement.objects.create(**fields)
    selected={}
    if explicit_allocations is not None:
        if sum(explicit_allocations.values()) != quantity:
            raise ValidationError("Correction allocations do not match movement quantity.")
        selected=explicit_allocations
    elif quantity>0:
        metadata=incoming_lot or {}
        code=metadata.get("code") or f"POST-{movement.posting.sequence}"
        expiry=metadata.get("expiry")
        try: expiry=date.fromisoformat(expiry) if expiry else None
        except (TypeError,ValueError) as error: raise ValidationError("Invalid batch expiry date.") from error
        if not isinstance(code,str) or len(code)>100: raise ValidationError("Batch code must be at most 100 characters.")
        lot,created=StockLot.objects.get_or_create(item=item,code=code,defaults={"expiry_date":expiry})
        if not created and lot.expiry_date!=expiry: raise ValidationError("An existing batch's expiry cannot be changed.")
        selected={lot.pk:quantity}
    else:
        remaining=-quantity
        for lot in lot_balances(item):
            if not allow_expired and lot.expiry_date and lot.expiry_date<timezone.localdate(): continue
            take=min(remaining,lot.on_hand or 0)
            if take>0: selected[lot.pk]=-take; remaining-=take
            if remaining==0: break
        if remaining: raise ValidationError("Insufficient non-expired batch stock.")
    current={lot.pk:lot.on_hand or 0 for lot in lot_balances(item)}
    for lot_id,signed in selected.items():
        if lot_id not in current or (signed<0 and current[lot_id]+signed<0):
            raise ValidationError("Batch correction would make stock negative or use another item.")
        if signed: LotAllocation.objects.create(movement=movement,lot_id=lot_id,quantity=signed)
    return movement


# Allocation totals must equal each immutable item movement, with no negative batch balance.
def reconcile_lots():
    from django.db.models import Sum
    for movement in StockMovement.objects.annotate(allocated=Sum("allocations__quantity")):
        if movement.allocated!=movement.quantity or movement.allocations.exclude(lot__item_id=movement.item_id).exists():
            raise ValidationError("Batch allocations disagree with the stock ledger.")
    if any((lot.on_hand or 0)<0 for lot in lot_balances()):
        raise ValidationError("Negative batch stock.")


@transaction.atomic
def set_reorder_level(*, item, minimum_quantity, actor):
    from .models import ReorderLevel
    require_role(actor,["admin"])
    require_integer(minimum_quantity)
    if item.category!="raw": raise ValidationError("Reorder alerts are for raw materials.")
    FactoryControl.objects.select_for_update().get(pk=1)
    old=ReorderLevel.objects.filter(item=item).first()
    before={"minimum":old.minimum_quantity} if old else {}
    level,_=ReorderLevel.objects.update_or_create(item=item,defaults={"minimum_quantity":minimum_quantity})
    audit(actor,"reorder.edit",level,before,{"minimum":minimum_quantity})
    return level


def reorder_alerts():
    from .models import ReorderLevel
    from sales.services import available_stock
    balances=available_stock()
    return [{"item":level.item,"available":balances[level.item.code]["available"],"minimum":level.minimum_quantity}
            for level in ReorderLevel.objects.select_related("item") if balances[level.item.code]["available"]<=level.minimum_quantity]


# Negative adjustments consume weighted-average value; positive ones need explicit cost.
@transaction.atomic
def adjust_stock(*, item, quantity, value_paise, reason, request_key, document_date, actor):
    from production.services import issue_value
    from sales.services import available_stock
    require_role(actor,["admin"])
    if type(quantity) is not int or quantity == 0 or not reason.strip() or not request_key:
        raise ValidationError("Nonzero integer quantity, reason and request key required.")
    payload={"item":item.pk,"quantity":quantity,"value_paise":value_paise,"reason":reason,"date":str(document_date)}
    control=FactoryControl.objects.select_for_update().get(pk=1)
    old=Adjustment.objects.filter(request_key=request_key).first()
    if old:
        if old.payload!=payload or old.actor_id!=actor.pk: raise ValidationError("Conflicting adjustment retry.")
        return Posting.objects.get(adjustment=old)
    balance=available_stock()[item.code]
    if quantity<0:
        if value_paise is not None: raise ValidationError("Negative adjustments calculate their own value.")
        if -quantity>balance["quantity"]-balance["reserved"]: raise ValidationError("Adjustment would consume reserved or unavailable stock.")
        value=None if balance["value_paise"] is None else -issue_value(-quantity,balance["quantity"],balance["value_paise"])
    else:
        require_integer(value_paise)
        value=value_paise
    source=Adjustment.objects.create(reason=reason,payload=payload,request_key=request_key,document_date=document_date,actor=actor)
    return append_adjustment(control,source,[(item,quantity,value)])


# Reverse only untouched recorded runs, never dependent dispatches or physical production.
@transaction.atomic
def reverse_run(*, run, reason, request_key, document_date, actor):
    from production.models import ProductionRun
    from sales.services import available_stock
    require_role(actor,["admin"])
    if not reason.strip() or not request_key: raise ValidationError("Correction reason and request key required.")
    control=FactoryControl.objects.select_for_update().get(pk=1)
    run=ProductionRun.objects.get(pk=run.pk)
    payload={"run":run.pk,"reason":reason,"date":str(document_date)}
    old=Adjustment.objects.filter(request_key=request_key).first()
    if old:
        if old.payload!=payload or old.actor_id!=actor.pk: raise ValidationError("Conflicting reversal retry.")
        return Posting.objects.get(adjustment=old)
    if run.state not in ("issued","completed"): raise ValidationError("Only issued or completed runs can be reversed.")
    movements=list(StockMovement.objects.filter(posting__production__run=run).select_related("item","posting"))
    if not movements: raise ValidationError("Run has no stock postings.")
    last=max(m.posting.sequence for m in movements)
    items={m.item_id for m in movements}
    if StockMovement.objects.filter(item_id__in=items,posting__sequence__gt=last).exists():
        raise ValidationError("A later stock event touches this run; reversal is blocked.")
    # Also exclude unrelated events between issue and completion affecting any input.
    first=min(m.posting.sequence for m in movements)
    if StockMovement.objects.filter(item_id__in=items,posting__sequence__gt=first).exclude(posting__production__run=run).exists():
        raise ValidationError("An intervening stock event depends on this run.")
    balances=available_stock()
    lines=[]
    for movement in movements:
        if movement.quantity>0 and balances[movement.item.code]["available"]<movement.quantity:
            raise ValidationError("Reversal would consume reserved or unavailable finished goods.")
        lines.append((movement.item,-movement.quantity,-movement.value_paise))
    source=Adjustment.objects.create(reversed_run=run,reason=reason,payload=payload,request_key=request_key,document_date=document_date,actor=actor)
    posting=append_adjustment(control,source,lines)
    audit(actor,"run.reverse",run,{"state":run.state},{"state":"reversed","reason":reason})
    run.state="reversed"
    run.save(update_fields=["state"])
    return posting
