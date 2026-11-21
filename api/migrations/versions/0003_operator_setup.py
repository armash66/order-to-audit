"""Account setup and durable sign-in throttling for the local product workspace."""
from alembic import op
import sqlalchemy as sa

revision = "0003_operator_setup"
down_revision = "0002_factory_actions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "factory_accountsecurity",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("auth_user.id"), primary_key=True),
        sa.Column("must_change_password", sa.Boolean, nullable=False),
    )
    op.create_table(
        "factory_loginattempt",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("failures", sa.Integer, nullable=False),
        sa.Column("last_attempt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("factory_loginattempt")
    op.drop_table("factory_accountsecurity")
