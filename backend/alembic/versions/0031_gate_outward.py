"""gate outward (#137 Phase 2b)

Revision ID: 0031_gate_outward
Revises: 0030_gate_inward
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0031_gate_outward'
down_revision: Union[str, Sequence[str], None] = '0030_gate_inward'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'gateoutward'):
        op.create_table('gateoutward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source_doc_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source_doc_id', sa.Integer(), nullable=True),
        sa.Column('gate_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('time_out', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('vehicle_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('challan_no', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('remarks', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('draft','approved','cancelled')", name='ck_go_status'),
        sa.CheckConstraint("source_doc_type IN ('invoice','debit_note','scrap')", name='ck_go_source_doc_type'),
        sa.ForeignKeyConstraint(['approved_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_go_number_per_tenant')
        )
        op.create_index(op.f('ix_gateoutward_number'), 'gateoutward', ['number'], unique=False)
        op.create_index(op.f('ix_gateoutward_tenant_id'), 'gateoutward', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'gateoutwardline'):
        op.create_table('gateoutwardline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gate_outward_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint('qty > 0', name='ck_go_line_qty_positive'),
        sa.ForeignKeyConstraint(['gate_outward_id'], ['gateoutward.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_gateoutwardline_gate_outward_id'), 'gateoutwardline', ['gate_outward_id'], unique=False)


def downgrade() -> None:
    op.drop_table('gateoutwardline')
    op.drop_table('gateoutward')
