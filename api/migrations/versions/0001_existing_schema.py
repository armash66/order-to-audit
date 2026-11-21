"""Adopt the existing schema or create an identical empty database; never rewrite data."""

import json
from pathlib import Path
from alembic import op
from sqlalchemy import inspect
from api.migrations.schema import signature

revision = "0001_existing_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    directory = Path(__file__).resolve().parents[1]
    existing = set(inspect(conn).get_table_names(schema="public")) - {"alembic_version"}
    if not existing:
        conn.exec_driver_sql(
            directory.joinpath("schema.sql").read_text(encoding="utf-8")
        )
        conn.exec_driver_sql("SET search_path TO public")
    expected = json.loads(
        directory.joinpath("schema-signature.json").read_text(encoding="utf-8")
    )
    actual = signature(conn)
    if actual != expected:
        differences = [key for key in expected if actual[key] != expected[key]]
        raise RuntimeError(
            "Schema adoption refused: incompatible "
            + ", ".join(differences)
            + ". No data was changed."
        )


def downgrade():
    raise RuntimeError(
        "This adoption revision cannot drop an existing factory database."
    )
