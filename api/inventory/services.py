"""Native SQLAlchemy receipt posting against the unchanged ledger schema."""

from datetime import date
from sqlalchemy import select
from api import database
from api.units.services import to_base_units
from api.native import (
    authorize,
    required_integer,
    factory_lock,
    table,
    insert_row,
    posting,
    movement,
)


# Normalize before posting under the same lock; equivalent units have identical retry payloads.
def post_receipt(data, user, request_key, kind="purchase"):
    authorize(user, ["admin", "production"] if kind == "purchase" else ["admin"])
    with database.transaction() as conn:
        factory_lock(conn)
        lines = [{**row, "quantity": to_base_units(
            conn, row["item"], row["quantity"], row.get("unit")
        )} for row in data["lines"]]
        return _post_receipt_base({**data, "lines": lines}, user, request_key, kind)


# Retry comparison occurs under the same database lock as source creation and posting.
def _post_receipt_base(data, user, request_key, kind="purchase"):
    if kind not in ("purchase", "opening"):
        raise ValueError("Unknown receipt type.")
    authorize(user, ["admin", "production"] if kind == "purchase" else ["admin"])
    day = date.fromisoformat(data["date"])
    supplier_id = required_integer(data["supplier"], 1) if kind == "purchase" else None
    details = data.get("lots") or {}
    lines = sorted(
        (
            required_integer(row["item"], 1),
            required_integer(row["quantity"], 1),
            (
                None
                if kind == "opening" and row["value_paise"] is None
                else required_integer(row["value_paise"], 0)
            ),
        )
        for row in data["lines"]
    )
    if not request_key or not lines or len({line[0] for line in lines}) != len(lines):
        raise ValueError("Receipt needs a key and distinct nonempty item lines.")
    with database.transaction() as conn:
        factory_lock(conn)
        supplier = table(conn, "inventory_supplier")
        if (
            kind == "purchase"
            and conn.execute(
                select(supplier.c.id).where(supplier.c.id == supplier_id)
            ).first()
            is None
        ):
            raise ValueError("Supplier not found.")
        items = table(conn, "inventory_item")
        rows = (
            conn.execute(
                select(items).where(items.c.id.in_([line[0] for line in lines]))
            )
            .mappings()
            .all()
        )
        if len(rows) != len(lines) or set(details) - {row["code"] for row in rows}:
            raise ValueError("Receipt item or batch metadata is invalid.")
        codes = {row["id"]: row["code"] for row in rows}
        header_name = (
            "inventory_purchasereceipt"
            if kind == "purchase"
            else "inventory_openingstock"
        )
        line_name = (
            "inventory_purchaseline" if kind == "purchase" else "inventory_openingline"
        )
        header = table(conn, header_name)
        line_table = table(conn, line_name)
        old = (
            conn.execute(select(header).where(header.c.request_key == request_key))
            .mappings()
            .first()
        )
        if old:
            previous = conn.execute(
                select(
                    line_table.c.item_id,
                    line_table.c.quantity,
                    line_table.c.value_paise,
                )
                .where(line_table.c.document_id == old["id"])
                .order_by(line_table.c.item_id)
            ).all()
            if (
                list(map(tuple, previous)) != lines
                or old["document_date"] != day
                or old["actor_id"] != user["id"]
                or (kind == "purchase" and old["supplier_id"] != supplier_id)
                or old["lot_details"] != details
            ):
                raise ValueError("Request key already used with different content.")
            postings = table(conn, "inventory_posting")
            return conn.execute(
                select(postings.c.id).where(postings.c[kind + "_id"] == old["id"])
            ).scalar_one()
        extra = {"supplier_id": supplier_id} if kind == "purchase" else {}
        source_id = insert_row(
            conn,
            header_name,
            request_key=request_key,
            document_date=day,
            actor_id=user["id"],
            lot_details=details,
            **extra
        )
        posting_id, sequence = posting(conn, kind, source_id)
        for item_id, quantity, value in lines:
            line_id = insert_row(
                conn,
                line_name,
                document_id=source_id,
                item_id=item_id,
                quantity=quantity,
                value_paise=value,
            )
            movement(
                conn,
                posting_id=posting_id,
                sequence=sequence,
                item_id=item_id,
                quantity=quantity,
                value_paise=value,
                source=kind + "_line",
                source_id=line_id,
                incoming=details.get(codes[item_id]),
            )
        return posting_id
