"""TenantMembership table + backfill from User.tenant_id/role (#220)

Revision ID: 0044_tenant_membership
Revises: 0043_statement_external_id
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0044_tenant_membership"
down_revision: Union[str, Sequence[str], None] = "0043_statement_external_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not bind.dialect.has_table(bind, "tenantmembership"):
        op.create_table(
            "tenantmembership",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="viewer"),
            sa.Column("invited_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_tenantmembership_user_id", "tenantmembership", ["user_id"])
        op.create_index("ix_tenantmembership_tenant_id", "tenantmembership", ["tenant_id"])
        op.create_index("ix_tenantmembership_role", "tenantmembership", ["role"])
        # SQLite can't ADD CONSTRAINT via ALTER; unique enforced at app level
        # for existing DBs. create_all / fresh installs get the model UniqueConstraint.

    # Backfill one membership per existing user (idempotent).
    users = bind.execute(sa.text("SELECT id, tenant_id, role FROM user")).fetchall()
    for uid, tid, role in users:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM tenantmembership WHERE user_id = :u AND tenant_id = :t LIMIT 1"
            ),
            {"u": uid, "t": tid},
        ).fetchone()
        if exists:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO tenantmembership (user_id, tenant_id, role, created_at) "
                "VALUES (:u, :t, :r, CURRENT_TIMESTAMP)"
            ),
            {"u": uid, "t": tid, "r": role or "viewer"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "tenantmembership"):
        op.drop_table("tenantmembership")
