"""Leave module tables (#303)

Revision ID: 0075_leave_module
Revises: 0074_stock_transfers
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0075_leave_module"
down_revision: Union[str, Sequence[str], None] = "0074_stock_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "leavetype"):
        op.create_table(
            "leavetype",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("annual_entitlement", sa.Float(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if not bind.dialect.has_table(bind, "leavebalance"):
        op.create_table(
            "leavebalance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("leave_type_id", sa.Integer(), nullable=False, index=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("entitled", sa.Float(), nullable=False, server_default="0"),
            sa.Column("used", sa.Float(), nullable=False, server_default="0"),
            sa.Column("pending", sa.Float(), nullable=False, server_default="0"),
        )
    if not bind.dialect.has_table(bind, "leaverequest"):
        op.create_table(
            "leaverequest",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("employee_id", sa.Integer(), nullable=False, index=True),
            sa.Column("leave_type_id", sa.Integer(), nullable=False, index=True),
            sa.Column("from_date", sa.String(), nullable=False),
            sa.Column("to_date", sa.String(), nullable=False),
            sa.Column("days", sa.Float(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("reject_reason", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_leaverequest_status", "leaverequest", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("leaverequest", "leavebalance", "leavetype"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
