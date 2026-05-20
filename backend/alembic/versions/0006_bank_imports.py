"""P6: bank statement imports + statement lines.

Revision ID: 0006_bank_imports
Revises: 0005_multi_currency
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_bank_imports"
down_revision = "0005_multi_currency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "bankstatementimport" not in tables:
        op.create_table(
            "bankstatementimport",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bankaccount.id"), nullable=False),
            sa.Column("file_name", sa.String(), nullable=False),
            sa.Column("file_hash", sa.String(), nullable=False, index=True),
            sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(), nullable=False, server_default="parsed"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "bank_account_id", "file_hash",
                name="unique_bank_import_file_per_account",
            ),
        )

    if "statementline" not in tables:
        op.create_table(
            "statementline",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("import_id", sa.Integer(),
                      sa.ForeignKey("bankstatementimport.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("date", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("debit", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("credit", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("matched_transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("is_matched", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_stmt_line_nonneg"),
        )


def downgrade() -> None:
    op.drop_table("statementline")
    op.drop_table("bankstatementimport")
