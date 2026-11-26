"""Remove the unused Django session store after verifying it has no dependants."""
from alembic import op
import sqlalchemy as sa

revision = "0004_drop_unused_django_session"
down_revision = "0003_operator_setup"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "django_session" not in inspector.get_table_names(schema="public"):
        return

    # Refuse to drop a table if a later schema change has made it a dependency target.
    dependants = []
    for table_name in inspector.get_table_names(schema="public"):
        for foreign_key in inspector.get_foreign_keys(table_name, schema="public"):
            if foreign_key.get("referred_table") == "django_session":
                dependants.append(table_name)
    if dependants:
        raise RuntimeError(
            "Refusing to drop django_session; incoming foreign keys from: "
            + ", ".join(sorted(set(dependants)))
        )

    # The active FastAPI runtime uses signed bearer tokens, not Django sessions.
    op.drop_table("django_session", schema="public")


def downgrade():
    # Django sessions were verified empty; downgrade restores schema, not session data.
    op.create_table(
        "django_session",
        sa.Column("session_key", sa.String(length=40), nullable=False),
        sa.Column("session_data", sa.Text(), nullable=False),
        sa.Column("expire_date", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_key", name="django_session_pkey"),
        schema="public",
    )
    op.create_index(
        "django_session_expire_date_a5c62663",
        "django_session",
        ["expire_date"],
        schema="public",
    )
    op.create_index(
        "django_session_session_key_c0390e0f_like",
        "django_session",
        [sa.text("session_key varchar_pattern_ops")],
        schema="public",
    )
