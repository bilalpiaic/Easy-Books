"""per-product cost_method override (IAS 2.25)

Revision ID: 0025_product_cost_method
Revises: 0024_party_links
Create Date: 2026-06-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0025_product_cost_method"
down_revision: Union[str, Sequence[str], None] = "0024_party_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    if "cost_method" not in cols:
        op.add_column("product", sa.Column("cost_method", sa.String(), nullable=True))


def downgrade() -> None:
    pass
