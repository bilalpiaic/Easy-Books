"""Repair tenant SaaS columns dropped by 0067 sqlite rebuild.

Revision ID: 0068_tenant_saas_repair
Revises: 0067_spinning_module
Create Date: 2026-08-04

0067's SQLite tenant table rebuild copied only a subset of columns and silently
dropped plan/max_users/... added in 0041_wave_bcd. This migration restores them
idempotently so existing installs can start again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0068_tenant_saas_repair"
down_revision: Union[str, Sequence[str], None] = "0067_spinning_module"
branch_labels = None
depends_on = None

_TENANT_SAAS_COLS = [
    ("plan", sa.Column("plan", sa.String(), server_default="free", nullable=False)),
    ("max_users", sa.Column("max_users", sa.Integer(), server_default="2", nullable=False)),
    ("max_documents", sa.Column("max_documents", sa.Integer(), server_default="50", nullable=False)),
    ("storage_quota_mb", sa.Column("storage_quota_mb", sa.Integer(), server_default="100", nullable=False)),
    ("is_suspended", sa.Column("is_suspended", sa.Boolean(), server_default=sa.false(), nullable=False)),
    ("trial_ends_at", sa.Column("trial_ends_at", sa.DateTime(), nullable=True)),
    ("stripe_customer_id", sa.Column("stripe_customer_id", sa.String(), nullable=True)),
    ("stripe_subscription_id", sa.Column("stripe_subscription_id", sa.String(), nullable=True)),
    ("subscription_status", sa.Column("subscription_status", sa.String(), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not bind.dialect.has_table(bind, "tenant"):
        return

    tcols = {c["name"] for c in insp.get_columns("tenant")}
    missing = [name for name, _ in _TENANT_SAAS_COLS if name not in tcols]
    if not missing:
        return

    with op.batch_alter_table("tenant") as batch:
        for name, col in _TENANT_SAAS_COLS:
            if name not in tcols:
                batch.add_column(col)

    if "plan" in missing:
        op.create_index("ix_tenant_plan", "tenant", ["plan"], unique=False)


def downgrade() -> None:
    # Non-destructive repair — leave columns in place on downgrade.
    pass
