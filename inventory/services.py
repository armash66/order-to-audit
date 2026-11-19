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
def post_receipt(*, kind, request_key, document_date, lines, actor, supplier=None):
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
    control = FactoryControl.objects.select_for_update().get(pk=1)
    header, line_model = (OpeningStock, OpeningLine) if kind == "opening" else (PurchaseReceipt, PurchaseLine)
    existing = header.objects.filter(request_key=request_key).first()
    if existing is not None:  # Duplicate-post guard: return the original event, never append again.
        previous = list(existing.lines.order_by("item_id").values_list("item_id", "quantity", "value_paise"))
        if previous != normalized or existing.document_date != document_date or existing.actor_id != actor.pk or (kind == "purchase" and existing.supplier_id != supplier.pk):
            raise ValidationError("Request key already used with different content.")
        return Posting.objects.get(**{kind: existing})
    if kind == "opening" and Posting.objects.exists():
        raise ValidationError("Opening stock must precede operational postings.")
    fields = {"request_key": request_key, "document_date": document_date, "actor": actor}
    if supplier is not None:
        fields["supplier"] = supplier
    source = header.objects.create(**fields)
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting = Posting.objects.create(sequence=control.last_sequence, **{kind: source})
    for item_id, quantity, value in normalized:
        line = line_model.objects.create(document=source, item_id=item_id, quantity=quantity, value_paise=value)
        StockMovement.objects.create(posting=posting, item_id=item_id, quantity=quantity,
                                     value_paise=value, **{kind + "_line": line})
    return posting


# Compare independent source expectations with individual movements and reported totals.
@transaction.atomic
def reconcile_stock():
    FactoryControl.objects.select_for_update().get(pk=1)
    from production.models import ProductionEvent

    expected = {item.code: {"quantity": 0, "value_paise": 0} for item in Item.objects.all()}
    for item in Item.objects.filter(category="finished"):
        expected[item.code]["valuation_basis"] = "materials-only"
    errors = []
    for kind, header in (("opening", OpeningStock), ("purchase", PurchaseReceipt), ("production", ProductionEvent)):
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
    return reported
