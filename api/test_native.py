"""Runtime-only validation: run in a fresh Compose project, without Django installed."""

import importlib.util
import json
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import text
from api import database
from api.benchmark import run_benchmark
from api.seed import seed_benchmark
from api.reconciliation import reconcile
from api.production import services as production
from api.migrations.schema import signature


def test_runtime_has_no_django_dependency():
    assert importlib.util.find_spec("django") is None
    from api.main import app

    assert app.title == "Order-to-Audit API"


def test_native_benchmark_and_rollback():
    before = reconcile()
    results = run_benchmark()
    assert len(results) == 49
    assert all(row[3] for row in results), [row for row in results if not row[3]]
    assert reconcile() == before
    with database.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM inventory_posting WHERE opening_id IS NULL")
            ).scalar_one()
            == 0
        )


def test_seed_preserves_credentials_and_opening():
    with database.engine.connect() as conn:
        passwords = conn.execute(
            text("SELECT id,password FROM auth_user ORDER BY id")
        ).all()
        count = conn.execute(
            text("SELECT COUNT(*) FROM inventory_stockmovement")
        ).scalar_one()
    seed_benchmark()
    seed_benchmark()
    with database.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT id,password FROM auth_user ORDER BY id")).all()
            == passwords
        )
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM inventory_stockmovement")
            ).scalar_one()
            == count
        )


def test_schema_and_immutability_trigger():
    expected = json.loads(
        Path(__file__)
        .with_name("migrations")
        .joinpath("schema-signature.json")
        .read_text(encoding="utf-8")
    )
    with database.engine.connect() as conn:
        assert signature(conn) == expected
    from sqlalchemy.exc import DBAPIError

    for sql in [
        "UPDATE inventory_stockmovement SET quantity=quantity",
        "DELETE FROM inventory_stockmovement",
    ]:
        with pytest.raises(DBAPIError, match="immutable"):
            with database.transaction() as conn:
                conn.execute(text(sql))


def test_adoption_preserves_existing_rows_and_rejects_disabled_guard():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from importlib import import_module

    revision = import_module("api.migrations.versions.0001_existing_schema")
    before = reconcile()
    with database.transaction() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            revision.upgrade()
    assert reconcile() == before
    with pytest.raises(RuntimeError, match="incompatible triggers"):
        with database.transaction() as conn:
            conn.execute(
                text("ALTER TABLE inventory_stockmovement DISABLE TRIGGER USER")
            )
            with Operations.context(MigrationContext.configure(conn)):
                revision.upgrade()
    with database.engine.connect() as conn:
        expected = json.loads(
            Path(__file__)
            .with_name("migrations")
            .joinpath("schema-signature.json")
            .read_text(encoding="utf-8")
        )
        assert signature(conn) == expected


@pytest.mark.parametrize("mutation", ["variance", "valuation"])
def test_native_mutation_checks(mutation):
    before = reconcile()
    if mutation == "variance":

        def mutant(actual, standard, tolerance):
            ratio = Fraction(actual - standard, standard) if standard else None
            return {
                "ratio": ratio,
                "flagged": (
                    abs(ratio) * 10000 >= tolerance if ratio is not None else False
                ),
            }

        target = "variance"
        expected = "3 flags yield/oil/carton/pouch"
    else:

        def mutant(quantity, on_hand, value):
            return quantity

        target = "issue_value"
        expected = "8 materials/run paise"
    with patch.object(production, target, side_effect=mutant):
        results = run_benchmark()
    assert any(label == expected and not passed for label, _, _, passed in results)
    assert reconcile() == before
