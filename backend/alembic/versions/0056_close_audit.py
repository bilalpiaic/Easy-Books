"""Month-end close checklist + auditor export pack (#262).

Revision ID: 0056_close_audit
Revises: 0055_inventory_depth
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0056_close_audit"
down_revision: Union[str, Sequence[str], None] = "0055_inventory_depth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "closechecklistitem"):
        return
    op.create_table(
        "closechecklistitem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("task_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by_id", sa.Integer(), nullable=True),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.UniqueConstraint("tenant_id", "period_id", "task_key", name="uq_close_checklist_period_task"),
    )
    op.create_index("ix_closechecklistitem_tenant_id", "closechecklistitem", ["tenant_id"])
    op.create_index("ix_closechecklistitem_period_id", "closechecklistitem", ["period_id"])
    op.create_index("ix_closechecklistitem_task_key", "closechecklistitem", ["task_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "closechecklistitem"):
        op.drop_table("closechecklistitem")
