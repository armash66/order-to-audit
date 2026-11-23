"""Native SQLAlchemy production writer; standards and ledger sources retain their schema."""

from datetime import date
from fractions import Fraction
from contextlib import nullcontext
from sqlalchemy import select, update, text
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
    issue_value,
    balance,
    audit,
    now,
    round_paise,
)


def get_run(conn, identifier):
    model = table(conn, "production_productionrun")
    run = (
        conn.execute(select(model).where(model.c.id == required_integer(identifier, 1)))
        .mappings()
        .first()
    )
    if run is None:
        raise ValueError("Production run not found.")
    return run


# Snapshot recipe/version and SKU packaging standards atomically under the factory lock.
def create_run(data, user, key):
    authorize(user, ["admin", "production"])
    if not key:
        raise ValueError("Request key is required.")
    batches = required_integer(data["batches"], 1)
    bom_id = required_integer(data["bom"], 1)
    day = date.fromisoformat(data["date"])
    expiry = date.fromisoformat(data["expiry"]) if data.get("expiry") else None
    with database.transaction() as conn:
        factory_lock(conn)
        runs = table(conn, "production_productionrun")
        old = (
            conn.execute(select(runs).where(runs.c.request_key == key))
            .mappings()
            .first()
        )
        if old:
            if (
                old["bom_id"],
                old["batches"],
                old["document_date"],
                old["actor_id"],
                old["output_expiry"],
            ) != (bom_id, batches, day, user["id"], expiry):
                raise ValueError("Run request key reused with different content.")
            return old["id"]
        bom = (
            conn.execute(
                text(
                    """SELECT b.*, r.version AS recipe_version, s.item_id, i.category, i.base_unit
            FROM inventory_bom b JOIN inventory_recipe r ON r.id=b.recipe_id
            JOIN inventory_sku s ON s.id=b.sku_id JOIN inventory_item i ON i.id=s.item_id
            WHERE b.id=:id"""
                ),
                {"id": bom_id},
            )
            .mappings()
            .first()
        )
        if not bom or bom["category"] != "finished" or bom["base_unit"] != "piece":
            raise ValueError("Output must be a finished-goods piece item.")
        required_integer(bom["expected_packets"], 1)
        raw = (
            conn.execute(
                text(
                    """SELECT l.item_id,l.quantity,i.category FROM inventory_recipeline l
            JOIN inventory_item i ON i.id=l.item_id WHERE l.recipe_id=:id"""
                ),
                {"id": bom["recipe_id"]},
            )
            .mappings()
            .all()
        )
        packaging = (
            conn.execute(
                text(
                    """SELECT l.item_id,l.quantity,i.category FROM inventory_bomline l
            JOIN inventory_item i ON i.id=l.item_id WHERE l.bom_id=:id"""
                ),
                {"id": bom_id},
            )
            .mappings()
            .all()
        )
        if not raw:
            raise ValueError("Recipe needs at least one raw ingredient.")
        identifier = insert_row(
            conn,
            "production_productionrun",
            request_key=key,
            document_date=day,
            actor_id=user["id"],
            bom_id=bom_id,
            bom_version=bom["version"],
            recipe_version=bom["recipe_version"],
            batches=batches,
            expected_packets=bom["expected_packets"] * batches,
            output_item_id=bom["item_id"],
            state="draft",
            good_packets=None,
            output_expiry=expiry,
        )
        for stage, lines in [("raw", raw), ("packaging", packaging)]:
            for line in lines:
                if line["category"] != stage:
                    raise ValueError("BOM stage does not match item category.")
                quantity = required_integer(line["quantity"], 1) * batches
                insert_row(
                    conn,
                    "production_runstandard",
                    run_id=identifier,
                    item_id=line["item_id"],
                    stage=stage,
                    quantity=quantity,
                )
        audit(
            conn,
            user,
            "run.create",
            "production.ProductionRun",
            identifier,
            {},
            {"batches": batches, "expected_packets": bom["expected_packets"] * batches},
        )
        return identifier


