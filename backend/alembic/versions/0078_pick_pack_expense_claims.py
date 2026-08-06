"""Pick/pack + reservations (#302) and expense claims (#303)

Revision ID: 0078_pick_pack_expense_claims
Revises: 0077_ecommerce_connectors
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0078_pick_pack_expense_claims"
down_revision: Union[str, Sequence[str], None] = "0077_ecommerce_connectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "stockreservation"):
        op.create_table(
            "stockreservation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False, index=True),
            sa.Column("location_id", sa.Integer(), nullable=True, index=True),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("source_doc_type", sa.String(), nullable=False, server_default="manual"),
            sa.Column("source_doc_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("released_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_stockreservation_status", "stockreservation", ["status"])
        op.create_index(
            "ix_stockreservation_source",
            "stockreservation",
            ["source_doc_type", "source_doc_id"],
        )

    if not bind.dialect.has_table(bind, "picklist"):
        op.create_table(
            "picklist",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("number", sa.String(), nullable=False, index=True),
            sa.Column("invoice_id", sa.Integer(), nullable=False, index=True),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("packed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_picklist_status", "picklist", ["status"])

    if not bind.dialect.has_table(bind, "picklistline"):
        op.create_table(
            "picklistline",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pick_list_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("qty_ordered", sa.Numeric(18, 4), nullable=False),
            sa.Column("qty_picked", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("reservation_id", sa.Integer(), nullable=True),
        )

    if not bind.dialect.has_table(bind, "expenseclaim"):
        op.create_table(
            "expenseclaim",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("number", sa.String(), nullable=False, index=True),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("claim_date", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("total", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("bill_id", sa.Integer(), nullable=True),
            sa.Column("vendor_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("reject_reason", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_expenseclaim_status", "expenseclaim", ["status"])

    if not bind.dialect.has_table(bind, "expenseclaimline"):
        op.create_table(
            "expenseclaimline",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("claim_id", sa.Integer(), nullable=False, index=True),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("expense_account_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "expenseclaimline",
        "expenseclaim",
        "picklistline",
        "picklist",
        "stockreservation",
    ):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
