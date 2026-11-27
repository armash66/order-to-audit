"""Role-scoped SQLAlchemy workspace reads over the existing PostgreSQL schema."""

from fractions import Fraction
from fastapi import HTTPException
from sqlalchemy import select, text
from api import database
from api.native import authorize, factory_lock, table, now
from api.sales.services import (
    get_row,
    available,
    order_lines,
    invoice_lines,
    shipped,
    outstanding,
)
from api.production.services import run_report


def rows(conn, sql, **params):
    return [dict(row) for row in conn.execute(text(sql), params).mappings()]


def scoped_order(conn, identifier, user):
    authorize(user, ["admin", "salesman", "accountant", "owner"])
    order = get_row(conn, "sales_order", identifier)
    if (
        not user["is_staff"]
        and "salesman" in user["roles"]
        and order["actor_id"] != user["id"]
    ):
        raise HTTPException(403, "You can only access your own orders.")
    return order


# Suggestions read non-expired, unreserved stock and never post or reserve their own quantities.
def suggestion(conn, sku_id):
    bom = rows(
        conn,
        "SELECT * FROM inventory_bom WHERE sku_id=:sku ORDER BY version DESC LIMIT 1",
        sku=sku_id,
    )
    if not bom:
        return None
    bom = bom[0]
    sku = get_row(conn, "inventory_sku", sku_id)
    demand = conn.execute(
        text(
            "SELECT COALESCE(SUM(l.quantity),0) FROM sales_orderline l JOIN sales_order o ON o.id=l.order_id WHERE l.sku_id=:sku AND o.status='submitted'"
        ),
        {"sku": sku_id},
    ).scalar_one()
    uncovered = max(0, int(demand) - available(conn, sku["item_id"]))
    batches = (uncovered + bom["expected_packets"] - 1) // bom["expected_packets"]
    inputs = rows(
        conn,
        """SELECT l.item_id,l.quantity,i.code,i.base_unit FROM inventory_recipeline l
        JOIN inventory_item i ON i.id=l.item_id WHERE l.recipe_id=:recipe UNION ALL
        SELECT l.item_id,l.quantity,i.code,i.base_unit FROM inventory_bomline l
        JOIN inventory_item i ON i.id=l.item_id WHERE l.bom_id=:bom""",
        recipe=bom["recipe_id"],
        bom=bom["id"],
    )
    result = []
    for line in inputs:
        stock = available(conn, line["item_id"])
        needed = line["quantity"] * batches
        result.append(
            {
                "item": line["code"],
                "unit": line["base_unit"],
                "stock": stock,
                "required": needed,
                "shortage": max(0, needed - stock),
                "supported_batches": Fraction(stock, line["quantity"]),
                "feasible_batches": stock // line["quantity"],
            }
        )
    feasible = min((row["feasible_batches"] for row in result), default=0)
    return {
        "uncovered": uncovered,
        "required_batches": batches,
        "feasible_batches": feasible,
        "blocked": batches > feasible,
        "next_action": (
            "Receive missing BOM inputs, then start production."
            if batches > feasible else
            "Start the suggested production run."
            if batches else "Available finished goods cover submitted demand."
        ),
        "inputs": result,
    }