# Source lines include zero consumption; immutable movements never contain zero quantities.
def append_line(conn, run, event_id, posting_id, sequence, item_id, quantity, value):
    line_id = insert_row(
        conn,
        "production_productionline",
        event_id=event_id,
        item_id=item_id,
        quantity=quantity,
        value_paise=value,
    )
    if quantity:
        incoming = (
            {
                "code": f"RUN-{run['id']}",
                "expiry": (
                    run["output_expiry"].isoformat() if run["output_expiry"] else None
                ),
            }
            if quantity > 0
            else None
        )
        movement(
            conn,
            posting_id=posting_id,
            sequence=sequence,
            item_id=item_id,
            quantity=quantity,
            value_paise=value,
            source="production_line",
            source_id=line_id,
            incoming=incoming,
        )


# Convert measured inputs within the posting transaction, keeping snapshots in base units.
def post_event(kind, data, user, key):
    authorize(user, ["admin", "production"])
    with database.transaction() as conn:
        factory_lock(conn)
        items = table(conn, "inventory_item")
        normalized = dict(data)
        for name in ("actual", "damaged"):
            values = data.get(name, {})
            if not isinstance(values, dict):
                raise ValueError("Actual and damaged inputs must be quantity maps.")
            normalized[name] = {}
            for code, value in values.items():
                item_id = conn.execute(select(items.c.id).where(items.c.code == code)).scalar_one_or_none()
                if item_id is None:
                    raise ValueError("Item not found.")
                normalized[name][code] = to_base_units(conn, item_id, value)
        return _post_event_base(kind, normalized, user, key)


# Issue and completion are separate sources; both preserve request-key and payload retry semantics.
def _post_event_base(kind, data, user, key):
    authorize(user, ["admin", "production"])
    if kind not in ("issue", "complete") or not key:
        raise ValueError("Invalid production event.")
    if not isinstance(data.get("actual"), dict) or not isinstance(
        data.get("damaged", {}), dict
    ):
        raise ValueError("Actual and damaged inputs must be quantity maps.")
    actual = {
        code: required_integer(value, 0) for code, value in data["actual"].items()
    }
    damaged = {
        code: required_integer(value, 0)
        for code, value in data.get("damaged", {}).items()
    }
    good = required_integer(data["good_packets"], 0) if kind == "complete" else None
    if kind == "issue" and (damaged or data.get("good_packets") is not None):
        raise ValueError("Output and packaging damage belong to completion.")
    if any(
        code not in actual or quantity > actual[code]
        for code, quantity in damaged.items()
    ):
        raise ValueError("Damage must be included in actual packaging issue.")
    payload = {"actual": actual, "good_packets": good, "damaged": damaged}
    with database.transaction() as conn:
        factory_lock(conn)
        run = get_run(conn, data["id"])
        events = table(conn, "production_productionevent")
        old = (
            conn.execute(
                select(events).where(
                    events.c.run_id == run["id"], events.c.kind == kind
                )
            )
            .mappings()
            .first()
        )
        if old:
            if (old["request_key"], old["payload"], old["actor_id"]) != (
                key,
                payload,
                user["id"],
            ):
                raise ValueError("Event already posted with different content or key.")
            postings = table(conn, "inventory_posting")
            return conn.execute(
                select(postings.c.id).where(postings.c.production_id == old["id"])
            ).scalar_one()
        if conn.execute(select(events.c.id).where(events.c.request_key == key)).first():
            raise ValueError("Event request key already used.")
        if run["state"] != ("draft" if kind == "issue" else "issued"):
            raise ValueError("Invalid production transition.")
        standards = (
            conn.execute(
                text(
                    """SELECT s.item_id,i.code FROM production_runstandard s
            JOIN inventory_item i ON i.id=s.item_id WHERE s.run_id=:run AND s.stage=:stage"""
                ),
                {"run": run["id"], "stage": "raw" if kind == "issue" else "packaging"},
            )
            .mappings()
            .all()
        )
        if set(actual) != {row["code"] for row in standards}:
            raise ValueError(
                "Supply actual quantities for exactly the snapshotted inputs."
            )
        issues = []
        for row in standards:
            quantity = actual[row["code"]]
            on_hand, value = balance(conn, row["item_id"])
            issues.append(
                (row["item_id"], quantity, issue_value(quantity, on_hand, value))
            )
        event_id = insert_row(
            conn,
            "production_productionevent",
            request_key=key,
            document_date=run["document_date"],
            actor_id=user["id"],
            run_id=run["id"],
            kind=kind,
            payload=payload,
        )
        posting_id, sequence = posting(conn, "production", event_id)
        for item_id, quantity, value in issues:
            append_line(
                conn, run, event_id, posting_id, sequence, item_id, -quantity, -value
            )
        if kind == "complete":
            raw_value = conn.execute(
                text(
                    """SELECT -COALESCE(SUM(l.value_paise),0) FROM production_productionline l
                JOIN production_productionevent e ON e.id=l.event_id WHERE e.run_id=:run AND e.kind='issue' """
                ),
                {"run": run["id"]},
            ).scalar_one()
            if good:
                append_line(
                    conn,
                    run,
                    event_id,
                    posting_id,
                    sequence,
                    run["output_item_id"],
                    good,
                    int(raw_value) + sum(value for _, _, value in issues),
                )
        audit(
            conn,
            user,
            "run." + kind,
            "production.ProductionRun",
            run["id"],
            {"state": run["state"]},
            payload,
        )
        runs = table(conn, "production_productionrun")
        conn.execute(
            update(runs)
            .where(runs.c.id == run["id"])
            .values(
                state="issued" if kind == "issue" else "completed", good_packets=good
            )
        )
        return posting_id


