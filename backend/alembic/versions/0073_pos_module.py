"""POS module tables (#304)

Revision ID: 0073_pos_module
Revises: 0072_bank_feed_sync_status
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0073_pos_module"
down_revision: Union[str, Sequence[str], None] = "0072_bank_feed_sync_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "posregister"):
        op.create_table(
            "posregister",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("code", sa.String(), nullable=False, server_default="REG1"),
            sa.Column("cash_account_id", sa.Integer(), nullable=True),
            sa.Column("bank_account_id", sa.Integer(), nullable=True),
            sa.Column("default_customer_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_posregister_code", "posregister", ["code"])

    if not bind.dialect.has_table(bind, "posshift"):
        op.create_table(
            "posshift",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("register_id", sa.Integer(), nullable=False, index=True),
            sa.Column("opened_by_id", sa.Integer(), nullable=False),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("opening_float", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("closed_by_id", sa.Integer(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("closing_count", sa.Numeric(18, 4), nullable=True),
            sa.Column("expected_cash", sa.Numeric(18, 4), nullable=True),
            sa.Column("variance", sa.Numeric(18, 4), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("notes", sa.String(), nullable=True),
        )
        op.create_index("ix_posshift_status", "posshift", ["status"])

    if not bind.dialect.has_table(bind, "possale"):
        op.create_table(
            "possale",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("shift_id", sa.Integer(), nullable=False, index=True),
            sa.Column("invoice_id", sa.Integer(), nullable=False, index=True),
            sa.Column("payment_received_id", sa.Integer(), nullable=True),
            sa.Column("tender", sa.String(), nullable=False, server_default="cash"),
            sa.Column("cash_tendered", sa.Numeric(18, 4), nullable=True),
            sa.Column("change_given", sa.Numeric(18, 4), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("possale", "posshift", "posregister"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
