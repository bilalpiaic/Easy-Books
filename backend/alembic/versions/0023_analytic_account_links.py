"""analytic_account_id links to invoice, bill, paymentreceived, billpayment

Revision ID: 0023analytic_links
Revises: 0022_promo_rules
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0023analytic_links"
down_revision: Union[str, Sequence[str], None] = "0022_promo_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for tbl in ("invoice", "bill", "paymentreceived", "billpayment"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns(tbl)}
        if "analytic_account_id" not in cols:
            op.add_column(tbl, sa.Column("analytic_account_id", sa.Integer(), nullable=True))
    # FK constraints omitted: SQLite does not support ADD CONSTRAINT via ALTER TABLE.


def downgrade() -> None:
    for tbl in ("invoice", "bill", "paymentreceived", "billpayment"):
        op.drop_column(tbl, "analytic_account_id")
