"""Native unit conversion, canonical retries and atomic rejection on a seeded database."""

from contextlib import contextmanager
from uuid import uuid4
import pytest
from sqlalchemy import text
from api import database
from api.native import balance, factory_lock
from api.services import user_by_name
from api.units.services import to_base_units
from api.inventory.services import post_receipt
from api.production.services import create_run, post_event
from api.sales.services import command
from api.masters.services import product


# Test writes share the real service connection, then roll back even after a passing assertion.
@contextmanager
def scenario():
    class Rollback(Exception):
        pass
    try:
        with database.transaction() as conn:
            factory_lock(conn)
            items = dict(conn.execute(text("SELECT code,id FROM inventory_item")).all())
            yield conn, items, user_by_name(conn, "admin")
            raise Rollback()
    except Rollback:
        pass


def test_exact_item_specific_units_and_invalid_amounts():
    with scenario() as (conn, items, user):
        assert to_base_units(conn, items["FLOUR"], "40", "kg") == 40000
        assert to_base_units(conn, items["OIL"], "10.5", "L") == 10500
        assert to_base_units(conn, items["MURUKKU200"], "2", "carton") == 40
        assert to_base_units(conn, items["MURUKKU200"], "1.5", "carton") == 30
        sku = product({"code": "TEST500", "name": "Test 500 g", "pack_size_g": 500,
                       "price_paise": 10000, "hsn": "99999999", "carton_size": 10}, user)
        item = conn.execute(text("SELECT item_id FROM inventory_sku WHERE id=:id"), {"id": sku}).scalar_one()
        assert to_base_units(conn, item, "2", "carton") == 20
        for quantity, unit in [("1", "L"), ("0.0001", "kg"), (10.5, "kg"),
                               (True, "kg"), ("NaN", "kg"), ("1e3", "kg"),
                               ("9223372036854775808", "g")]:
            with pytest.raises(ValueError):
                to_base_units(conn, items["FLOUR"], quantity, unit)


def test_receipt_retry_and_invalid_mixed_units_roll_back():
    with scenario() as (conn, items, user):
        supplier = conn.execute(text("SELECT id FROM inventory_supplier LIMIT 1")).scalar_one()
        data = {"supplier": supplier, "date": "2026-11-19", "lines": [
            {"item": items["FLOUR"], "quantity": "60", "unit": "kg", "value_paise": 270000}]}
        before = balance(conn, items["FLOUR"])
        key = str(uuid4())
        first = post_receipt(data, user, key)
        base = {**data, "lines": [{**data["lines"][0], "quantity": 60000, "unit": "g"}]}
        assert post_receipt(base, user, key) == first
        assert balance(conn, items["FLOUR"])[0] == before[0] + 60000
        snapshot = balance(conn, items["FLOUR"])
        invalid = {**data, "lines": data["lines"] + [
            {"item": items["OIL"], "quantity": "1", "unit": "kg", "value_paise": 14000}]}
        with pytest.raises(ValueError, match="Unit is not valid"):
            post_receipt(invalid, user, str(uuid4()))
        assert balance(conn, items["FLOUR"]) == snapshot


def test_production_and_order_canonical_unit_retries():
    with scenario() as (conn, items, user):
        bom = conn.execute(text("SELECT id FROM inventory_bom LIMIT 1")).scalar_one()
        run = create_run({"bom": bom, "batches": 1, "date": "2026-11-19"}, user, str(uuid4()))
        key = str(uuid4())
        before = balance(conn, items["FLOUR"])
        invalid = {"id": run, "actual": {"FLOUR": {"quantity": "40", "unit": "L"}, "OIL": 10500, "SPICE": 1200}}
        with pytest.raises(ValueError):
            post_event("issue", invalid, user, key)
        assert balance(conn, items["FLOUR"]) == before
        measured = {"id": run, "actual": {"FLOUR": {"quantity": "40", "unit": "kg"},
                    "OIL": {"quantity": "10.5", "unit": "L"}, "SPICE": 1200}}
        first = post_event("issue", measured, user, key)
        assert post_event("issue", {"id": run, "actual": {"FLOUR": 40000, "OIL": 10500, "SPICE": 1200}}, user, key) == first
        assert balance(conn, items["FLOUR"])[0] == before[0] - 40000
        sku = conn.execute(text("SELECT id FROM inventory_sku WHERE item_id=:id"), {"id": items["MURUKKU200"]}).scalar_one()
        customer = conn.execute(text("SELECT id FROM inventory_customer LIMIT 1")).scalar_one()
        order = {"customer": customer, "date": "2026-11-19", "quantities": {str(sku): {"quantity": "2", "unit": "carton"}}}
        key = str(uuid4())
        identifier = command("order.create", order, user, key)
        assert command("order.create", {**order, "quantities": {str(sku): 40}}, user, key) == identifier
        assert conn.execute(text("SELECT quantity FROM sales_orderline WHERE order_id=:id"), {"id": identifier}).scalar_one() == 40
