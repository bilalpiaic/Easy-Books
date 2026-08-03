"""India GST fields on customer/vendor/product (#265).

Revision ID: 0064_in_gst
Revises: 0063_sa_zatca
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0064_in_gst"
down_revision: Union[str, Sequence[str], None] = "0063_sa_zatca"
branch_labels = None
depends_on = None


def _add_col_if_missing(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    for table in ("customer", "vendor"):
        _add_col_if_missing(table, "gstin", sa.Column("gstin", sa.String(), nullable=True))
        _add_col_if_missing(
            table, "state_code", sa.Column("state_code", sa.String(), nullable=True)
        )
    _add_col_if_missing("product", "hsn_sac", sa.Column("hsn_sac", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table, cols in (
        ("customer", ("gstin", "state_code")),
        ("vendor", ("gstin", "state_code")),
        ("product", ("hsn_sac",)),
    ):
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for col in cols:
            if col in existing:
                op.drop_column(table, col)