# Trace an input or finished-goods lot through immutable allocations and dispatches.
def recall(lot_id, user):
    authorize(user, ["admin", "production", "accountant", "owner"])
    with database.transaction() as conn:
        lot = get_row(conn, "inventory_stocklot", lot_id)
        item = get_row(conn, "inventory_item", lot["item_id"])
        movements = rows(conn, """SELECT m.id,m.posting_id,m.quantity,p.sequence,p.opening_id,p.purchase_id,
            p.production_id,p.dispatch_id,p.adjustment_id FROM inventory_lotallocation a
            JOIN inventory_stockmovement m ON m.id=a.movement_id
            JOIN inventory_posting p ON p.id=m.posting_id WHERE a.lot_id=:lot ORDER BY p.sequence,m.id""", lot=lot_id)
        run_ids = {row["run_id"] for row in rows(conn, """SELECT DISTINCT e.run_id
            FROM inventory_lotallocation a JOIN inventory_stockmovement m ON m.id=a.movement_id
            JOIN production_productionline l ON l.id=m.production_line_id
            JOIN production_productionevent e ON e.id=l.event_id
            WHERE a.lot_id=:lot AND m.quantity<0""", lot=lot_id)}
        finished = []
        if item["category"] == "finished":
            finished.append({"id": lot["id"], "code": lot["code"], "item": item["name"]})
        for run_id in sorted(run_ids):
            finished.extend(rows(conn, """SELECT DISTINCT b.id,b.code,i.name AS item
                FROM production_productionevent e JOIN production_productionline l ON l.event_id=e.id
                JOIN inventory_stockmovement m ON m.production_line_id=l.id
                JOIN inventory_lotallocation a ON a.movement_id=m.id
                JOIN inventory_stocklot b ON b.id=a.lot_id
                JOIN inventory_item i ON i.id=b.item_id
                WHERE e.run_id=:run AND m.quantity>0 AND i.category='finished'""", run=run_id))
        finished = list({row["id"]: row for row in finished}.values())
        dispatches = []
        for fg in finished:
            dispatches.extend(rows(conn, """SELECT DISTINCT d.id AS dispatch_id,d.document_date,
                v.number AS invoice,c.name AS customer,-a.quantity AS packets
                FROM inventory_lotallocation a JOIN inventory_stockmovement m ON m.id=a.movement_id
                JOIN sales_dispatchline l ON l.id=m.dispatch_line_id
                JOIN sales_dispatch d ON d.id=l.document_id JOIN sales_invoice v ON v.id=d.invoice_id
                JOIN sales_order o ON o.id=v.order_id JOIN inventory_customer c ON c.id=o.customer_id
                WHERE a.lot_id=:lot AND a.quantity<0 ORDER BY d.id""", lot=fg["id"]))
        return {"lot": {"id": lot["id"], "code": lot["code"], "item": item["name"],
                        "expiry": lot["expiry_date"]}, "movements": movements,
                "production_run_ids": sorted(run_ids), "finished_lots": finished,
                "dispatches": dispatches}


def order_detail(identifier, user):
    with database.transaction() as conn:
        factory_lock(conn)
        order = scoped_order(conn, identifier, user)
        customer = get_row(conn, "inventory_customer", order["customer_id"])
        lines = order_lines(conn, order["id"])
        result = {
            "id": order["id"],
            "status": order["status"],
            "customer": customer["name"],
            "reason": order["rejection_reason"],
            "lines": [
                {
                    "id": line["id"],
                    "sku_id": line["sku_id"],
                    "sku__item__name": line["description"],
                    "quantity": line["quantity"],
                    "price_paise": line["price_paise"],
                }
                for line in lines
            ],
            "stock": [],
            "invoice": None,
        }
        for line in lines:
            stock = available(conn, line["item_id"])
            item = get_row(conn, "inventory_item", line["item_id"])
            result["stock"].append(
                {
                    "item": item["code"],
                    "requested": line["quantity"],
                    "available": stock,
                    "shortage": max(0, line["quantity"] - stock),
                }
            )
        invoice = rows(
            conn, "SELECT * FROM sales_invoice WHERE order_id=:id", id=order["id"]
        )
        if invoice:
            invoice = invoice[0]
            progress = []
            for line in invoice_lines(conn, invoice["id"]):
                sent = shipped(conn, invoice["id"], line["item_id"])
                returned = int(
                    conn.execute(
                        text(
                            "SELECT COALESCE(SUM(quantity),0) FROM sales_returnline WHERE invoice_line_id=:id"
                        ),
                        {"id": line["id"]},
                    ).scalar_one()
                )
                progress.append(
                    {
                        "item_id": line["item_id"],
                        "name": line["description"],
                        "ordered": line["quantity"],
                        "shipped": sent,
                        "remaining": line["quantity"] - sent,
                        "returnable": sent - returned,
                    }
                )
            result["invoice"] = {
                field: invoice[field]
                for field in (
                    "id",
                    "number",
                    "status",
                    "taxable_paise",
                    "cgst_paise",
                    "sgst_paise",
                    "igst_paise",
                    "total_paise",
                )
            }
            result["invoice"].update(
                outstanding=outstanding(conn, invoice), fulfilment=progress
            )
            result["invoice"]["followups"] = rows(conn, """SELECT f.id,f.note,f.next_contact,
                f.recorded_at,u.username AS actor FROM factory_collectionfollowup f
                JOIN auth_user u ON u.id=f.actor_id WHERE f.invoice_id=:id ORDER BY f.id DESC""", id=invoice["id"])
        if user["is_staff"] or "admin" in user["roles"]:
            result["suggestions"] = [
                value
                for line in lines
                if (value := suggestion(conn, line["sku_id"])) is not None
            ]
        return result


