"""Textile Processing strengthen — quality CODE structure, SO lines, than Rej/Safi, packing types.

Revision ID: 0071_textile_processing_strengthen
Revises: 0070_textile_processing
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0071_textile_processing_strengthen"
down_revision: Union[str, Sequence[str], None] = "0070_textile_processing"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return bind.dialect.has_table(bind, name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # TpQuality structured CODE fields
    for col, typ in (
        ("fiber", sa.String()),
        ("warp_count", sa.String()),
        ("weft_count", sa.String()),
        ("epi", sa.String()),
        ("ppi", sa.String()),
        ("width_inch", sa.String()),
    ):
        if not _has_column(bind, "tp_quality", col):
            op.add_column("tp_quality", sa.Column(col, typ, nullable=True))

    # TpGreyThan Rej / Safi
    if not _has_column(bind, "tp_grey_than", "rejection_mtr"):
        op.add_column(
            "tp_grey_than",
            sa.Column("rejection_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )
    if not _has_column(bind, "tp_grey_than", "safi_mtr"):
        op.add_column(
            "tp_grey_than",
            sa.Column("safi_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )

    # TpPacking assortment tags
    for col, typ in (
        ("item_type", sa.String()),
        ("quality_id", sa.Integer()),
        ("process_id", sa.Integer()),
    ):
        if not _has_column(bind, "tp_packing", col):
            op.add_column("tp_packing", sa.Column(col, typ, nullable=True))

    if not _has_table(bind, "tp_sales_order_quality_line"):
        op.create_table(
            "tp_sales_order_quality_line",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("sales_order_id", sa.Integer(), nullable=False, index=True),
            sa.Column("quality_id", sa.Integer(), nullable=False, index=True),
            sa.Column("expected_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("grey_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
        )

    if not _has_table(bind, "tp_sales_order_packing_line"):
        op.create_table(
            "tp_sales_order_packing_line",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("sales_order_id", sa.Integer(), nullable=False, index=True),
            sa.Column("item_type", sa.String(), nullable=False, server_default="KMZ"),
            sa.Column("quality_id", sa.Integer(), nullable=False, index=True),
            sa.Column("process_id", sa.Integer(), nullable=True),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("meters", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "tp_sales_order_packing_line"):
        op.drop_table("tp_sales_order_packing_line")
    if _has_table(bind, "tp_sales_order_quality_line"):
        op.drop_table("tp_sales_order_quality_line")
    for col in ("process_id", "quality_id", "item_type"):
        if _has_column(bind, "tp_packing", col):
            op.drop_column("tp_packing", col)
    for col in ("safi_mtr", "rejection_mtr"):
        if _has_column(bind, "tp_grey_than", col):
            op.drop_column("tp_grey_than", col)
    for col in ("width_inch", "ppi", "epi", "weft_count", "warp_count", "fiber"):
        if _has_column(bind, "tp_quality", col):
            op.drop_column("tp_quality", col)
