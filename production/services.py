from fractions import Fraction
from access.services import audit

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from inventory.models import BOM, FactoryControl, Posting, StockMovement
from inventory.services import require_integer, round_paise, stock_summary
from .models import ProductionRun, RunStandard, ProductionEvent, ProductionLine, Overhead, ToleranceChange


# Service permissions also protect calls that do not come through a view.
def authorize(actor, admin_only=False):
    roles = ["admin"] if admin_only else ["admin", "production"]
    if not actor.is_active or not (actor.is_staff or actor.groups.filter(name__in=roles).exists()):
        raise PermissionDenied("Production permission required.")


# Snapshot scaled raw and packaging standards once; later BOM edits cannot change a run.
@transaction.atomic
def create_run(*, bom, batches, request_key, document_date, actor):
    authorize(actor)
    require_integer(batches, 1)
    if not request_key:
        raise ValidationError("Request key is required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    existing = ProductionRun.objects.filter(request_key=request_key).first()
    if existing:
        if (existing.bom_id, existing.batches, existing.document_date, existing.actor_id) != (bom.pk, batches, document_date, actor.pk):
            raise ValidationError("Run request key reused with different content.")
        return existing
    bom = BOM.objects.select_related("sku__item", "recipe").get(pk=bom.pk)
    if bom.sku.item.category != "finished" or bom.sku.item.base_unit != "piece":
        raise ValidationError("Output must be a finished-goods piece item.")
    require_integer(bom.expected_packets, 1)
    run = ProductionRun.objects.create(bom=bom, batches=batches, request_key=request_key,
        document_date=document_date, actor=actor, bom_version=bom.version,
        recipe_version=bom.recipe.version, expected_packets=bom.expected_packets * batches,
        output_item=bom.sku.item)
    if not bom.recipe.lines.exists():
        raise ValidationError("Recipe needs at least one raw ingredient.")
    for stage, lines in (("raw", bom.recipe.lines.all()), ("packaging", bom.lines.all())):
        for line in lines.select_related("item"):
            require_integer(line.quantity, 1)
            if line.item.category != stage:
                raise ValidationError("Recipe must contain raw inputs; BOM lines must contain packaging.")
            RunStandard.objects.create(run=run, item=line.item, stage=stage, quantity=line.quantity * batches)
    audit(actor, "run.create", run, {}, {"batches": batches, "expected_packets": run.expected_packets})
    return run


# Round only the total issue value; the last issue consumes every remaining paise.
def issue_value(quantity, on_hand, value_paise):
    require_integer(quantity)
    require_integer(on_hand)
    if quantity > on_hand:
        raise ValidationError("Insufficient stock.")
    if quantity == 0:
        return 0
    if value_paise is None:
        raise ValidationError("Cannot cost an input with unknown stock valuation.")
    require_integer(value_paise)
    if quantity == on_hand:
        return value_paise
    return round_paise(Fraction(value_paise * quantity, on_hand))


# Store the actual source line even for zero usage, but never post a zero movement.
def append_line(event, posting, item, quantity, value):
    line = ProductionLine.objects.create(event=event, item=item, quantity=quantity, value_paise=value)
    if quantity:
        StockMovement.objects.create(posting=posting, production_line=line, item=item,
                                     quantity=quantity, value_paise=value)
    return line


# Both transitions use one transaction and lock; completion never repeats the raw issue.
@transaction.atomic
def post_event(*, run, kind, actual, request_key, actor, good_packets=None, damaged=None):
    authorize(actor)
    if kind not in ("issue", "complete") or not request_key or not isinstance(actual, dict):
        raise ValidationError("Valid event, request key and actual input map required.")
    for quantity in actual.values():
        require_integer(quantity)
    damaged = {} if damaged is None else damaged
    if not isinstance(damaged, dict):
        raise ValidationError("Damaged packaging must be a quantity map.")
    if kind == "complete":
        require_integer(good_packets)
        for code, quantity in damaged.items():
            require_integer(quantity)
            if code not in actual or quantity > actual[code]:
                raise ValidationError("Damage must be included in the actual packaging issue.")
    elif good_packets is not None or damaged:
        raise ValidationError("Output and packaging damage belong to completion only.")
    payload = {"actual": actual, "good_packets": good_packets, "damaged": damaged}
    control = FactoryControl.objects.select_for_update().get(pk=1)
    run = ProductionRun.objects.get(pk=run.pk)
    previous = ProductionEvent.objects.filter(run=run, kind=kind).first()
    if previous:
        if previous.request_key != request_key or previous.payload != payload or previous.actor_id != actor.pk:
            raise ValidationError("Event already posted with different content or key.")
        return Posting.objects.get(production=previous)
    if ProductionEvent.objects.filter(request_key=request_key).exists():
        raise ValidationError("Event request key already used.")
    required_state = "draft" if kind == "issue" else "issued"
    if run.state != required_state:
        raise ValidationError("Invalid production transition.")
    stage = "raw" if kind == "issue" else "packaging"
    standards = list(run.standards.filter(stage=stage).select_related("item"))
    if set(actual) != {standard.item.code for standard in standards}:
        raise ValidationError("Supply actual quantities for exactly the snapshotted inputs.")
    balances = stock_summary()
    issues = []
    for standard in standards:
        balance = balances[standard.item.code]
        quantity = actual[standard.item.code]
        value = issue_value(quantity, balance["quantity"], balance["value_paise"])
        issues.append((standard.item, quantity, value))
    event = ProductionEvent.objects.create(run=run, kind=kind, request_key=request_key,
        document_date=run.document_date, actor=actor, payload=payload)
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting = Posting.objects.create(sequence=control.last_sequence, production=event)
    for item, quantity, value in issues:
        append_line(event, posting, item, -quantity, -value)
    if kind == "complete":
        raw_value = -sum(run.events.get(kind="issue").lines.values_list("value_paise", flat=True))
        materials_value = raw_value + sum(value for _, _, value in issues)
        if good_packets:
            append_line(event, posting, run.output_item, good_packets, materials_value)
        run.good_packets = good_packets
    audit(actor, "run." + kind, run, {"state": run.state}, payload)
    run.state = "issued" if kind == "issue" else "completed"
    run.save(update_fields=["state", "good_packets"])
    return posting


# Public entry points keep issue and completion inputs explicit for callers.
def issue_run(*, run, actual, request_key, actor):
    return post_event(run=run, kind="issue", actual=actual, request_key=request_key, actor=actor)


def complete_run(*, run, actual, good_packets, damaged, request_key, actor):
    return post_event(run=run, kind="complete", actual=actual, good_packets=good_packets,
                      damaged=damaged, request_key=request_key, actor=actor)


# Overhead is a new cost document, never an edit to an earlier FG stock movement.
@transaction.atomic
def add_overhead(*, run, label, amount_paise, request_key, document_date, actor):
    authorize(actor, admin_only=True)
    require_integer(amount_paise, 1)
    if not label.strip() or not request_key:
        raise ValidationError("Label and request key are required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    run = ProductionRun.objects.get(pk=run.pk)
    if run.state != "completed":
        raise ValidationError("Complete the run before adding overhead.")
    values = dict(run=run, label=label, amount_paise=amount_paise, document_date=document_date, actor=actor)
    existing = Overhead.objects.filter(request_key=request_key).first()
    if existing:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise ValidationError("Overhead request key reused with different content.")
        return existing
    return Overhead.objects.create(request_key=request_key, **values)


# Tolerance changes are audited settings, not changes to production quantities.
@transaction.atomic
def set_tolerance(*, basis_points, actor):
    authorize(actor, admin_only=True)
    require_integer(basis_points)
    if basis_points > 10000:
        raise ValidationError("Tolerance must be between 0 and 100 percent.")
    control = FactoryControl.objects.select_for_update().get(pk=1)
    if control.tolerance_bps != basis_points:
        ToleranceChange.objects.create(actor=actor, before_bps=control.tolerance_bps, after_bps=basis_points)
        control.tolerance_bps = basis_points
        control.save(update_fields=["tolerance_bps"])
    return control.tolerance_bps


# Fractions preserve the exact equality boundary: 3 percent is not beyond 3 percent.
def variance(actual, standard, tolerance_bps):
    require_integer(actual)
    require_integer(standard)
    require_integer(tolerance_bps)
    if standard == 0:
        return {"ratio": None, "flagged": False}
    ratio = Fraction(actual - standard, standard)
    return {"ratio": ratio, "flagged": abs(ratio) * 10000 > tolerance_bps}


# Report from source events using today's tolerance; FG value remains materials-only.
@transaction.atomic
def run_report(run):
    control = FactoryControl.objects.select_for_update().get(pk=1)
    run = ProductionRun.objects.get(pk=run.pk)
    events = {event.kind: event for event in run.events.all()}
    actual = {}
    materials = 0
    for event in events.values():
        for line in event.lines.exclude(item=run.output_item).select_related("item"):
            actual[line.item.code] = -line.quantity
            materials -= line.value_paise
    consumption = {}
    for standard in run.standards.select_related("item"):
        quantity = actual.get(standard.item.code)
        consumption[standard.item.code] = {"planned": standard.quantity, "actual": quantity,
            **(variance(quantity, standard.quantity, control.tolerance_bps) if quantity is not None else {"ratio": None, "flagged": False})}
    overhead = sum(run.overheads.values_list("amount_paise", flat=True))
    if run.state == "reversed":
        materials = overhead = 0
    total = materials + overhead
    unit_cost = Fraction(total, run.good_packets) if run.good_packets else None
    return {"state": run.state, "consumption": consumption, "tolerance_bps": control.tolerance_bps,
        "expected_packets": run.expected_packets, "good_packets": run.good_packets,
        "yield": variance(run.good_packets, run.expected_packets, control.tolerance_bps) if run.good_packets is not None else {"ratio": None, "flagged": False},
        "unclassified_shortfall": max(0, run.expected_packets - run.good_packets) if run.good_packets is not None else None,
        "damaged_packaging": events["complete"].payload["damaged"] if "complete" in events else {},
        "materials_paise": materials, "overhead_paise": overhead, "total_paise": total,
        "margin_paise": run.bom.sku.price_paise - unit_cost if unit_cost is not None else None,
        "cost_per_packet_paise": unit_cost, "display_cost_paise": round_paise(unit_cost) if unit_cost is not None else None,
        "fg_valuation_basis": "materials-only"}


# Draft batch edits rescale snapshotted standards; posted inputs remain frozen.
@transaction.atomic
def edit_run_draft(run, batches, actor):
    authorize(actor)
    require_integer(batches, 1)
    FactoryControl.objects.select_for_update().get(pk=1)
    run = ProductionRun.objects.get(pk=run.pk)
    if run.state != "draft":
        raise ValidationError("Only draft runs can be edited.")
    before = {"batches": run.batches, "expected_packets": run.expected_packets}
    for standard in run.standards.all():
        standard.quantity = standard.quantity // run.batches * batches
        standard.save(update_fields=["quantity"])
    run.expected_packets = run.expected_packets // run.batches * batches
    run.batches = batches
    run.save(update_fields=["expected_packets", "batches"])
    audit(actor, "run.edit", run, before, {"batches": batches, "expected_packets": run.expected_packets})
    return run


# Pending demand is aggregated once per SKU; suggestions never reserve or post stock.
@transaction.atomic
def suggest_production(*, sku, actor, uncovered=None):
    authorize(actor)
    from sales.models import OrderLine
    from sales.services import available_stock
    FactoryControl.objects.select_for_update().get(pk=1)
    balances=available_stock()
    if uncovered is None:
        demand=sum(OrderLine.objects.filter(sku=sku,order__status="submitted").values_list("quantity",flat=True))
        uncovered=max(0,demand-balances[sku.item.code]["available"])
    require_integer(uncovered)
    bom=BOM.objects.filter(sku=sku).order_by("-version").first()
    if bom is None: raise ValidationError("No BOM exists for this product.")
    batches=(uncovered+bom.expected_packets-1)//bom.expected_packets
    rows=[]
    for line in [*bom.recipe.lines.select_related("item"),*bom.lines.select_related("item")]:
        stock=balances[line.item.code]["quantity"]
        rows.append({"item":line.item.code,"unit":line.item.base_unit,"stock":stock,"required":line.quantity*batches,
                     "shortage":max(0,line.quantity*batches-stock),"supported_batches":Fraction(stock,line.quantity),"feasible_batches":stock//line.quantity})
    feasible=min((row["feasible_batches"] for row in rows),default=0)
    return {"uncovered":uncovered,"required_batches":batches,"feasible_batches":feasible,"blocked":batches>feasible,"inputs":rows}
