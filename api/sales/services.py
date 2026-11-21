"""Native sales transactions sharing the inventory factory lock and source schema."""

from datetime import date
from fractions import Fraction
from sqlalchemy import select, update, text
from api import database
from api.native import (
    authorize,
    required_integer,
    factory_lock,
    table,
    insert_row,
    posting,
    movement,
    issue_value,
    balance,
    audit,
    now,
    round_paise,
)


def get_row(conn, name, identifier):
    target = table(conn, name)
    row = (
        conn.execute(
            select(target).where(target.c.id == required_integer(identifier, 1))
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError("Record not found.")
    return row


def change(conn, name, identifier, **values):
    target = table(conn, name)
    conn.execute(update(target).where(target.c.id == identifier).values(**values))


def quantity_map(values):
    if not isinstance(values, dict) or not values:
        raise ValueError("Positive quantities are required.")
    result = {
        str(required_integer(key, 1)): required_integer(value, 1)
        for key, value in values.items()
    }
    if len(result) != len(values):
        raise ValueError("Duplicate product identifier.")
    return result


# Reservations are derived from approved/invoiced lines less gross dispatch, not mutable counters.
def available(conn, item_id):
    quantity, _ = balance(conn, item_id)
    expired = conn.execute(
        text(
            """SELECT COALESCE(SUM(a.quantity),0) FROM inventory_lotallocation a
        JOIN inventory_stocklot l ON l.id=a.lot_id WHERE l.item_id=:item AND l.expiry_date<:today"""
        ),
        {"item": item_id, "today": now().date()},
    ).scalar_one()
    reserved = conn.execute(
        text(
            """SELECT COALESCE(SUM(l.quantity + COALESCE((
        SELECT SUM(d.quantity) FROM sales_dispatchline d JOIN sales_dispatch h ON h.id=d.document_id
        JOIN sales_invoice i ON i.id=h.invoice_id WHERE i.order_id=o.id AND d.item_id=s.item_id),0)),0)
        FROM sales_orderline l JOIN sales_order o ON o.id=l.order_id JOIN inventory_sku s ON s.id=l.sku_id
        WHERE s.item_id=:item AND o.status IN ('approved','invoiced')"""
        ),
        {"item": item_id},
    ).scalar_one()
    return quantity - int(expired) - int(reserved)


def order_lines(conn, identifier):
    return (
        conn.execute(
            text(
                """SELECT l.*,s.item_id,s.hsn,i.name AS description FROM sales_orderline l
        JOIN inventory_sku s ON s.id=l.sku_id JOIN inventory_item i ON i.id=s.item_id
        WHERE l.order_id=:id ORDER BY l.id"""
            ),
            {"id": identifier},
        )
        .mappings()
        .all()
    )


# Each tax component rounds independently per line; invoice totals are sums of those integers.
def line_tax(taxable, interstate):
    required_integer(taxable, 0)
    if interstate:
        return (0, 0, round_paise(Fraction(taxable * 5, 100)))
    half = round_paise(Fraction(taxable * 25, 1000))
    return half, half, 0


# Only called under the factory lock; drafts never consume a financial-year sequence.
def next_number(conn, day):
    year = day.year if day.month >= 4 else day.year - 1
    number = conn.execute(
        text(
            """INSERT INTO sales_invoicesequence(financial_year,last_number) VALUES (:year,1)
        ON CONFLICT(financial_year) DO UPDATE SET last_number=sales_invoicesequence.last_number+1
        RETURNING last_number"""
        ),
        {"year": year},
    ).scalar_one()
    return f"{year}-{str(year+1)[-2:]}/{number:05d}"


def submit(conn, data, user, key, day):
    quantities = quantity_map(data["quantities"])
    customer = get_row(conn, "inventory_customer", data["customer"])
    orders = table(conn, "sales_order")
    old = (
        conn.execute(select(orders).where(orders.c.request_key == key))
        .mappings()
        .first()
    )
    if old:
        if (
            old["customer_id"],
            old["actor_id"],
            old["document_date"],
            old["submitted_payload"],
        ) != (customer["id"], user["id"], day, quantities):
            raise ValueError("Order request key conflicts with an existing order.")
        return old["id"]
    identifier = insert_row(
        conn,
        "sales_order",
        customer_id=customer["id"],
        actor_id=user["id"],
        document_date=day,
        request_key=key,
        submitted_payload=quantities,
        status="submitted",
        rejection_reason="",
    )
    for sku_id, quantity in quantities.items():
        sku = get_row(conn, "inventory_sku", sku_id)
        item = get_row(conn, "inventory_item", sku["item_id"])
        if item["category"] != "finished":
            raise ValueError("Only finished goods can be ordered.")
        prices = table(conn, "sales_customerprice")
        price = (
            conn.execute(
                select(prices).where(
                    prices.c.customer_id == customer["id"], prices.c.sku_id == sku["id"]
                )
            )
            .mappings()
            .first()
        )
        insert_row(
            conn,
            "sales_orderline",
            order_id=identifier,
            sku_id=sku["id"],
            quantity=quantity,
            price_paise=price["price_paise"] if price else sku["price_paise"],
            price_label=price["label"] if price else "Price list",
        )
    audit(conn, user, "order.submit", "sales.Order", identifier, {}, quantities)
    return identifier


def make_invoice(conn, order, user, day, draft, old):
    if old:
        if old["document_date"] != day:
            raise ValueError("Invoice already exists with a different date.")
        if old["status"] == "draft" and not draft:
            number = next_number(conn, day)
            change(conn, "sales_invoice", old["id"], status="posted", number=number)
            change(conn, "sales_order", order["id"], status="invoiced")
            audit(
                conn,
                user,
                "invoice.post",
                "sales.Invoice",
                old["id"],
                {"status": "draft"},
                {"status": "posted", "number": number},
            )
        return old["id"]
    if order["status"] != "approved":
        raise ValueError("Approve the order first.")
    customer = get_row(conn, "inventory_customer", order["customer_id"])
    state = customer["gstin"][:2] if customer["gstin"] else customer["state_code"]
    if len(state) != 2 or not state.isdigit():
        raise ValueError("Customer supply state is required.")
    rows = []
    for line in order_lines(conn, order["id"]):
        taxable = line["quantity"] * line["price_paise"]
        cgst, sgst, igst = line_tax(taxable, state != "33")
        rows.append(
            {
                **{
                    key: line[key]
                    for key in (
                        "sku_id",
                        "description",
                        "hsn",
                        "quantity",
                        "price_paise",
                    )
                },
                "taxable_paise": taxable,
                "cgst_paise": cgst,
                "sgst_paise": sgst,
                "igst_paise": igst,
            }
        )
    totals = {
        field: sum(row[field] for row in rows)
        for field in ("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise")
    }
    status = "draft" if draft else "posted"
    identifier = insert_row(
        conn,
        "sales_invoice",
        order_id=order["id"],
        actor_id=user["id"],
        document_date=day,
        request_key=f"invoice-order-{order['id']}",
        number=f"DRAFT-{order['id']}" if draft else next_number(conn, day),
        status=status,
        customer_name=customer["name"],
        customer_gstin=customer["gstin"],
        supply_state=state,
        total_paise=sum(totals.values()),
        **totals,
    )
    for row in rows:
        insert_row(conn, "sales_invoiceline", invoice_id=identifier, **row)
    if not draft:
        change(conn, "sales_order", order["id"], status="invoiced")
    audit(
        conn,
        user,
        "invoice.create",
        "sales.Invoice",
        identifier,
        {},
        {"status": status, "total_paise": sum(totals.values())},
    )
    return identifier


def invoice_lines(conn, identifier):
    return (
        conn.execute(
            text(
                """SELECT l.*,s.item_id FROM sales_invoiceline l JOIN inventory_sku s ON s.id=l.sku_id
        WHERE l.invoice_id=:id ORDER BY l.id"""
            ),
            {"id": identifier},
        )
        .mappings()
        .all()
    )


def shipped(conn, invoice_id, item_id):
    return -int(
        conn.execute(
            text(
                """SELECT COALESCE(SUM(l.quantity),0) FROM sales_dispatchline l
        JOIN sales_dispatch d ON d.id=l.document_id WHERE d.invoice_id=:invoice AND l.item_id=:item"""
            ),
            {"invoice": invoice_id, "item": item_id},
        ).scalar_one()
    )


def dispatch(conn, order, invoice, data, user, key, day):
    documents = table(conn, "sales_dispatch")
    old = (
        conn.execute(select(documents).where(documents.c.request_key == key))
        .mappings()
        .first()
    )
    requested = quantity_map(data["quantities"]) if "quantities" in data else None
    if old:
        lines = table(conn, "sales_dispatchline")
        previous = {
            str(row["item_id"]): -row["quantity"]
            for row in conn.execute(
                select(lines).where(lines.c.document_id == old["id"])
            ).mappings()
        }
        if (
            old["invoice_id"] != invoice["id"]
            or old["document_date"] != day
            or (requested is not None and requested != previous)
        ):
            raise ValueError("Dispatch retry conflicts with the original request.")
        return old["id"]
    if invoice["status"] != "posted" or order["status"] != "invoiced":
        raise ValueError("Only an active, undispatched invoice can be dispatched.")
    lines = invoice_lines(conn, invoice["id"])
    remaining = {
        str(line["item_id"]): line["quantity"]
        - shipped(conn, invoice["id"], line["item_id"])
        for line in lines
    }
    requested = (
        requested
        if requested is not None
        else {key: value for key, value in remaining.items() if value}
    )
    if not requested or set(requested) - set(remaining):
        raise ValueError("Select invoiced products and positive dispatch quantities.")
    identifier = insert_row(
        conn,
        "sales_dispatch",
        invoice_id=invoice["id"],
        actor_id=user["id"],
        document_date=day,
        request_key=key,
    )
    posting_id, sequence = posting(conn, "dispatch", identifier)
    for line in lines:
        item = line["item_id"]
        quantity = requested.get(str(item), 0)
        if not quantity:
            continue
        if quantity > remaining[str(item)]:
            raise ValueError("Dispatch exceeds the unshipped invoice quantity.")
        on_hand, value = balance(conn, item)
        if quantity > on_hand:
            raise ValueError("Insufficient physical stock.")
        value = None if value is None else -issue_value(quantity, on_hand, value)
        source = insert_row(
            conn,
            "sales_dispatchline",
            document_id=identifier,
            item_id=item,
            quantity=-quantity,
            value_paise=value,
        )
        movement(
            conn,
            posting_id=posting_id,
            sequence=sequence,
            item_id=item,
            quantity=-quantity,
            value_paise=value,
            source="dispatch_line",
            source_id=source,
        )
    status = (
        "dispatched"
        if all(remaining[item] == requested.get(item, 0) for item in remaining)
        else "invoiced"
    )
    change(conn, "sales_order", order["id"], status=status)
    audit(
        conn,
        user,
        "order.dispatch",
        "sales.Order",
        order["id"],
        {"status": "invoiced"},
        {"status": status, "quantities": requested},
    )
    return identifier


def outstanding(conn, invoice, as_of=None):
    if invoice["status"] == "draft" or (as_of and invoice["document_date"] > as_of):
        return 0
    deducted = 0
    for name in ("sales_payment", "sales_creditnote", "sales_salesreturn"):
        target = table(conn, name)
        from sqlalchemy import func

        query = select(func.coalesce(func.sum(target.c.amount_paise), 0)).where(
            target.c.invoice_id == invoice["id"]
        )
        if as_of:
            query = query.where(target.c.document_date <= as_of)
        deducted += int(conn.execute(query).scalar_one())
    return invoice["total_paise"] - deducted


# Cumulative allocation restores original tax and dispatch valuation, including the last paise.
def return_goods(conn, invoice, data, user, key, day):
    from api.inventory.corrections import append_adjustment

    requested = quantity_map(data["quantities"])
    reason = data["reason"]
    if not reason.strip():
        raise ValueError("Return reason required.")
    payload = {
        "invoice": invoice["id"],
        "quantities": requested,
        "reason": reason,
        "date": str(day),
    }
    returns = table(conn, "sales_salesreturn")
    old = (
        conn.execute(select(returns).where(returns.c.request_key == key))
        .mappings()
        .first()
    )
    if old:
        if old["payload"] != payload or old["actor_id"] != user["id"]:
            raise ValueError("Return retry conflicts.")
        return old["id"]
    if invoice["status"] != "posted" or day < invoice["document_date"]:
        raise ValueError("Return requires a posted invoice and a valid date.")
    lines = invoice_lines(conn, invoice["id"])
    if set(requested) - {str(line["item_id"]) for line in lines}:
        raise ValueError("Return contains an uninvoiced product.")
    adjustment = insert_row(
        conn,
        "inventory_adjustment",
        reason="Customer return: " + reason,
        payload=payload,
        request_key="return-" + key,
        document_date=day,
        actor_id=user["id"],
        reversed_run_id=None,
    )
    identifier = insert_row(
        conn,
        "sales_salesreturn",
        invoice_id=invoice["id"],
        adjustment_id=adjustment,
        reason=reason,
        payload=payload,
        request_key=key,
        document_date=day,
        actor_id=user["id"],
        amount_paise=0,
    )
    stock_lines = []
    total = 0
    returns_lines = table(conn, "sales_returnline")
    fields = ("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise")
    for line in lines:
        quantity = requested.get(str(line["item_id"]), 0)
        if not quantity:
            continue
        prior = list(
            conn.execute(
                select(returns_lines).where(
                    returns_lines.c.invoice_line_id == line["id"]
                )
            ).mappings()
        )
        if quantity > shipped(conn, invoice["id"], line["item_id"]) - sum(
            row["quantity"] for row in prior
        ):
            raise ValueError("Return exceeds delivered, not-yet-returned quantity.")
        deliveries = (
            conn.execute(
                text(
                    """SELECT l.*,d.document_date FROM sales_dispatchline l
            JOIN sales_dispatch d ON d.id=l.document_id WHERE d.invoice_id=:invoice AND l.item_id=:item
            ORDER BY l.id"""
                ),
                {"invoice": invoice["id"], "item": line["item_id"]},
            )
            .mappings()
            .all()
        )
        remaining = quantity
        value = 0
        for delivery in deliveries:
            returned = sum(
                row["quantity"]
                for row in prior
                if row["dispatch_line_id"] == delivery["id"]
            )
            portion = min(remaining, -delivery["quantity"] - returned)
            if not portion:
                continue
            if day < delivery["document_date"]:
                raise ValueError("A return cannot predate its dispatch.")
            previous = sum(row["quantity"] for row in prior)
            values = {
                field: round_paise(
                    Fraction(line[field] * (previous + portion), line["quantity"])
                )
                - sum(row[field] for row in prior)
                for field in fields
            }
            cost = delivery["value_paise"]
            stock_value = (
                None
                if cost is None
                else round_paise(
                    Fraction(cost * (returned + portion), delivery["quantity"])
                )
                - round_paise(Fraction(cost * returned, delivery["quantity"]))
            )
            record = {
                "document_id": identifier,
                "invoice_line_id": line["id"],
                "dispatch_line_id": delivery["id"],
                "quantity": portion,
                "stock_value_paise": stock_value,
                **values,
            }
            insert_row(conn, "sales_returnline", **record)
            prior.append(record)
            total += sum(values.values())
            value = (
                None if value is None or stock_value is None else value + stock_value
            )
            remaining -= portion
            if not remaining:
                break
        stock_lines.append((line["item_id"], quantity, value))
    append_adjustment(conn, adjustment, stock_lines, payload, user)
    change(conn, "sales_salesreturn", identifier, amount_paise=total)
    audit(conn, user, "invoice.return", "sales.Invoice", invoice["id"], {}, payload)
    return identifier


# One transaction spans permissions, reservation decisions, documents, ledger and audit records.
def command(action, data, user, key):
    authorize(user, ["admin", "salesman"] if action == "order.create" else ["admin"])
    if not key:
        raise ValueError("Request key required.")
    day = date.fromisoformat(data["date"])
    with database.transaction() as conn:
        factory_lock(conn)
        if action == "order.create":
            return submit(conn, data, user, key, day)
        order = get_row(conn, "sales_order", data["id"])
        invoices = table(conn, "sales_invoice")
        invoice = (
            conn.execute(select(invoices).where(invoices.c.order_id == order["id"]))
            .mappings()
            .first()
        )
        identifier = order["id"]
        if action == "order.approve":
            if order["status"] == "approved":
                return identifier
            if order["status"] != "submitted":
                raise ValueError("Only submitted orders can be approved.")
            if any(
                line["quantity"] > available(conn, line["item_id"])
                for line in order_lines(conn, identifier)
            ):
                raise ValueError(
                    "Insufficient available stock; order remains submitted."
                )
            change(conn, "sales_order", identifier, status="approved")
            audit(
                conn,
                user,
                "order.approve",
                "sales.Order",
                identifier,
                {"status": "submitted"},
                {"status": "approved"},
            )
        elif action == "order.reject":
            reason = data["reason"]
            if not reason.strip():
                raise ValueError("A rejection reason is required.")
            if order["status"] == "rejected" and order["rejection_reason"] == reason:
                return identifier
            if order["status"] not in ("submitted", "approved") or invoice:
                raise ValueError("This order cannot be rejected directly.")
            change(
                conn,
                "sales_order",
                identifier,
                status="rejected",
                rejection_reason=reason,
            )
            audit(
                conn,
                user,
                "order.reject",
                "sales.Order",
                identifier,
                {"status": order["status"]},
                {"status": "rejected", "reason": reason},
            )
        elif action == "order.edit":
            if order["status"] not in ("submitted", "approved") or invoice:
                raise ValueError("Order is frozen once an invoice exists.")
            lines = order_lines(conn, identifier)
            before = {
                str(line["id"]): [line["quantity"], line["price_paise"]]
                for line in lines
            }
            if set(data["lines"]) != set(before):
                raise ValueError("Edit the existing order lines only.")
            after = {}
            for line in lines:
                quantity, price = data["lines"][str(line["id"])]
                quantity = required_integer(quantity, 1)
                price = required_integer(price, 0)
                change(
                    conn,
                    "sales_orderline",
                    line["id"],
                    quantity=quantity,
                    price_paise=price,
                )
                after[str(line["id"])] = [quantity, price]
            change(conn, "sales_order", identifier, status="submitted")
            audit(conn, user, "order.edit", "sales.Order", identifier, before, after)
        elif action == "order.invoice":
            return make_invoice(
                conn, order, user, day, data.get("draft") is True, invoice
            )
        else:
            if invoice is None:
                raise ValueError("Create an invoice before this action.")
            if action == "order.dispatch":
                return dispatch(conn, order, invoice, data, user, key, day)
            if action == "order.return":
                return return_goods(conn, invoice, data, user, key, day)
            if action == "order.edit_invoice":
                if invoice["status"] != "draft":
                    raise ValueError(
                        "Posted invoices cannot be edited; use an eligible credit note."
                    )
                change(conn, "sales_invoice", invoice["id"], document_date=day)
                audit(
                    conn,
                    user,
                    "invoice.edit",
                    "sales.Invoice",
                    invoice["id"],
                    {"document_date": str(invoice["document_date"])},
                    {"document_date": str(day)},
                )
                return invoice["id"]
            if action == "order.payment":
                amount = required_integer(data["amount_paise"], 1)
                target = table(conn, "sales_payment")
                old = (
                    conn.execute(select(target).where(target.c.request_key == key))
                    .mappings()
                    .first()
                )
                if old:
                    if (
                        old["invoice_id"],
                        old["amount_paise"],
                        old["document_date"],
                    ) != (invoice["id"], amount, day):
                        raise ValueError("Payment retry conflicts.")
                    return old["id"]
                if (
                    invoice["status"] != "posted"
                    or amount > outstanding(conn, invoice)
                    or day < invoice["document_date"]
                ):
                    raise ValueError("Invalid payment amount, date or invoice status.")
                return insert_row(
                    conn,
                    "sales_payment",
                    invoice_id=invoice["id"],
                    amount_paise=amount,
                    request_key=key,
                    document_date=day,
                    actor_id=user["id"],
                )
            if action == "order.credit":
                reason = data["reason"]
                credits = table(conn, "sales_creditnote")
                old = (
                    conn.execute(
                        select(credits).where(credits.c.invoice_id == invoice["id"])
                    )
                    .mappings()
                    .first()
                )
                if old:
                    if old["reason"] != reason or old["document_date"] != day:
                        raise ValueError("Credit retry conflicts.")
                    return old["id"]
                for name in ("sales_payment", "sales_dispatch"):
                    target = table(conn, name)
                    if conn.execute(
                        select(target.c.id).where(target.c.invoice_id == invoice["id"])
                    ).first():
                        raise ValueError(
                            "Full credit requires an unpaid, undispatched invoice."
                        )
                if (
                    invoice["status"] != "posted"
                    or not reason.strip()
                    or day < invoice["document_date"]
                ):
                    raise ValueError("Invalid credit reason, date or invoice status.")
                credit = insert_row(
                    conn,
                    "sales_creditnote",
                    invoice_id=invoice["id"],
                    amount_paise=invoice["total_paise"],
                    reason=reason,
                    request_key=f"credit-{invoice['id']}",
                    document_date=day,
                    actor_id=user["id"],
                )
                change(conn, "sales_invoice", invoice["id"], status="credited")
                change(
                    conn,
                    "sales_order",
                    identifier,
                    status="rejected",
                    rejection_reason=reason,
                )
                audit(
                    conn,
                    user,
                    "invoice.credit",
                    "sales.Invoice",
                    invoice["id"],
                    {"status": "posted"},
                    {"status": "credited", "reason": reason},
                )
                return credit
            raise ValueError("Unknown sales action.")
        return identifier
