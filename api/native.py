"""SQLAlchemy primitives for the existing PostgreSQL schema; no Django dependency."""

from datetime import datetime
from fractions import Fraction
from weakref import WeakKeyDictionary
from threading import RLock
from zoneinfo import ZoneInfo
from sqlalchemy import MetaData, Table, insert, select, update, text

_schemas = WeakKeyDictionary()
_schema_lock = RLock()


# Reflection maps the existing schema without creating tables or taking migration ownership.
def table(conn, name):
    with _schema_lock:
        metadata = _schemas.setdefault(conn.engine, MetaData())
        if name not in metadata.tables:
            Table(name, metadata, autoload_with=conn)
        return metadata.tables[name]


def insert_row(conn, table_name, **values):
    target = table(conn, table_name)
    return conn.execute(
        insert(target).values(**values).returning(target.c.id)
    ).scalar_one()


def required_integer(value, minimum=None):
    if isinstance(value, str):
        if not value or not value.lstrip("-").isdigit():
            raise ValueError("Use integer base units or paise.")
        value = int(value)
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("Integer value outside the permitted range.")
    return value


def authorize(user, roles):
    if not user["is_active"] or not (
        user["is_staff"] or set(user["roles"]) & set(roles)
    ):
        from fastapi import HTTPException

        raise HTTPException(403, "This action is not permitted for your role.")


def factory_lock(conn):
    control = table(conn, "inventory_factorycontrol")
    return (
        conn.execute(select(control).where(control.c.id == 1).with_for_update())
        .mappings()
        .one()
    )


def now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def audit(conn, user, action, source_type, source_id, before, after):
    return insert_row(
        conn,
        "access_auditlog",
        actor_id=user["id"],
        occurred_at=now(),
        action=action,
        source_type=source_type,
        source_id=source_id,
        before=before,
        after=after,
    )


# Allocate sequence and source in the caller's locked transaction, never by document date.
def posting(conn, kind, source_id):
    control = table(conn, "inventory_factorycontrol")
    sequence = conn.execute(
        update(control)
        .where(control.c.id == 1)
        .values(last_sequence=control.c.last_sequence + 1)
        .returning(control.c.last_sequence)
    ).scalar_one()
    identifier = insert_row(
        conn,
        "inventory_posting",
        sequence=sequence,
        posted_at=now(),
        **{kind + "_id": source_id},
    )
    return identifier, sequence


def round_paise(value):
    value = Fraction(value)
    whole, remainder = divmod(abs(value.numerator), value.denominator)
    return (-1 if value < 0 else 1) * (whole + (2 * remainder >= value.denominator))


def issue_value(quantity, on_hand, value):
    required_integer(quantity, 0)
    required_integer(on_hand, 0)
    if quantity > on_hand:
        raise ValueError("Insufficient stock.")
    if quantity == 0:
        return 0
    if value is None:
        raise ValueError("Unknown input valuation.")
    required_integer(value, 0)
    return (
        value
        if quantity == on_hand
        else round_paise(Fraction(value * quantity, on_hand))
    )


def balance(conn, item_id):
    row = (
        conn.execute(
            text(
                """SELECT COALESCE(SUM(quantity),0) AS quantity,
        CASE WHEN COUNT(*) FILTER(WHERE value_paise IS NULL)>0 THEN NULL
        ELSE COALESCE(SUM(value_paise),0) END AS value_paise
        FROM inventory_stockmovement WHERE item_id=:item"""
            ),
            {"item": item_id},
        )
        .mappings()
        .one()
    )
    # PostgreSQL SUM(bigint) is numeric; these sums contain only integer ledger entries.
    return int(row["quantity"]), (
        int(row["value_paise"]) if row["value_paise"] is not None else None
    )


def lots(conn, item_id):
    return (
        conn.execute(
            text(
                """SELECT l.id, l.code, l.expiry_date,
        COALESCE(SUM(a.quantity),0) AS quantity FROM inventory_stocklot l
        LEFT JOIN inventory_lotallocation a ON a.lot_id=l.id WHERE l.item_id=:item
        GROUP BY l.id ORDER BY l.expiry_date ASC NULLS LAST, l.id"""
            ),
            {"item": item_id},
        )
        .mappings()
        .all()
    )


# Every movement and its FEFO allocations are created inside the same factory transaction.
def movement(
    conn,
    *,
    posting_id,
    sequence,
    item_id,
    quantity,
    value_paise,
    source,
    source_id,
    incoming=None,
    explicit_allocations=None,
    allow_expired=False,
):
    from datetime import date

    if quantity == 0:
        raise ValueError("Zero stock movements are not permitted.")
    movement_id = insert_row(
        conn,
        "inventory_stockmovement",
        posting_id=posting_id,
        item_id=item_id,
        quantity=quantity,
        value_paise=value_paise,
        **{source + "_id": source_id},
    )
    allocations = []
    if explicit_allocations is not None:
        if sum(explicit_allocations.values()) != quantity:
            raise ValueError("Correction allocations do not match movement quantity.")
        allocations = list(explicit_allocations.items())
    elif quantity > 0:
        incoming = incoming or {}
        code = incoming.get("code") or f"POST-{sequence}"
        if not isinstance(code, str) or len(code) > 100:
            raise ValueError("Batch code must be at most 100 characters.")
        expiry = (
            date.fromisoformat(incoming["expiry"]) if incoming.get("expiry") else None
        )
        existing = next(
            (lot for lot in lots(conn, item_id) if lot["code"] == code), None
        )
        if existing:
            if existing["expiry_date"] != expiry:
                raise ValueError("An existing batch expiry cannot be changed.")
            lot_id = existing["id"]
        else:
            lot_id = insert_row(
                conn,
                "inventory_stocklot",
                item_id=item_id,
                code=code,
                expiry_date=expiry,
            )
        allocations.append((lot_id, quantity))
    else:
        remaining = -quantity
        for lot in lots(conn, item_id):
            if (
                not allow_expired
                and lot["expiry_date"]
                and lot["expiry_date"] < now().date()
            ):
                continue
            take = min(remaining, lot["quantity"])
            if take > 0:
                allocations.append((lot["id"], -take))
                remaining -= take
            if remaining == 0:
                break
        if remaining:
            raise ValueError("Insufficient non-expired batch stock.")
    current = {lot["id"]: int(lot["quantity"]) for lot in lots(conn, item_id)}
    for lot_id, signed in allocations:
        if lot_id not in current or current[lot_id] + signed < 0:
            raise ValueError(
                "Batch correction would make stock negative or use another item."
            )
        if signed:
            insert_row(
                conn,
                "inventory_lotallocation",
                movement_id=movement_id,
                lot_id=lot_id,
                quantity=int(signed),
            )
    return movement_id