def read(kind, user, identifier=None):
    roles = (
        ["admin", "production", "salesman", "accountant", "owner"]
        if kind == "catalog"
        else (
            ["admin", "production"]
            if kind in ("runs", "run")
            else (
                ["admin", "salesman"]
                if kind == "prices"
                else (
                    ["admin", "production", "accountant", "owner"]
                    if kind in ("batches", "source", "audit", "receipts")
                    else ["admin", "salesman", "accountant", "owner"]
                )
            )
        )
    )
    authorize(user, roles)
    with database.transaction() as conn:
        if kind == "receipts":
            # Only posted receipt lines appear; each row retains its source posting and item.
            return rows(conn, """SELECT l.id,p.id AS receipt_id,p.document_date,s.name AS supplier,
                i.code AS item_code,i.name AS item,i.base_unit,l.quantity,l.value_paise,
                posting.id AS posting_id
                FROM inventory_purchasereceipt p JOIN inventory_purchaseline l ON l.document_id=p.id
                JOIN inventory_supplier s ON s.id=p.supplier_id
                JOIN inventory_item i ON i.id=l.item_id
                JOIN inventory_posting posting ON posting.purchase_id=p.id
                ORDER BY posting.id DESC,l.id""")
        if kind == "audit":
            # Recent entries show who changed a document and its recorded before/after values.
            return rows(
                conn,
                """SELECT a.id,a.occurred_at,u.username AS actor,a.action,a.source_type,
                    a.source_id,a.before,a.after FROM access_auditlog a
                    JOIN auth_user u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 100""",
            )
        if kind == "catalog":
            factory = user["is_staff"] or bool(
                set(user["roles"]) & {"admin", "production", "accountant", "owner"}
            )
            return {
                "today": now().date(),
                "user_id": user["id"],
                "customers": rows(conn, "SELECT * FROM inventory_customer ORDER BY id"),
                "suppliers": (
                    rows(conn, "SELECT * FROM inventory_supplier ORDER BY id")
                    if factory
                    else []
                ),
                "items": (
                    rows(conn, "SELECT * FROM inventory_item ORDER BY id")
                    if factory
                    else []
                ),
                "skus": rows(
                    conn,
                    "SELECT s.id,s.item_id,i.name AS item__name,s.pack_size_g,s.price_paise,s.hsn FROM inventory_sku s JOIN inventory_item i ON i.id=s.item_id ORDER BY s.id",
                ),
                "boms": (
                    rows(
                        conn,
                        "SELECT b.id,i.name AS sku__item__name,b.version,b.expected_packets FROM inventory_bom b JOIN inventory_sku s ON s.id=b.sku_id JOIN inventory_item i ON i.id=s.item_id ORDER BY b.id",
                    )
                    if factory
                    else []
                ),
                "recipes": (
                    rows(conn, "SELECT id,code,version FROM inventory_recipe ORDER BY code,version")
                    if factory else []
                ),
            }
        if kind == "orders":
            own = not user["is_staff"] and "salesman" in user["roles"]
            return rows(
                conn,
                """SELECT o.id,c.name AS customer__name,o.status,o.document_date FROM sales_order o
                JOIN inventory_customer c ON c.id=o.customer_id WHERE (:own=FALSE OR o.actor_id=:actor) ORDER BY o.id DESC""",
                own=own,
                actor=user["id"],
            )
        if kind == "runs":
            return rows(
                conn,
                """SELECT r.id,i.name AS output_item__name,r.state,r.expected_packets,r.good_packets
            FROM production_productionrun r JOIN inventory_item i ON i.id=r.output_item_id ORDER BY r.id DESC""",
            )
        if kind == "run":
            factory_lock(conn)
            run = get_row(conn, "production_productionrun", identifier)
            item = get_row(conn, "inventory_item", run["output_item_id"])
            result = {
                "id": run["id"],
                "name": item["name"],
                "state": run["state"],
                "report": run_report(identifier, user, conn),
                "standards": rows(
                    conn,
                    """SELECT i.code AS item__code,i.name AS item__name,i.base_unit AS item__base_unit,s.quantity,s.stage
                    FROM production_runstandard s JOIN inventory_item i ON i.id=s.item_id WHERE s.run_id=:id ORDER BY s.id""",
                    id=run["id"],
                ),
            }
            result["loss_notes"] = rows(conn, """SELECT n.id,n.reason,n.note,n.recorded_at,
                u.username AS actor FROM factory_lossnote n JOIN auth_user u ON u.id=n.actor_id
                WHERE n.run_id=:id ORDER BY n.id""", id=run["id"])
            return result
        if kind == "prices":
            get_row(conn, "inventory_customer", identifier)
            return rows(
                conn,
                """SELECT s.id AS sku_id,i.name,COALESCE(p.price_paise,s.price_paise) AS price_paise,
                COALESCE(p.label,'Price list') AS label FROM inventory_sku s JOIN inventory_item i ON i.id=s.item_id
                LEFT JOIN sales_customerprice p ON p.sku_id=s.id AND p.customer_id=:id ORDER BY s.id""",
                id=identifier,
            )
        if kind == "visits":
            own = not user["is_staff"] and "salesman" in user["roles"]
            return rows(
                conn,
                """SELECT v.id,c.name AS customer__name,v.route,v.note,v.visited_at,v.latitude_microdegrees,v.longitude_microdegrees
                FROM extensions_visit v JOIN inventory_customer c ON c.id=v.customer_id
                WHERE (:own=FALSE OR v.actor_id=:actor) ORDER BY v.visited_at DESC""",
                own=own,
                actor=user["id"],
            )
        if kind == "batches":
            factory_lock(conn)
            batches = rows(
                conn,
                """SELECT l.id,i.name AS item,i.category,l.code,l.expiry_date AS expiry,
                COALESCE(h.status,'released') AS quality_status,h.reason AS quality_reason,
                COALESCE(SUM(a.quantity),0)::bigint AS quantity
                FROM inventory_stocklot l JOIN inventory_item i ON i.id=l.item_id
                LEFT JOIN inventory_lotallocation a ON a.lot_id=l.id
                LEFT JOIN factory_qualityhold h ON h.lot_id=l.id
                GROUP BY l.id,i.name,i.category,h.status,h.reason ORDER BY l.expiry_date NULLS LAST,l.id""",
            )
            alerts = []
            for level in rows(
                conn,
                "SELECT r.*,i.name FROM inventory_reorderlevel r JOIN inventory_item i ON i.id=r.item_id",
            ):
                stock = available(conn, level["item_id"])
                if stock <= level["minimum_quantity"]:
                    alerts.append(
                        {
                            "item": level["name"],
                            "available": stock,
                            "minimum": level["minimum_quantity"],
                        }
                    )
            return {"lots": batches, "alerts": alerts}
        if kind == "source":
            row = dict(get_row(conn, "inventory_posting", identifier))
            result = {key.removesuffix("_id"): value for key, value in row.items()}
            sources = {
                "opening": (
                    "inventory_openingstock",
                    "inventory_openingline",
                    "document_id",
                ),
                "purchase": (
                    "inventory_purchasereceipt",
                    "inventory_purchaseline",
                    "document_id",
                ),
                "production": (
                    "production_productionevent",
                    "production_productionline",
                    "event_id",
                ),
                "dispatch": ("sales_dispatch", "sales_dispatchline", "document_id"),
                "adjustment": (
                    "inventory_adjustment",
                    "inventory_adjustmentline",
                    "document_id",
                ),
            }
            for key, (header, lines, foreign) in sources.items():
                if row[key + "_id"]:
                    result["document"] = dict(get_row(conn, header, row[key + "_id"]))
                    target = table(conn, lines)
                    result["lines"] = [
                        dict(line)
                        for line in conn.execute(
                            select(target).where(target.c[foreign] == row[key + "_id"])
                        ).mappings()
                    ]
            return result
    raise ValueError("Unknown workspace query.")
