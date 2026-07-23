"""PO overhead/labour absorption rates + delivered_qty (#222)

Revision ID: 0045_po_overhead_partial
Revises: 0044_tenant_membership
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0045_po_overhead_partial"
down_revision: Union[str, Sequence[str], None] = "0044_tenant_membership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.has_table(bind, "rateplan"):
        cols = {c["name"] for c in insp.get_columns("rateplan")}
        if "labour_per_unit" not in cols:
            op.add_column(
                "rateplan",
                sa.Column("labour_per_unit", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )
        if "overhead_per_unit" not in cols:
            op.add_column(
                "rateplan",
                sa.Column("overhead_per_unit", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )

    if bind.dialect.has_table(bind, "productionorder"):
        cols = {c["name"] for c in insp.get_columns("productionorder")}
        if "labour_cost" not in cols:
            op.add_column(
                "productionorder",
                sa.Column("labour_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )
        if "overhead_cost" not in cols:
            op.add_column(
                "productionorder",
                sa.Column("overhead_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )
        if "delivered_qty" not in cols:
            op.add_column(
                "productionorder",
                sa.Column("delivered_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if bind.dialect.has_table(bind, "productionorder"):
        cols = {c["name"] for c in insp.get_columns("productionorder")}
        for col in ("delivered_qty", "overhead_cost", "labour_cost"):
            if col in cols:
                op.drop_column("productionorder", col)
    if bind.dialect.has_table(bind, "rateplan"):
        cols = {c["name"] for c in insp.get_columns("rateplan")}
        for col in ("overhead_per_unit", "labour_per_unit"):
            if col in cols:
                op.drop_column("rateplan", col)
