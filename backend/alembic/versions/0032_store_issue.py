"""store issue (#137 Phase 3)

Revision ID: 0032_store_issue
Revises: 0031_gate_outward
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0032_store_issue'
down_revision: Union[str, Sequence[str], None] = '0031_gate_outward'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'storeissue'):
        op.create_table('storeissue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('issue_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('from_location_id', sa.Integer(), nullable=False),
        sa.Column('analytic_account_id', sa.Integer(), nullable=True),
        sa.Column('debit_account_id', sa.Integer(), nullable=False),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analytic_account_id'], ['analyticaccount.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['debit_account_id'], ['account.id'], ),
        sa.ForeignKeyConstraint(['from_location_id'], ['stocklocation.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number', name='unique_si_number_per_tenant')
        )
        op.create_index(op.f('ix_storeissue_number'), 'storeissue', ['number'], unique=False)
        op.create_index(op.f('ix_storeissue_tenant_id'), 'storeissue', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'storeissueline'):
        op.create_table('storeissueline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_issue_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint('qty > 0', name='ck_si_line_qty_positive'),
        sa.ForeignKeyConstraint(['store_issue_id'], ['storeissue.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_storeissueline_store_issue_id'), 'storeissueline', ['store_issue_id'], unique=False)


def downgrade() -> None:
    op.drop_table('storeissueline')
    op.drop_table('storeissue')
