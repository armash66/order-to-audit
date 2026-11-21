"""Add quality decisions, production loss notes and collection follow-ups."""
from alembic import op
import sqlalchemy as sa

revision = '0002_factory_actions'
down_revision = '0001_existing_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('factory_qualityhold',
        sa.Column('id',sa.BigInteger,primary_key=True),
        sa.Column('lot_id',sa.BigInteger,sa.ForeignKey('inventory_stocklot.id'),nullable=False,unique=True),
        sa.Column('status',sa.String(12),nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('auth_user.id'),nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("status IN ('held','released')",name='quality_status_valid'))
    op.create_table('factory_lossnote',
        sa.Column('id',sa.BigInteger,primary_key=True),
        sa.Column('run_id',sa.BigInteger,sa.ForeignKey('production_productionrun.id'),nullable=False),
        sa.Column('reason',sa.String(100),nullable=False),
        sa.Column('note',sa.Text,nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('auth_user.id'),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False,unique=True))
    op.create_table('factory_collectionfollowup',
        sa.Column('id',sa.BigInteger,primary_key=True),
        sa.Column('invoice_id',sa.BigInteger,sa.ForeignKey('sales_invoice.id'),nullable=False),
        sa.Column('note',sa.Text,nullable=False),
        sa.Column('next_contact',sa.Date,nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('auth_user.id'),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False,unique=True))


def downgrade():
    op.drop_table('factory_collectionfollowup')
    op.drop_table('factory_lossnote')
    op.drop_table('factory_qualityhold')
