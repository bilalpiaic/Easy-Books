"""0026_pra_integration

Revision ID: d42ac2e7674d
Revises: 0025_attendance
Create Date: 2026-06-22 10:13:24.896808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'd42ac2e7674d'
down_revision: Union[str, Sequence[str], None] = '0025_attendance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # New table: PRASubmissionLog (guarded for coexistence with create_all)
    if not bind.dialect.has_table(bind, 'prasubmissionlog'):
        op.create_table(
            'prasubmissionlog',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('invoice_id', sa.Integer(), nullable=False),
            sa.Column('attempt_at', sa.DateTime(), nullable=False),
            sa.Column('endpoint', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('request_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('response_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('response_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('http_status', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.Column('error_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_prasubmissionlog_invoice_id', 'prasubmissionlog', ['invoice_id'])
        op.create_index('ix_prasubmissionlog_tenant_id', 'prasubmissionlog', ['tenant_id'])

    # Customer: buyer tax identification for PRA
    cols = {c['name'] for c in sa.inspect(bind).get_columns('customer')}
    if 'ntn' not in cols:
        op.add_column('customer', sa.Column('ntn', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    if 'cnic' not in cols:
        op.add_column('customer', sa.Column('cnic', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Invoice: PRA e-Invoice tracking fields
    inv_cols = {c['name'] for c in sa.inspect(bind).get_columns('invoice')}
    if 'payment_mode' not in inv_cols:
        op.add_column('invoice', sa.Column('payment_mode', sa.Integer(), nullable=True))
    if 'pra_usin' not in inv_cols:
        op.add_column('invoice', sa.Column('pra_usin', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    if 'pra_fiscal_number' not in inv_cols:
        op.add_column('invoice', sa.Column('pra_fiscal_number', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    if 'pra_status' not in inv_cols:
        op.add_column('invoice', sa.Column('pra_status', sqlmodel.sql.sqltypes.AutoString(),
                                           nullable=False, server_default='not_required'))
    if 'pra_submitted_at' not in inv_cols:
        op.add_column('invoice', sa.Column('pra_submitted_at', sa.DateTime(), nullable=True))
    if 'pra_response_raw' not in inv_cols:
        op.add_column('invoice', sa.Column('pra_response_raw', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Product: PRA product classification code
    prod_cols = {c['name'] for c in sa.inspect(bind).get_columns('product')}
    if 'pct_code' not in prod_cols:
        op.add_column('product', sa.Column('pct_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('product', 'pct_code')
    op.drop_column('invoice', 'pra_response_raw')
    op.drop_column('invoice', 'pra_submitted_at')
    op.drop_column('invoice', 'pra_status')
    op.drop_column('invoice', 'pra_fiscal_number')
    op.drop_column('invoice', 'pra_usin')
    op.drop_column('invoice', 'payment_mode')
    op.drop_column('customer', 'cnic')
    op.drop_column('customer', 'ntn')
    op.drop_index('ix_prasubmissionlog_tenant_id', table_name='prasubmissionlog')
    op.drop_index('ix_prasubmissionlog_invoice_id', table_name='prasubmissionlog')
    op.drop_table('prasubmissionlog')
