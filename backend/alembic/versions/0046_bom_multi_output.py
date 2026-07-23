"""Multi-output BoMs + PO output snapshots (#223)

Revision ID: 0046_bom_multi_output
Revises: 0045_po_overhead_partial
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0046_bom_multi_output"
down_revision: Union[str, Sequence[str], None] = "0045_po_overhead_partial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.has_table(bind, "bomheader"):
        cols = {c["name"] for c in insp.get_columns("bomheader")}
        if "cost_alloc_method" not in cols:
            op.add_column(
                "bomheader",
                sa.Column(
                    "cost_alloc_method",
                    sa.String(),
                    nullable=False,
                    server_default="primary_only",
                ),
            )

    if not bind.dialect.has_table(bind, "bomoutput"):
        op.create_table(
            "bomoutput",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("bom_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False, index=True),
            sa.Column("qty_per_batch", sa.Numeric(18, 4), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="primary"),
            sa.Column("alloc_pct", sa.Numeric(18, 4), nullable=True),
            sa.Column("sales_price_hint", sa.Numeric(18, 4), nullable=True),
        )
        # Backfill one primary output per existing BoM header
        op.execute(
            """
            INSERT INTO bomoutput (bom_id, product_id, qty_per_batch, role)
            SELECT id, output_product_id, output_qty, 'primary'
            FROM bomheader
            """
        )

    if not bind.dialect.has_table(bind, "productionorderoutput"):
        op.create_table(
            "productionorderoutput",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("po_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False, index=True),
            sa.Column("role", sa.String(), nullable=False, server_default="primary"),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("delivered_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "productionorderoutput"):
        op.drop_table("productionorderoutput")
    if bind.dialect.has_table(bind, "bomoutput"):
        op.drop_table("bomoutput")
    if bind.dialect.has_table(bind, "bomheader"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("bomheader")}
        if "cost_alloc_method" in cols:
            op.drop_column("bomheader", "cost_alloc_method")
