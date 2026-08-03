"""Withholding tax + corporate tax worksheet (#267).

Revision ID: 0066_wht_cit
Revises: 0065_eu_peppol
Create Date: 2026-08-04

Temporarily revises 0065_eu_peppol so this branch does not depend on unmerged
peppol (0065_eu_peppol). Parent will set down_revision to 0065_eu_peppol when
merging after peppol lands.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0066_wht_cit"
down_revision: Union[str, Sequence[str], None] = "0065_eu_peppol"
branch_labels = None
depends_on = None


def _add_col_if_missing(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()

    _add_col_if_missing(
        "taxcode",
        "is_withholding",
        sa.Column("is_withholding", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    _add_col_if_missing(
        "vendor",
        "wht_tax_code_id",
        sa.Column("wht_tax_code_id", sa.Integer(), nullable=True),
    )
    _add_col_if_missing(
        "vendor",
        "wht_rate",
        sa.Column("wht_rate", sa.Numeric(10, 4), nullable=True),
    )

    _add_col_if_missing(
        "billpayment",
        "vendor_id",
        sa.Column("vendor_id", sa.Integer(), nullable=True),
    )
    _add_col_if_missing(
        "billpayment",
        "wht_amount",
        sa.Column(
            "wht_amount",
            sa.Numeric(18, 4),
            nullable=False,
            server_default="0",
        ),
    )

    if not bind.dialect.has_table(bind, "citadjustment"):
        op.create_table(
            "citadjustment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("fiscal_year", sa.String(), nullable=False, index=True),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "citadjustment"):
        op.drop_table("citadjustment")
    for table, col in (
        ("billpayment", "wht_amount"),
        ("billpayment", "vendor_id"),
        ("vendor", "wht_rate"),
        ("vendor", "wht_tax_code_id"),
        ("taxcode", "is_withholding"),
    ):
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if col in cols:
            op.drop_column(table, col)
