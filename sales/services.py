from fractions import Fraction
from access.services import audit
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from inventory.models import Customer, SKU, FactoryControl, Posting, StockMovement
from inventory.services import stock_summary, require_integer, round_paise, record_movement, lot_balances
from production.services import issue_value
from .models import (Order, OrderLine, Invoice, InvoiceLine, InvoiceSequence, Dispatch, DispatchLine,
                     Payment, CreditNote, CustomerPrice, SalesReturn, ReturnLine)


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
        balance["expired"] = 0
    from django.utils import timezone
    for lot in lot_balances():
        if lot.expiry_date and lot.expiry_date<timezone.localdate():
            balances[lot.item.code]["expired"] += lot.on_hand or 0
    for line in OrderLine.objects.filter(order__status__in=["approved", "invoiced"]).select_related("sku__item"):
        shipped = -sum(DispatchLine.objects.filter(document__invoice__order=line.order,item=line.sku.item).values_list("quantity",flat=True))
        balances[line.sku.item.code]["reserved"] += line.quantity - shipped
    for balance in balances.values():
        balance["available"] = balance["quantity"] - balance["expired"] - balance["reserved"]
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
        override = CustomerPrice.objects.filter(customer=customer,sku=sku).first()
        OrderLine.objects.create(order=order, sku=sku, quantity=quantity, price_paise=override.price_paise if override else sku.price_paise,
                                 price_label=override.label if override else "Price list")
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
def dispatch_invoice(invoice, actor, document_date, quantities=None, request_key=None):
    authorize(actor, ["admin"])
    if quantities is not None and not request_key:
        raise ValidationError("Partial dispatch requires its own request key.")
    control = FactoryControl.objects.select_for_update().get(pk=1)
    invoice = Invoice.objects.select_related("order").get(pk=invoice.pk)
    key = request_key or f"dispatch-{invoice.pk}"
    old = Dispatch.objects.filter(request_key=key).first()
    if old:
        previous = {str(line.item_id): -line.quantity for line in old.lines.all()}
        supplied = {str(k): v for k,v in quantities.items()} if quantities is not None else previous
        if old.invoice_id != invoice.pk or old.document_date != document_date or supplied != previous:
            raise ValidationError("Dispatch retry conflicts with the original request.")
        return old
    if invoice.status != "posted" or invoice.order.status != "invoiced":
        raise ValidationError("Only an active, undispatched invoice can be dispatched.")
    balances = stock_summary()
    remaining = dispatch_remaining(invoice)
    requested = {str(k):v for k,v in quantities.items()} if quantities is not None else {str(row["item_id"]):row["remaining"] for row in remaining if row["remaining"]}
    if not requested or set(requested)-{str(row["item_id"]) for row in remaining}:
        raise ValidationError("Select invoiced products and positive dispatch quantities.")
    for quantity in requested.values(): require_integer(quantity,1)
    dispatch = Dispatch.objects.create(invoice=invoice, actor=actor, document_date=document_date, request_key=key)
    control.last_sequence += 1
    control.save(update_fields=["last_sequence"])
    posting = Posting.objects.create(sequence=control.last_sequence, dispatch=dispatch)
    for line in invoice.lines.select_related("sku__item"):
        item = line.sku.item
        quantity = requested.get(str(item.pk),0)
        if not quantity: continue
        remaining_quantity = next(row["remaining"] for row in remaining if row["item_id"] == item.pk)
        if quantity > remaining_quantity:
            raise ValidationError("Dispatch exceeds the unshipped invoice quantity.")
        balance = balances[item.code]
        if quantity > balance["quantity"]:
            raise ValidationError("Insufficient physical stock.")
        value = None if balance["value_paise"] is None else -issue_value(quantity, balance["quantity"], balance["value_paise"])
        source = DispatchLine.objects.create(document=dispatch, item=item, quantity=-quantity, value_paise=value)
        record_movement(posting=posting, item=item, quantity=-quantity, value_paise=value, dispatch_line=source)
    invoice.order.status = "dispatched" if all(row["remaining"] == 0 for row in dispatch_remaining(invoice)) else "invoiced"
    invoice.order.save(update_fields=["status"])
    audit(actor, "order.dispatch", invoice.order, {"status": "invoiced"}, {"status": invoice.order.status, "quantities": requested})
    return dispatch


def outstanding(invoice, as_of=None):
    if invoice.status == "draft" or (as_of and invoice.document_date > as_of):
        return 0
    payments = invoice.payments.all()
    if as_of:
        payments = payments.filter(document_date__lte=as_of)
    credit = CreditNote.objects.filter(invoice=invoice)
    returns = invoice.returns.all()
    if as_of:
        credit = credit.filter(document_date__lte=as_of)
        returns = returns.filter(document_date__lte=as_of)
    return invoice.total_paise - sum(payments.values_list("amount_paise", flat=True)) - sum(credit.values_list("amount_paise", flat=True)) - sum(returns.values_list("amount_paise",flat=True))


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


