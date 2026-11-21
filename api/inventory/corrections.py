"""Reasoned stock adjustments and exact production reversals, without ORM writes."""

from datetime import date
from sqlalchemy import select, text
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
)
from api.sales.services import get_row, change, available


# Returns and reversals share the same typed adjustment source and atomic ledger writer.
def append_adjustment(conn, source_id, lines, payload, user, reversed_run=None):
    posting_id, sequence = posting(conn, "adjustment", source_id)
    for item, quantity, value in lines:
        line = insert_row(
            conn,
            "inventory_adjustmentline",
            document_id=source_id,
            item_id=item,
            quantity=quantity,
            value_paise=value,
        )
        allocations = None
        if reversed_run:
            rows = (
                conn.execute(
                    text(
                        """SELECT a.lot_id,-SUM(a.quantity) AS quantity FROM inventory_lotallocation a
                JOIN inventory_stockmovement m ON m.id=a.movement_id JOIN inventory_posting p ON p.id=m.posting_id
                JOIN production_productionevent e ON e.id=p.production_id WHERE e.run_id=:run AND m.item_id=:item
                GROUP BY a.lot_id"""
                    ),
                    {"run": reversed_run, "item": item},
                )
                .mappings()
                .all()
            )
            allocations = {row["lot_id"]: int(row["quantity"]) for row in rows}
        incoming = None
        if "invoice" in payload and quantity > 0:
            expiry = conn.execute(
                text(
                    """SELECT MIN(l.expiry_date) FROM inventory_stocklot l
                JOIN inventory_lotallocation a ON a.lot_id=l.id JOIN inventory_stockmovement m ON m.id=a.movement_id
                JOIN sales_dispatchline dl ON dl.id=m.dispatch_line_id JOIN sales_dispatch d ON d.id=dl.document_id
                WHERE d.invoice_id=:invoice AND l.item_id=:item"""
                ),
                {"invoice": payload["invoice"], "item": item},
            ).scalar_one()
            incoming = {
                "code": f"RETURN-{source_id}",
                "expiry": str(expiry) if expiry else None,
            }
        movement(
            conn,
            posting_id=posting_id,
            sequence=sequence,
            item_id=item,
            quantity=quantity,
            value_paise=value,
            source="adjustment_line",
            source_id=line,
            incoming=incoming,
            explicit_allocations=allocations,
            allow_expired=True,
        )
    audit(conn, user, "stock.adjust", "inventory.Adjustment", source_id, {}, payload)
    return posting_id


def command(action, data, user, key):
    authorize(user, ["admin"])
    reason = data["reason"]
    day = date.fromisoformat(data["date"])
    if not key or not reason.strip():
        raise ValueError("Correction reason and request key required.")
    with database.transaction() as conn:
        factory_lock(conn)
        if action == "adjustment":
            item = get_row(conn, "inventory_item", data["item"])
            quantity = required_integer(data["quantity"])
            if not quantity:
                raise ValueError("Nonzero adjustment quantity required.")
            supplied = (
                required_integer(data["value_paise"], 0)
                if data.get("value_paise") not in (None, "")
                else None
            )
            payload = {
                "item": item["id"],
                "quantity": quantity,
                "value_paise": supplied,
                "reason": reason,
                "date": str(day),
            }
            run = None
        else:
            run = get_row(conn, "production_productionrun", data["id"])
            payload = {"run": run["id"], "reason": reason, "date": str(day)}
        adjustments = table(conn, "inventory_adjustment")
        old = (
            conn.execute(select(adjustments).where(adjustments.c.request_key == key))
            .mappings()
            .first()
        )
        if old:
            if old["payload"] != payload or old["actor_id"] != user["id"]:
                raise ValueError("Conflicting correction retry.")
            postings = table(conn, "inventory_posting")
            return conn.execute(
                select(postings.c.id).where(postings.c.adjustment_id == old["id"])
            ).scalar_one()
        if run:
            if run["state"] not in ("issued", "completed"):
                raise ValueError("Only issued or completed runs can be reversed.")
            rows = (
                conn.execute(
                    text(
                        """SELECT m.*,p.sequence FROM inventory_stockmovement m
                JOIN inventory_posting p ON p.id=m.posting_id JOIN production_productionevent e ON e.id=p.production_id
                WHERE e.run_id=:run"""
                    ),
                    {"run": run["id"]},
                )
                .mappings()
                .all()
            )
            if not rows:
                raise ValueError("Run has no stock postings.")
            first = min(row["sequence"] for row in rows)
            items = list({row["item_id"] for row in rows})
            later = conn.execute(
                text(
                    """SELECT m.id FROM inventory_stockmovement m JOIN inventory_posting p ON p.id=m.posting_id
                LEFT JOIN production_productionevent e ON e.id=p.production_id WHERE m.item_id=ANY(:items)
                AND p.sequence>:first AND e.run_id IS DISTINCT FROM :run LIMIT 1"""
                ),
                {"items": items, "first": first, "run": run["id"]},
            ).first()
            if later:
                raise ValueError(
                    "A later or intervening stock event depends on this run."
                )
            for row in rows:
                if (
                    row["quantity"] > 0
                    and available(conn, row["item_id"]) < row["quantity"]
                ):
                    raise ValueError(
                        "Reversal would consume reserved or unavailable finished goods."
                    )
            lines = [
                (row["item_id"], -row["quantity"], -row["value_paise"]) for row in rows
            ]
        else:
            on_hand, value = balance(conn, item["id"])
            if quantity < 0:
                if supplied is not None:
                    raise ValueError("Negative adjustments calculate their own value.")
                expired = int(
                    conn.execute(
                        text(
                            """SELECT COALESCE(SUM(a.quantity),0) FROM inventory_lotallocation a
                    JOIN inventory_stocklot l ON l.id=a.lot_id WHERE l.item_id=:item AND l.expiry_date<:today"""
                        ),
                        {"item": item["id"], "today": now().date()},
                    ).scalar_one()
                )
                if -quantity > available(conn, item["id"]) + expired:
                    raise ValueError("Adjustment would consume reserved stock.")
                value = (
                    None if value is None else -issue_value(-quantity, on_hand, value)
                )
            else:
                value = required_integer(supplied, 0)
            lines = [(item["id"], quantity, value)]
        source = insert_row(
            conn,
            "inventory_adjustment",
            reason=reason,
            payload=payload,
            request_key=key,
            document_date=day,
            actor_id=user["id"],
            reversed_run_id=run["id"] if run else None,
        )
        identifier = append_adjustment(
            conn, source, lines, payload, user, run["id"] if run else None
        )
        if run:
            change(conn, "production_productionrun", run["id"], state="reversed")
            audit(
                conn,
                user,
                "run.reverse",
                "production.ProductionRun",
                run["id"],
                {"state": run["state"]},
                {"state": "reversed", "reason": reason},
            )
        return identifier
