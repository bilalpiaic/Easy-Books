"""Intercompany flags + mirror links on invoice/bill (#261).

Revision ID: 0062_intercompany
Revises: 0061_analytic_dimensions
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0062_intercompany"
down_revision: Union[str, Sequence[str], None] = "0061_analytic_dimensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        if "is_intercompany" not in inv_cols:
            batch.add_column(
                sa.Column("is_intercompany", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "ic_counterparty_tenant_id" not in inv_cols:
            batch.add_column(sa.Column("ic_counterparty_tenant_id", sa.Integer(), nullable=True))
        if "ic_mirror_bill_id" not in inv_cols:
            batch.add_column(sa.Column("ic_mirror_bill_id", sa.Integer(), nullable=True))

    bill_cols = {c["name"] for c in sa.inspect(bind).get_columns("bill")}
    with op.batch_alter_table("bill") as batch:
        if "is_intercompany" not in bill_cols:
            batch.add_column(
                sa.Column("is_intercompany", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "ic_counterparty_tenant_id" not in bill_cols:
            batch.add_column(sa.Column("ic_counterparty_tenant_id", sa.Integer(), nullable=True))
        if "ic_mirror_invoice_id" not in bill_cols:
            batch.add_column(sa.Column("ic_mirror_invoice_id", sa.Integer(), nullable=True))

    # Indexes (idempotent via try/exists pattern for SQLite recreate)
    inv_idxs = {ix["name"] for ix in sa.inspect(bind).get_indexes("invoice")}
    if "ix_invoice_is_intercompany" not in inv_idxs:
        op.create_index("ix_invoice_is_intercompany", "invoice", ["is_intercompany"])
    if "ix_invoice_ic_counterparty_tenant_id" not in inv_idxs:
        op.create_index(
            "ix_invoice_ic_counterparty_tenant_id", "invoice", ["ic_counterparty_tenant_id"]
        )

    bill_idxs = {ix["name"] for ix in sa.inspect(bind).get_indexes("bill")}
    if "ix_bill_is_intercompany" not in bill_idxs:
        op.create_index("ix_bill_is_intercompany", "bill", ["is_intercompany"])
    if "ix_bill_ic_counterparty_tenant_id" not in bill_idxs:
        op.create_index(
            "ix_bill_ic_counterparty_tenant_id", "bill", ["ic_counterparty_tenant_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    bill_idxs = {ix["name"] for ix in sa.inspect(bind).get_indexes("bill")}
    for name in ("ix_bill_ic_counterparty_tenant_id", "ix_bill_is_intercompany"):
        if name in bill_idxs:
            op.drop_index(name, table_name="bill")
    inv_idxs = {ix["name"] for ix in sa.inspect(bind).get_indexes("invoice")}
    for name in ("ix_invoice_ic_counterparty_tenant_id", "ix_invoice_is_intercompany"):
        if name in inv_idxs:
            op.drop_index(name, table_name="invoice")

    with op.batch_alter_table("bill") as batch:
        batch.drop_column("ic_mirror_invoice_id")
        batch.drop_column("ic_counterparty_tenant_id")
        batch.drop_column("is_intercompany")
    with op.batch_alter_table("invoice") as batch:
        batch.drop_column("ic_mirror_bill_id")
        batch.drop_column("ic_counterparty_tenant_id")
        batch.drop_column("is_intercompany")
