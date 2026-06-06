"""voucher series columns

Add ``voucher_type`` (not null, server_default 'JV') and ``legacy_jv_number``
(nullable) to the ``transaction`` table.  Both columns are existence-guarded
so the migration is safe to run against a database that was bootstrapped with
``SQLModel.metadata.create_all()`` which already has the new model fields.

SQLite-safe: no FK or UNIQUE constraint changes — just two ADD COLUMN calls.

Revision ID: 9ea44fbcd894
Revises: 5befc82a251f
Create Date: 2026-06-06 16:53:47.136490
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9ea44fbcd894'
down_revision: Union[str, Sequence[str], None] = '5befc82a251f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("transaction")}

    # voucher_type: not-null with a server-side default so existing rows get 'JV'.
    if "voucher_type" not in cols:
        op.add_column(
            "transaction",
            sa.Column(
                "voucher_type",
                sa.String(),
                nullable=False,
                server_default="JV",
            ),
        )

    # legacy_jv_number: nullable — populated by the backfill migration (Task 3).
    if "legacy_jv_number" not in cols:
        op.add_column(
            "transaction",
            sa.Column("legacy_jv_number", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("transaction")}

    if "legacy_jv_number" in cols:
        op.drop_column("transaction", "legacy_jv_number")

    if "voucher_type" in cols:
        op.drop_column("transaction", "voucher_type")
