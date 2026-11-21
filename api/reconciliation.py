"""Independent source-document and batch reconciliation for the immutable ledger."""

from sqlalchemy import text
from api import database
from api.native import factory_lock, balance
from api.queries import rows


def reconcile():
    with database.transaction() as conn:
        factory_lock(conn)
        sources = {
            "opening": ("inventory_openingline", "document_id"),
            "purchase": ("inventory_purchaseline", "document_id"),
            "production": ("production_productionline", "event_id"),
            "dispatch": ("sales_dispatchline", "document_id"),
            "adjustment": ("inventory_adjustmentline", "document_id"),
        }
        expected = []
        for kind, (name, foreign) in sources.items():
            # Names are fixed internal identifiers; only posted source lines belong in the ledger.
            expected.extend(
                rows(
                    conn,
                    f"""SELECT p.id AS posting_id,l.id AS source_id,l.item_id,l.quantity,l.value_paise,
                '{kind}' AS kind FROM {name} l JOIN inventory_posting p ON p.{kind}_id=l.{foreign} WHERE l.quantity<>0""",
                )
            )
        actual = rows(
            conn,
            """SELECT posting_id,COALESCE(opening_line_id,purchase_line_id,production_line_id,dispatch_line_id,adjustment_line_id) AS source_id,
            item_id,quantity,value_paise,CASE WHEN opening_line_id IS NOT NULL THEN 'opening' WHEN purchase_line_id IS NOT NULL THEN 'purchase'
            WHEN production_line_id IS NOT NULL THEN 'production' WHEN dispatch_line_id IS NOT NULL THEN 'dispatch' ELSE 'adjustment' END AS kind
            FROM inventory_stockmovement""",
        )
        key = lambda row: (row["kind"], row["source_id"])
        if sorted(actual, key=key) != sorted(expected, key=key):
            raise ValueError("Posted source lines disagree with stock movements.")
        invalid = conn.execute(
            text(
                """SELECT m.id FROM inventory_stockmovement m LEFT JOIN inventory_lotallocation a ON a.movement_id=m.id
            LEFT JOIN inventory_stocklot l ON l.id=a.lot_id GROUP BY m.id HAVING COALESCE(SUM(a.quantity),0)<>m.quantity
            OR COUNT(*) FILTER(WHERE l.item_id<>m.item_id)>0 LIMIT 1"""
            )
        ).first()
        if invalid:
            raise ValueError("Batch allocations disagree with the stock ledger.")
        if conn.execute(
            text(
                "SELECT lot_id FROM inventory_lotallocation GROUP BY lot_id HAVING SUM(quantity)<0 LIMIT 1"
            )
        ).first():
            raise ValueError("Negative batch stock.")
        if conn.execute(
            text(
                """SELECT id FROM (SELECT m.id,SUM(m.quantity) OVER(PARTITION BY m.item_id ORDER BY p.sequence,m.id) AS quantity
            FROM inventory_stockmovement m JOIN inventory_posting p ON p.id=m.posting_id) history WHERE quantity<0 LIMIT 1"""
            )
        ).first():
            raise ValueError("Negative historical stock.")
        result = {}
        for item in rows(conn, "SELECT * FROM inventory_item ORDER BY id"):
            lines = [line for line in expected if line["item_id"] == item["id"]]
            quantity = sum(line["quantity"] for line in lines)
            value = (
                None
                if any(line["value_paise"] is None for line in lines)
                else sum(line["value_paise"] for line in lines)
            )
            if (quantity, value) != balance(conn, item["id"]):
                raise ValueError("Source totals disagree with reported stock.")
            result[item["code"]] = {"quantity": quantity, "value_paise": value}
            if item["category"] == "finished":
                result[item["code"]]["valuation_basis"] = "materials-only"
        return result
