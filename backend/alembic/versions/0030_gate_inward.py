"""gate inward (#137 Phase 2)

Revision ID: 0030_gate_inward
Revises: 0029_purchase_demand_comparative
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0030_gate_inward'
down_revision: Union[str, Sequence[str], None] = '0029_purchase_demand_comparative'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'gateinward'):
        op.create_table('gateinward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('po_id', sa.Integer(), nullable=False),
        sa.Column('gate_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('time_in', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('vehicle_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('challan_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('remarks', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('cancel_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('open','billed','cancelled')", name='ck_gi_status'),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchaseorder.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_gi_number_per_tenant')
        )
        op.create_index(op.f('ix_gateinward_number'), 'gateinward', ['number'], unique=False)
        op.create_index(op.f('ix_gateinward_po_id'), 'gateinward', ['po_id'], unique=False)
        op.create_index(op.f('ix_gateinward_tenant_id'), 'gateinward', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'gateinwardline'):
        op.create_table('gateinwardline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gate_inward_id', sa.Integer(), nullable=False),
        sa.Column('po_line_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('qty_received', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint('qty_received > 0', name='ck_gi_line_qty_positive'),
        sa.ForeignKeyConstraint(['gate_inward_id'], ['gateinward.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['po_line_id'], ['purchaseorderline.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_gateinwardline_gate_inward_id'), 'gateinwardline', ['gate_inward_id'], unique=False)


def downgrade() -> None:
    op.drop_table('gateinwardline')
    op.drop_table('gateinward')
