"""StatementLine.external_id for Plaid de-dupe (#214)

Revision ID: 0043_statement_external_id
Revises: 0042_payment_fx
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0043_statement_external_id"
down_revision: Union[str, Sequence[str], None] = "0042_payment_fx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("statementline")}
    if "external_id" not in cols:
        with op.batch_alter_table("statementline") as batch:
            batch.add_column(sa.Column("external_id", sa.String(), nullable=True))
            batch.create_index("ix_statementline_external_id", ["external_id"])


def downgrade() -> None:
    with op.batch_alter_table("statementline") as batch:
        batch.drop_index("ix_statementline_external_id")
        batch.drop_column("external_id")
