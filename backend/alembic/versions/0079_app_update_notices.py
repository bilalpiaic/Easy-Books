"""App update notices for in-app what's-new notifications

Revision ID: 0079_app_update_notices
Revises: 0078_pick_pack_expense_claims
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0079_app_update_notices"
down_revision: Union[str, Sequence[str], None] = "0078_pick_pack_expense_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "app_update_notice"):
        op.create_table(
            "app_update_notice",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sha", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=True),
            sa.Column("commit_date", sa.String(), nullable=True),
            sa.Column("notify_users", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_app_update_notice_sha", "app_update_notice", ["sha"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "app_update_notice"):
        op.drop_table("app_update_notice")
