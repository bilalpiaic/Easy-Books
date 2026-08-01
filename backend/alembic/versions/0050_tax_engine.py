"""Core tax engine — flags, rate history, line snapshots (#263)

Revision ID: 0050_tax_engine
Revises: 0049_uae_einvoice_log
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0050_tax_engine"
down_revision: Union[str, Sequence[str], None] = "0049_uae_einvoice_log"
branch_labels = None
depends_on = None


def _add_col_if_missing(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()

    for flag in ("is_reverse_charge", "is_exempt", "is_zero_rated"):
        _add_col_if_missing(
            "taxcode",
            flag,
            sa.Column(flag, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    for table in ("invoiceline", "billline"):
        _add_col_if_missing(
            table, "tax_rate", sa.Column("tax_rate", sa.Numeric(10, 4), nullable=True)
        )
        _add_col_if_missing(
            table,
            "tax_amount",
            sa.Column(
                "tax_amount",
                sa.Numeric(18, 4),
                nullable=False,
                server_default="0",
            ),
        )
        _add_col_if_missing(
            table,
            "tax_inclusive",
            sa.Column("tax_inclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not bind.dialect.has_table(bind, "taxratehistory"):
        op.create_table(
            "taxratehistory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tax_code_id", sa.Integer(), nullable=False, index=True),
            sa.Column("rate", sa.Numeric(18, 4), nullable=False),
            sa.Column("effective_from", sa.String(), nullable=False, index=True),
            sa.Column("effective_to", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_taxratehistory_code_from",
            "taxratehistory",
            ["tax_code_id", "effective_from"],
        )

    # Seed one open-ended history row per existing tax code (idempotent).
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(sa.text("SELECT DISTINCT tax_code_id FROM taxratehistory")).fetchall()
    }
    for row in conn.execute(sa.text("SELECT id, rate FROM taxcode")).fetchall():
        tc_id, rate = row[0], row[1]
        if tc_id in existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO taxratehistory (tax_code_id, rate, effective_from, effective_to) "
                "VALUES (:tid, :rate, '1900-01-01', NULL)"
            ),
            {"tid": tc_id, "rate": rate},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "taxratehistory"):
        op.drop_table("taxratehistory")
    # Column drops omitted — SQLite-hostile; forward-only in practice.
