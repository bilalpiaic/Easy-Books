"""Bank feeds harden — rules + match confidence columns (#268)

Revision ID: 0052_bank_feeds
Revises: 0051_approvals_sod
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0052_bank_feeds"
down_revision: Union[str, Sequence[str], None] = "0051_approvals_sod"
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
        "categorizationrule",
        "priority",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )
    _add_col_if_missing(
        "categorizationrule",
        "match_amount",
        sa.Column("match_amount", sa.Float(), nullable=True),
    )
    _add_col_if_missing(
        "categorizationrule",
        "create_expense_draft",
        sa.Column(
            "create_expense_draft",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    for name, col in [
        ("suggested_transaction_id", sa.Column("suggested_transaction_id", sa.Integer(), nullable=True)),
        ("match_confidence", sa.Column("match_confidence", sa.Float(), nullable=True)),
        ("categorized_account_id", sa.Column("categorized_account_id", sa.Integer(), nullable=True)),
        ("match_status", sa.Column("match_status", sa.String(), nullable=True)),
        ("match_decided_by_id", sa.Column("match_decided_by_id", sa.Integer(), nullable=True)),
        ("match_decided_at", sa.Column("match_decided_at", sa.DateTime(), nullable=True)),
        (
            "expense_draft_suggested",
            sa.Column(
                "expense_draft_suggested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        ),
    ]:
        _add_col_if_missing("statementline", name, col)

    bind = op.get_bind()
    if bind.dialect.has_table(bind, "statementline"):
        try:
            op.create_index("ix_statementline_match_status", "statementline", ["match_status"])
        except Exception:
            pass
    if bind.dialect.has_table(bind, "categorizationrule"):
        try:
            op.create_index("ix_categorizationrule_priority", "categorizationrule", ["priority"])
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "statementline"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("statementline")}
        for name in (
            "expense_draft_suggested",
            "match_decided_at",
            "match_decided_by_id",
            "match_status",
            "categorized_account_id",
            "match_confidence",
            "suggested_transaction_id",
        ):
            if name in cols:
                op.drop_column("statementline", name)
    if bind.dialect.has_table(bind, "categorizationrule"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("categorizationrule")}
        for name in ("create_expense_draft", "match_amount", "priority"):
            if name in cols:
                op.drop_column("categorizationrule", name)
