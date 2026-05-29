"""returns_and_advances

Revision ID: 520ea8c9ea33
Revises: ea79f9418e73
Create Date: 2026-05-29 11:30:27.375156

Adds Purchase Return (DebitNote/DebitNoteLine) and Advances
(CustomerAdvance/VendorAdvance). Tables are guarded with has_table() so they
coexist with the dev `create_all()` baseline. FK ADD-CONSTRAINT lines are
omitted — SQLite cannot ALTER constraints; tenant ownership is enforced in
the application layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '520ea8c9ea33'
down_revision: Union[str, Sequence[str], None] = 'ea79f9418e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _money():
    return sa.Numeric(precision=18, scale=4)


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'debitnote'):
        op.create_table(
            'debitnote',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('bill_id', sa.Integer(), nullable=False),
            sa.Column('vendor_id', sa.Integer(), nullable=True),
            sa.Column('vendor_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('issue_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('subtotal', _money(), nullable=False),
            sa.Column('gst_amount', _money(), nullable=False),
            sa.Column('total', _money(), nullable=False),
            sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('exchange_rate', _money(), nullable=False),
            sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('ap_account_id', sa.Integer(), nullable=True),
            sa.Column('transaction_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('draft','posted','applied')", name='ck_dn_status'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
            sa.ForeignKeyConstraint(['bill_id'], ['bill.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', 'number', name='unique_dn_number_per_tenant'),
        )
        op.create_index(op.f('ix_debitnote_tenant_id'), 'debitnote', ['tenant_id'], unique=False)

    if not bind.dialect.has_table(bind, 'debitnoteline'):
        op.create_table(
            'debitnoteline',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('debit_note_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('qty', _money(), nullable=False),
            sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('rate', _money(), nullable=False),
            sa.Column('amount', _money(), nullable=False),
            sa.ForeignKeyConstraint(['debit_note_id'], ['debitnote.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    for tbl, party_col, party_fk in (
        ('customeradvance', 'customer_id', 'customer.id'),
        ('vendoradvance', 'vendor_id', 'vendor.id'),
    ):
        if not bind.dialect.has_table(bind, tbl):
            ck = ('ck_cadv_status' if tbl == 'customeradvance' else 'ck_vadv_status')
            uq = ('unique_cadv_number_per_tenant' if tbl == 'customeradvance'
                  else 'unique_vadv_number_per_tenant')
            op.create_table(
                tbl,
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('tenant_id', sa.Integer(), nullable=False),
                sa.Column('number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
                sa.Column(party_col, sa.Integer(), nullable=False),
                sa.Column('date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
                sa.Column('amount', _money(), nullable=False),
                sa.Column('applied_amount', _money(), nullable=False),
                sa.Column('cash_account_id', sa.Integer(), nullable=False),
                sa.Column('advance_account_id', sa.Integer(), nullable=False),
                sa.Column('transaction_id', sa.Integer(), nullable=True),
                sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
                sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=False),
                sa.CheckConstraint("status IN ('open','partial','applied')", name=ck),
                sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
                sa.ForeignKeyConstraint([party_col], [party_fk]),
                sa.PrimaryKeyConstraint('id'),
                sa.UniqueConstraint('tenant_id', 'number', name=uq),
            )
            op.create_index(op.f(f'ix_{tbl}_tenant_id'), tbl, ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_table('vendoradvance')
    op.drop_table('customeradvance')
    op.drop_table('debitnoteline')
    op.drop_table('debitnote')