def add_overhead(data, user, key):
    authorize(user, ["admin"])
    amount = required_integer(data["amount_paise"], 1)
    if not data["label"].strip() or not key:
        raise ValueError("Label and key are required.")
    with database.transaction() as conn:
        factory_lock(conn)
        run = get_run(conn, data["id"])
        if run["state"] != "completed":
            raise ValueError("Complete the run before adding overhead.")
        values = {
            "run_id": run["id"],
            "actor_id": user["id"],
            "document_date": date.fromisoformat(data["date"]),
            "label": data["label"],
            "amount_paise": amount,
        }
        overhead = table(conn, "production_overhead")
        old = (
            conn.execute(select(overhead).where(overhead.c.request_key == key))
            .mappings()
            .first()
        )
        if old:
            if any(old[field] != value for field, value in values.items()):
                raise ValueError("Overhead request key reused with different content.")
            return old["id"]
        return insert_row(
            conn, "production_overhead", request_key=key, posted_at=now(), **values
        )


def edit_run(data, user):
    authorize(user, ["admin", "production"])
    batches = required_integer(data["batches"], 1)
    with database.transaction() as conn:
        factory_lock(conn)
        run = get_run(conn, data["id"])
        if run["state"] != "draft":
            raise ValueError("Only draft runs can be edited.")
        standards = table(conn, "production_runstandard")
        for row in (
            conn.execute(select(standards).where(standards.c.run_id == run["id"]))
            .mappings()
            .all()
        ):
            conn.execute(
                update(standards)
                .where(standards.c.id == row["id"])
                .values(quantity=row["quantity"] // run["batches"] * batches)
            )
        output = run["expected_packets"] // run["batches"] * batches
        runs = table(conn, "production_productionrun")
        conn.execute(
            update(runs)
            .where(runs.c.id == run["id"])
            .values(batches=batches, expected_packets=output)
        )
        audit(
            conn,
            user,
            "run.edit",
            "production.ProductionRun",
            run["id"],
            {"batches": run["batches"], "expected_packets": run["expected_packets"]},
            {"batches": batches, "expected_packets": output},
        )
        return run["id"]


def set_tolerance(data, user):
    authorize(user, ["admin"])
    tolerance = required_integer(data["basis_points"], 0)
    if tolerance > 10000:
        raise ValueError("Tolerance must be between 0 and 100 percent.")
    with database.transaction() as conn:
        control = factory_lock(conn)
        if control["tolerance_bps"] != tolerance:
            insert_row(
                conn,
                "production_tolerancechange",
                actor_id=user["id"],
                before_bps=control["tolerance_bps"],
                after_bps=tolerance,
                changed_at=now(),
            )
            target = table(conn, "inventory_factorycontrol")
            conn.execute(
                update(target).where(target.c.id == 1).values(tolerance_bps=tolerance)
            )
    return tolerance


# Fractions preserve equality at the tolerance boundary without percentage rounding.
def variance(actual, standard, tolerance):
    required_integer(actual, 0)
    required_integer(standard, 0)
    required_integer(tolerance, 0)
    ratio = Fraction(actual - standard, standard) if standard else None
    return {
        "ratio": ratio,
        "flagged": abs(ratio) * 10000 > tolerance if ratio is not None else False,
    }


# The factory lock gives one consistent view of inputs, output, overheads and current tolerance.
def run_report(identifier, user, connection=None):
    authorize(user, ["admin", "production", "accountant", "owner"])
    with (
        nullcontext(connection) if connection is not None else database.transaction()
    ) as conn:
        control = factory_lock(conn)
        run = get_run(conn, identifier)
        rows = (
            conn.execute(
                text(
                    """SELECT i.code,l.quantity,l.value_paise FROM production_productionline l
            JOIN production_productionevent e ON e.id=l.event_id JOIN inventory_item i ON i.id=l.item_id
            WHERE e.run_id=:id AND l.item_id<>:output"""
                ),
                {"id": run["id"], "output": run["output_item_id"]},
            )
            .mappings()
            .all()
        )
        actual = {row["code"]: -row["quantity"] for row in rows}
        materials = -sum(row["value_paise"] for row in rows)
        standards = (
            conn.execute(
                text(
                    """SELECT i.code,s.quantity FROM production_runstandard s
            JOIN inventory_item i ON i.id=s.item_id WHERE s.run_id=:id"""
                ),
                {"id": run["id"]},
            )
            .mappings()
            .all()
        )
        consumption = {
            row["code"]: {
                "planned": row["quantity"],
                "actual": actual.get(row["code"]),
                **(
                    variance(
                        actual[row["code"]], row["quantity"], control["tolerance_bps"]
                    )
                    if row["code"] in actual
                    else {"ratio": None, "flagged": False}
                ),
            }
            for row in standards
        }
        overhead = int(
            conn.execute(
                text(
                    "SELECT COALESCE(SUM(amount_paise),0) FROM production_overhead WHERE run_id=:id"
                ),
                {"id": run["id"]},
            ).scalar_one()
        )
        if run["state"] == "reversed":
            materials = overhead = 0
        total = materials + overhead
        good = run["good_packets"]
        cost = Fraction(total, good) if good else None
        price = conn.execute(
            text(
                "SELECT s.price_paise FROM inventory_bom b JOIN inventory_sku s ON s.id=b.sku_id WHERE b.id=:id"
            ),
            {"id": run["bom_id"]},
        ).scalar_one()
        complete = conn.execute(
            text(
                "SELECT payload FROM production_productionevent WHERE run_id=:id AND kind='complete'"
            ),
            {"id": run["id"]},
        ).scalar_one_or_none()
        return {
            "state": run["state"],
            "consumption": consumption,
            "tolerance_bps": control["tolerance_bps"],
            "expected_packets": run["expected_packets"],
            "good_packets": good,
            "yield": (
                variance(good, run["expected_packets"], control["tolerance_bps"])
                if good is not None
                else {"ratio": None, "flagged": False}
            ),
            "unclassified_shortfall": (
                max(0, run["expected_packets"] - good) if good is not None else None
            ),
            "damaged_packaging": complete["damaged"] if complete else {},
            "materials_paise": materials,
            "overhead_paise": overhead,
            "total_paise": total,
            "margin_paise": price - cost if cost is not None else None,
            "cost_per_packet_paise": cost,
            "display_cost_paise": round_paise(cost) if cost is not None else None,
            "fg_valuation_basis": "materials-only",
        }
