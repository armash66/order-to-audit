from fractions import Fraction
from access.services import audit
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from inventory.models import Customer, SKU, FactoryControl, Posting, StockMovement
from inventory.services import stock_summary, require_integer, round_paise
from production.services import issue_value
from .models import Order, OrderLine, Invoice, InvoiceLine, InvoiceSequence, Dispatch, DispatchLine, Payment, CreditNote


def authorize(actor, roles):
    if not actor.is_active or not (actor.is_staff or actor.groups.filter(name__in=roles).exists()):
        raise PermissionDenied("This action is not permitted for your role.")


def order_for_actor(order, actor):
    authorize(actor, ["salesman", "admin", "accountant", "owner"])
    if not actor.is_staff and actor.groups.filter(name="salesman").exists() and order.actor_id != actor.pk:
        raise PermissionDenied("You can only access your own orders.")
    return order


# Approved/invoiced order lines are reservations; no second editable stock counter exists.
def available_stock():
    balances = stock_summary()
    for balance in balances.values():
        balance["reserved"] = 0
    for line in OrderLine.objects.filter(order__status__in=["approved", "invoiced"]).select_related("sku__item"):
        balances[line.sku.item.code]["reserved"] += line.quantity
    for balance in balances.values():
        balance["available"] = balance["quantity"] - balance["reserved"]
    return balances


def stock_check(order, actor):
    order_for_actor(order, actor)
    balances = available_stock()
    return [{"item": line.sku.item.code, "requested": line.quantity,
             "available": balances[line.sku.item.code]["available"],
             "shortage": max(0, line.quantity - balances[line.sku.item.code]["available"])}
            for line in order.lines.select_related("sku__item")]


@transaction.atomic
def submit_order(*, customer, quantities, request_key, document_date, actor):
    authorize(actor, ["salesman", "admin"])
    if not request_key or not quantities:
        raise ValidationError("Customer, request key and order lines are required.")
    for quantity in quantities.values():
        require_integer(quantity, 1)
    payload = {str(k): v for k, v in quantities.items()}
    FactoryControl.objects.select_for_update().get(pk=1)
    old = Order.objects.filter(request_key=request_key).first()
    if old:
        if (old.customer_id, old.actor_id, old.document_date, old.submitted_payload) != (customer.pk, actor.pk, document_date, payload):
            raise ValidationError("Order request key conflicts with an existing order.")
        return old
    order = Order.objects.create(customer=customer, actor=actor, document_date=document_date,
                                 request_key=request_key, submitted_payload=payload)
    for sku_id, quantity in payload.items():
        try:
            sku = SKU.objects.select_related("item").get(pk=sku_id)
        except SKU.DoesNotExist as error:
            raise ValidationError("Unknown product in order.") from error
        if sku.item.category != "finished":
            raise ValidationError("Only finished goods can be ordered.")
        OrderLine.objects.create(order=order, sku=sku, quantity=quantity, price_paise=sku.price_paise)
    audit(actor, "order.submit", order, {}, payload)
    return order


@transaction.atomic
def approve_order(order, actor):
    authorize(actor, ["admin"])
    FactoryControl.objects.select_for_update().get(pk=1)
    order = Order.objects.get(pk=order.pk)
    if order.status == "approved":
        return order
    if order.status != "submitted":
        raise ValidationError("Only submitted orders can be approved.")
    if any(row["shortage"] for row in stock_check(order, actor)):
        raise ValidationError("Insufficient available stock; order remains submitted.")
    audit(actor, "order.approve", order, {"status": order.status}, {"status": "approved"})
    order.status = "approved"
    order.save(update_fields=["status"])
    return order


