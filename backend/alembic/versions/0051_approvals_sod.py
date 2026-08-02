"""Approvals SoD — amount snapshot, substitutes, decision log (#269)

Revision ID: 0051_approvals_sod
Revises: 0050_tax_engine
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0051_approvals_sod"
down_revision: Union[str, Sequence[str], None] = "0050_tax_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.has_table(bind, "approvalrequest"):
        cols = {c["name"] for c in insp.get_columns("approvalrequest")}
        if "amount" not in cols:
            with op.batch_alter_table("approvalrequest") as batch:
                batch.add_column(
                    sa.Column("amount", sa.Float(), nullable=False, server_default="0")
                )

    if not bind.dialect.has_table(bind, "approvalsubstitute"):
        op.create_table(
            "approvalsubstitute",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("substitute_user_id", sa.Integer(), nullable=False),
            sa.Column("starts_on", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("ends_on", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_approvalsubstitute_tenant_id", "approvalsubstitute", ["tenant_id"])
        op.create_index("ix_approvalsubstitute_user_id", "approvalsubstitute", ["user_id"])
        op.create_index(
            "ix_approvalsubstitute_substitute_user_id",
            "approvalsubstitute",
            ["substitute_user_id"],
        )

    if not bind.dialect.has_table(bind, "approvaldecision"):
        op.create_table(
            "approvaldecision",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("action", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_approvaldecision_tenant_id", "approvaldecision", ["tenant_id"])
        op.create_index("ix_approvaldecision_request_id", "approvaldecision", ["request_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "approvaldecision"):
        op.drop_table("approvaldecision")
    if bind.dialect.has_table(bind, "approvalsubstitute"):
        op.drop_table("approvalsubstitute")
    if bind.dialect.has_table(bind, "approvalrequest"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("approvalrequest")}
        if "amount" in cols:
            with op.batch_alter_table("approvalrequest") as batch:
                batch.drop_column("amount")
