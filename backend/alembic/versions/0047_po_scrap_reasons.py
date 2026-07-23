"""PO-scoped scrap/damage reason codes (#224)

Revision ID: 0047_po_scrap_reasons
Revises: 0046_bom_multi_output
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0047_po_scrap_reasons"
down_revision: Union[str, Sequence[str], None] = "0046_bom_multi_output"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "scrapreason"):
        op.create_table(
            "scrapreason",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if not bind.dialect.has_table(bind, "productionscrap"):
        op.create_table(
            "productionscrap",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("po_id", sa.Integer(), nullable=False, index=True),
            sa.Column("reason_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False, index=True),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("gl_posted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "productionscrap"):
        op.drop_table("productionscrap")
    if bind.dialect.has_table(bind, "scrapreason"):
        op.drop_table("scrapreason")
