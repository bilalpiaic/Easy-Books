"""Bank feed sync status columns on plaidconnection (#301)

Revision ID: 0072_bank_feed_sync_status
Revises: 0071_textile_processing_strengthen
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0072_bank_feed_sync_status"
down_revision: Union[str, Sequence[str], None] = "0071_textile_processing_strengthen"
branch_labels = None
depends_on = None


def _add_col_if_missing(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table):
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    _add_col_if_missing(
        "plaidconnection",
        "provider",
        sa.Column("provider", sa.String(), nullable=False, server_default="plaid"),
    )
    _add_col_if_missing(
        "plaidconnection",
        "last_error",
        sa.Column("last_error", sa.String(), nullable=True),
    )
    _add_col_if_missing(
        "plaidconnection",
        "sync_status",
        sa.Column("sync_status", sa.String(), nullable=False, server_default="never"),
    )
    _add_col_if_missing(
        "plaidconnection",
        "consent_expires_at",
        sa.Column("consent_expires_at", sa.DateTime(), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "plaidconnection"):
        try:
            op.create_index("ix_plaidconnection_provider", "plaidconnection", ["provider"])
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "plaidconnection"):
        return
    for name in ("consent_expires_at", "sync_status", "last_error", "provider"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("plaidconnection")}
        if name in cols:
            op.drop_column("plaidconnection", name)
