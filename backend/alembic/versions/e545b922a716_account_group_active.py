"""account_group_active

Add is_group (Boolean, default false) and is_active (Boolean, default true)
to the account table.  Purely additive — existing rows default to
is_group=false / is_active=true (all remain active postable leaves).

SQLite-safe:
  - ADD COLUMN (not ADD CONSTRAINT) — SQLite supports this.
  - FK ADD-CONSTRAINT lines from autogenerate are omitted; tenant ownership
    is enforced at the application layer.
  - Columns are guarded with a column-existence check so this migration is
    idempotent against a create_all() bootstrapped database.

Revision ID: e545b922a716
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e545b922a716"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("account")}

    if "is_group" not in cols:
        op.add_column(
            "account",
            sa.Column(
                "is_group",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),  # SQLite uses 0/1 for booleans
            ),
        )
        op.create_index(op.f("ix_account_is_group"), "account", ["is_group"], unique=False)

    if "is_active" not in cols:
        op.add_column(
            "account",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),  # existing rows → active
            ),
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_account_is_group"), table_name="account")
    op.drop_column("account", "is_active")
    op.drop_column("account", "is_group")