@transaction.atomic
def reject_order(order, reason, actor):
    authorize(actor, ["admin"])
    if not reason.strip():
        raise ValidationError("A rejection reason is required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    order = Order.objects.get(pk=order.pk)
    if order.status == "rejected" and order.rejection_reason == reason:
        return order
    if order.status not in ("submitted", "approved") or Invoice.objects.filter(order=order).exists():
        raise ValidationError("This order cannot be rejected directly.")
    audit(actor, "order.reject", order, {"status": order.status}, {"status": "rejected", "reason": reason})
    order.status, order.rejection_reason = "rejected", reason
    order.save(update_fields=["status", "rejection_reason"])
    return order


# Each line tax component rounds half-up independently, then invoice totals sum those components.
def line_tax(taxable_paise, interstate):
    require_integer(taxable_paise)
    if interstate:
        return (0, 0, round_paise(Fraction(taxable_paise * 5, 100)))
    half = round_paise(Fraction(taxable_paise * 25, 1000))
    return (half, half, 0)


@transaction.atomic
def invoice_order(order, actor, document_date, draft=False):
    authorize(actor, ["admin"])
    FactoryControl.objects.select_for_update().get(pk=1)
    order = Order.objects.select_related("customer").get(pk=order.pk)
    old = Invoice.objects.filter(order=order).first()
    if old:
        if old.document_date != document_date:
            raise ValidationError("Invoice already exists with a different date.")
        if old.status == "draft" and not draft:
            old.number = next_invoice_number(document_date)
            old.status = "posted"
            old.save(update_fields=["number", "status"])
            order.status = "invoiced"
            order.save(update_fields=["status"])
            audit(actor, "invoice.post", old, {"status": "draft"}, {"status": "posted", "number": old.number})
        return old
    if order.status != "approved":
        raise ValidationError("Approve the order first.")
    state = order.customer.gstin[:2] if order.customer.gstin else order.customer.state_code
    if len(state) != 2 or not state.isdigit():
        raise ValidationError("Customer supply state is required.")
    rows = []
    for line in order.lines.select_related("sku__item"):
        taxable = line.quantity * line.price_paise
        cgst, sgst, igst = line_tax(taxable, state != "33")
        rows.append(dict(sku=line.sku, description=line.sku.item.name, hsn=line.sku.hsn,
                         quantity=line.quantity, price_paise=line.price_paise, taxable_paise=taxable,
                         cgst_paise=cgst, sgst_paise=sgst, igst_paise=igst))
    totals = {field: sum(row[field] for row in rows) for field in ("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise")}
    invoice = Invoice.objects.create(order=order, actor=actor, document_date=document_date,
        request_key=f"invoice-order-{order.pk}", number=f"DRAFT-{order.pk}" if draft else next_invoice_number(document_date),
        status="draft" if draft else "posted",
        customer_name=order.customer.name, customer_gstin=order.customer.gstin, supply_state=state,
        total_paise=sum(totals.values()), **totals)
    for row in rows:
        InvoiceLine.objects.create(invoice=invoice, **row)
    if not draft:
        order.status = "invoiced"
        order.save(update_fields=["status"])
    audit(actor, "invoice.create", invoice, {}, {"status": invoice.status, "total_paise": invoice.total_paise})
    return invoice


@transaction.atomic
def dispatch_invoice(invoice, actor, document_date):
    authorize(actor, ["admin"])
    control = FactoryControl.objects.select_for_update().get(pk=1)
    invoice = Invoice.objects.select_related("order").get(pk=invoice.pk)
    old = Dispatch.objects.filter(invoice=invoice).first()
    if old:
        if old.document_date != document_date:
            raise ValidationError("Dispatch already posted on a different date.")
        return old
    if invoice.status != "posted" or invoice.order.status != "invoiced":
        raise ValidationError("Only an active, undispatched invoice can be dispatched.")
    balances = stock_summary()
    dispatch = Dispatch.objects.create(invoice=invoice, actor=actor, document_date=document_date, request_key=f"dispatch-{invoice.pk}")
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting = Posting.objects.create(sequence=control.last_sequence, dispatch=dispatch)
    for line in invoice.lines.select_related("sku__item"):
        item = line.sku.item
        balance = balances[item.code]
        if line.quantity > balance["quantity"]:
            raise ValidationError("Insufficient physical stock.")
        value = None if balance["value_paise"] is None else -issue_value(line.quantity, balance["quantity"], balance["value_paise"])
        source = DispatchLine.objects.create(document=dispatch, item=item, quantity=-line.quantity, value_paise=value)
        StockMovement.objects.create(posting=posting, item=item, quantity=-line.quantity, value_paise=value, dispatch_line=source)
    invoice.order.status = "dispatched"
    invoice.order.save(update_fields=["status"])
    audit(actor, "order.dispatch", invoice.order, {"status": "invoiced"}, {"status": "dispatched"})
    return dispatch


def outstanding(invoice, as_of=None):
    if invoice.status == "draft" or (as_of and invoice.document_date > as_of):
        return 0
    payments = invoice.payments.all()
    if as_of:
        payments = payments.filter(document_date__lte=as_of)
    credit = CreditNote.objects.filter(invoice=invoice)
    if as_of:
        credit = credit.filter(document_date__lte=as_of)
    return invoice.total_paise - sum(payments.values_list("amount_paise", flat=True)) - sum(credit.values_list("amount_paise", flat=True))


@transaction.atomic
def record_payment(*, invoice, amount_paise, request_key, document_date, actor):
    authorize(actor, ["admin"])
    require_integer(amount_paise, 1)
    if not request_key:
        raise ValidationError("Payment request key required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    invoice = Invoice.objects.get(pk=invoice.pk)
    old = Payment.objects.filter(request_key=request_key).first()
    if old:
        if (old.invoice_id, old.amount_paise, old.document_date) != (invoice.pk, amount_paise, document_date):
            raise ValidationError("Payment retry conflicts.")
        return old
    if invoice.status != "posted" or amount_paise > outstanding(invoice) or document_date < invoice.document_date:
        raise ValidationError("Invalid payment amount, date or invoice status.")
    return Payment.objects.create(invoice=invoice, amount_paise=amount_paise, request_key=request_key,
                                  document_date=document_date, actor=actor)


@transaction.atomic
def credit_invoice(invoice, reason, actor, document_date):
    authorize(actor, ["admin"])
    FactoryControl.objects.select_for_update().get(pk=1)
    invoice = Invoice.objects.select_related("order").get(pk=invoice.pk)
    old = CreditNote.objects.filter(invoice=invoice).first()
    if old:
        if old.reason != reason or old.document_date != document_date:
            raise ValidationError("Credit retry conflicts.")
        return old
    if invoice.status != "posted" or not reason.strip() or invoice.payments.exists() or Dispatch.objects.filter(invoice=invoice).exists():
        raise ValidationError("Full credit requires a reason and an unpaid, undispatched invoice.")
    if document_date < invoice.document_date:
        raise ValidationError("Credit cannot predate invoice.")
    credit = CreditNote.objects.create(invoice=invoice, amount_paise=invoice.total_paise, reason=reason,
        request_key=f"credit-{invoice.pk}", document_date=document_date, actor=actor)
    invoice.status = "credited"
    invoice.save(update_fields=["status"])
    audit(actor, "invoice.credit", invoice, {"status": "posted"}, {"status": "credited", "reason": reason})
    invoice.order.status, invoice.order.rejection_reason = "rejected", reason
    invoice.order.save(update_fields=["status", "rejection_reason"])
    return credit


# Called only while the factory lock is held; draft invoices do not consume FY numbers.
def next_invoice_number(document_date):
    year = document_date.year if document_date.month >= 4 else document_date.year - 1
    sequence, _ = InvoiceSequence.objects.get_or_create(financial_year=year)
    sequence.last_number += 1
    sequence.save()
    return f"{year}-{str(year+1)[-2:]}/{sequence.last_number:05d}"


@transaction.atomic
def edit_order(order, lines, actor):
    authorize(actor, ["admin"])
    FactoryControl.objects.select_for_update().get(pk=1)
    order = Order.objects.get(pk=order.pk)
    if order.status not in ("submitted", "approved") or Invoice.objects.filter(order=order).exists():
        raise ValidationError("Order is frozen once an invoice exists.")
    before = {str(line.pk): [line.quantity, line.price_paise] for line in order.lines.all()}
    if set(lines) != set(before):
        raise ValidationError("Edit the existing order lines only.")
    for line in order.lines.all():
        quantity, price = lines[str(line.pk)]
        require_integer(quantity, 1)
        require_integer(price)
        line.quantity, line.price_paise = quantity, price
        line.save(update_fields=["quantity", "price_paise"])
    order.status = "submitted"
    order.save(update_fields=["status"])
    audit(actor, "order.edit", order, before, lines)
    return order


@transaction.atomic
def edit_invoice_draft(invoice, document_date, actor):
    authorize(actor, ["admin"])
    FactoryControl.objects.select_for_update().get(pk=1)
    invoice = Invoice.objects.get(pk=invoice.pk)
    if invoice.status != "draft":
        raise ValidationError("Posted invoices cannot be edited; use an eligible credit note.")
    before = {"document_date": str(invoice.document_date)}
    invoice.document_date = document_date
    invoice.save(update_fields=["document_date"])
    audit(actor, "invoice.edit", invoice, before, {"document_date": str(document_date)})
    return invoice