# Gross dispatch progress does not reopen after a physical return.
def dispatch_remaining(invoice):
    rows = []
    for line in invoice.lines.select_related("sku__item"):
        shipped = -sum(DispatchLine.objects.filter(document__invoice=invoice,item=line.sku.item).values_list("quantity",flat=True))
        returned = sum(ReturnLine.objects.filter(invoice_line=line).values_list("quantity",flat=True))
        rows.append({"item_id":line.sku.item_id,"name":line.description,"ordered":line.quantity,
                     "shipped":shipped,"remaining":line.quantity-shipped,"returnable":shipped-returned})
    return rows


@transaction.atomic
def set_customer_price(*, customer, sku, price_paise, label, actor):
    authorize(actor,["admin"])
    require_integer(price_paise)
    if not label.strip(): raise ValidationError("Price or scheme description required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    old=CustomerPrice.objects.filter(customer=customer,sku=sku).first()
    before={"price_paise":old.price_paise,"label":old.label} if old else {}
    price,_=CustomerPrice.objects.update_or_create(customer=customer,sku=sku,defaults={"price_paise":price_paise,"label":label})
    audit(actor,"price.edit",price,before,{"price_paise":price_paise,"label":label})
    return price


def prices_for_customer(customer, actor):
    authorize(actor,["admin","salesman"])
    overrides={price.sku_id:price for price in CustomerPrice.objects.filter(customer=customer)}
    return [{"sku_id":sku.pk,"name":sku.item.name,"price_paise":overrides[sku.pk].price_paise if sku.pk in overrides else sku.price_paise,
             "label":overrides[sku.pk].label if sku.pk in overrides else "Price list"} for sku in SKU.objects.select_related("item")]


# Return credits use cumulative original tax allocation, preserving every paise on full return.
@transaction.atomic
def return_goods(*, invoice, quantities, reason, request_key, document_date, actor):
    from inventory.models import Adjustment
    from inventory.services import append_adjustment
    authorize(actor,["admin"])
    if not request_key or not reason.strip() or not quantities:
        raise ValidationError("Return quantities, reason and request key required.")
    requested={str(k):v for k,v in quantities.items()}
    for quantity in requested.values(): require_integer(quantity,1)
    control=FactoryControl.objects.select_for_update().get(pk=1)
    invoice=Invoice.objects.get(pk=invoice.pk)
    payload={"invoice":invoice.pk,"quantities":requested,"reason":reason,"date":str(document_date)}
    old=SalesReturn.objects.filter(request_key=request_key).first()
    if old:
        if old.payload!=payload or old.actor_id!=actor.pk: raise ValidationError("Return retry conflicts.")
        return old
    if invoice.status!="posted" or document_date<invoice.document_date:
        raise ValidationError("Return requires a posted invoice and a valid date.")
    progress={str(row["item_id"]):row for row in dispatch_remaining(invoice)}
    if set(requested)-set(progress): raise ValidationError("Return contains an uninvoiced product.")
    adjustment=Adjustment.objects.create(reason="Customer return: "+reason,payload=payload,request_key="return-"+request_key,document_date=document_date,actor=actor)
    note=SalesReturn.objects.create(invoice=invoice,adjustment=adjustment,reason=reason,payload=payload,
        request_key=request_key,document_date=document_date,actor=actor,amount_paise=0)
    stock_lines=[]
    for line in invoice.lines.select_related("sku__item"):
        quantity=requested.get(str(line.sku.item_id),0)
        if not quantity: continue
        if quantity>progress[str(line.sku.item_id)]["returnable"]:
            raise ValidationError("Return exceeds delivered, not-yet-returned quantity.")
        remaining=quantity
        value=0
        for shipped in DispatchLine.objects.filter(document__invoice=invoice,item=line.sku.item).select_related("document").order_by("pk"):
            returned=sum(ReturnLine.objects.filter(dispatch_line=shipped).values_list("quantity",flat=True))
            portion=min(remaining,-shipped.quantity-returned)
            if not portion: continue
            if document_date<shipped.document.document_date:
                raise ValidationError("A return cannot predate its dispatch.")
            prior=ReturnLine.objects.filter(invoice_line=line)
            previous_quantity=sum(prior.values_list("quantity",flat=True))
            values={field:round_paise(Fraction(getattr(line,field)*(previous_quantity+portion),line.quantity))-sum(prior.values_list(field,flat=True))
                    for field in ("taxable_paise","cgst_paise","sgst_paise","igst_paise")}
            stock_value=None if shipped.value_paise is None else round_paise(Fraction(shipped.value_paise*(returned+portion),shipped.quantity))-round_paise(Fraction(shipped.value_paise*returned,shipped.quantity))
            ReturnLine.objects.create(document=note,invoice_line=line,dispatch_line=shipped,quantity=portion,stock_value_paise=stock_value,**values)
            note.amount_paise+=sum(values.values())
            value=None if value is None or stock_value is None else value+stock_value
            remaining-=portion
            if not remaining: break
        stock_lines.append((line.sku.item,quantity,value))
    append_adjustment(control,adjustment,stock_lines)
    note.save(update_fields=["amount_paise"])
    audit(actor,"invoice.return",invoice,{},payload)
    return note
