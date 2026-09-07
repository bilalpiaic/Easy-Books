"""device_token — Capacitor push tokens (#307).

Revision ID: 0088_device_tokens
Revises: 0087_uk_mtd_my_invois
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0088_device_tokens"
down_revision: Union[str, Sequence[str], None] = "0087_uk_mtd_my_invois"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "device_token"):
        return
    op.create_table(
        "device_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token", name="uq_device_token_token"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "device_token"):
        op.drop_table("device_token")
