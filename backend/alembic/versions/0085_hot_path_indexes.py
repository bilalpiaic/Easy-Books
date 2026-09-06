"""Hot-path indexes for journal, dashboard, invoice lists, and allocations.

Revision ID: 0085_hot_path_indexes
Revises: 0084_password_reset
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0085_hot_path_indexes"
down_revision: Union[str, Sequence[str], None] = "0084_password_reset"
branch_labels = None
depends_on = None

_INDEXES = (
    ("transaction", "ix_transaction_tenant_date", ["tenant_id", "date"]),
    ("journalentry", "ix_journalentry_transaction_id", ["transaction_id"]),
    ("journalentry", "ix_journalentry_account_id", ["account_id"]),
    ("invoice", "ix_invoice_tenant_issue_date", ["tenant_id", "issue_date"]),
    ("invoiceline", "ix_invoiceline_invoice_id", ["invoice_id"]),
    ("billline", "ix_billline_bill_id", ["bill_id"]),
    ("paymentallocation", "ix_paymentallocation_invoice_id", ["invoice_id"]),
    ("paymentallocation", "ix_paymentallocation_bill_id", ["bill_id"]),
)


def _index_names(bind, table: str) -> set[str]:
    if not bind.dialect.has_table(bind, table):
        return set()
    return {ix["name"] for ix in sa.inspect(bind).get_indexes(table) if ix.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    for table, name, columns in _INDEXES:
        if name not in _index_names(bind, table):
            op.create_index(name, table, columns)


def downgrade() -> None:
    bind = op.get_bind()
    for table, name, _columns in reversed(_INDEXES):
        if name in _index_names(bind, table):
            op.drop_index(name, table_name=table)
