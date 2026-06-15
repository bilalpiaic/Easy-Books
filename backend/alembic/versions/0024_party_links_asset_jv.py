"""customer_id/vendor_id on journalentry, party_type on account, acquisition_transaction_id on fixedasset

Revision ID: 0024_party_links
Revises: 0023analytic_links
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0024_party_links"
down_revision: Union[str, Sequence[str], None] = "0023analytic_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    je_cols = {c["name"] for c in sa.inspect(bind).get_columns("journalentry")}
    if "customer_id" not in je_cols:
        op.add_column("journalentry", sa.Column("customer_id", sa.Integer(), nullable=True))
    if "vendor_id" not in je_cols:
        op.add_column("journalentry", sa.Column("vendor_id", sa.Integer(), nullable=True))

    acc_cols = {c["name"] for c in sa.inspect(bind).get_columns("account")}
    if "party_type" not in acc_cols:
        op.add_column("account", sa.Column("party_type", sa.String(), nullable=True))

    fa_cols = {c["name"] for c in sa.inspect(bind).get_columns("fixedasset")}
    if "acquisition_transaction_id" not in fa_cols:
        op.add_column(
            "fixedasset",
            sa.Column("acquisition_transaction_id", sa.Integer(), nullable=True),
        )
    # FK constraints omitted: SQLite does not support ADD CONSTRAINT via ALTER TABLE.


def downgrade() -> None:
    op.drop_column("journalentry", "customer_id")
    op.drop_column("journalentry", "vendor_id")
    op.drop_column("account", "party_type")
    op.drop_column("fixedasset", "acquisition_transaction_id")
