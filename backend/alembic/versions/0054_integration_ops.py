"""Task dead-letter + DLQ retry (#271).

Revision ID: 0054_integration_ops
Revises: 0053_portal_harden
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0054_integration_ops"
down_revision: Union[str, Sequence[str], None] = "0053_portal_harden"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "taskdeadletter"):
        return
    op.create_table(
        "taskdeadletter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("task_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("args_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="[]"),
        sa.Column("kwargs_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="{}"),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("retried_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_taskdeadletter_tenant_id", "taskdeadletter", ["tenant_id"])
    op.create_index("ix_taskdeadletter_task_name", "taskdeadletter", ["task_name"])
    op.create_index("ix_taskdeadletter_status", "taskdeadletter", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "taskdeadletter"):
        op.drop_table("taskdeadletter")
