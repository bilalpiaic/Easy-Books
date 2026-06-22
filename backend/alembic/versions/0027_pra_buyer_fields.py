"""add buyer_ntn and buyer_cnic to invoice

Revision ID: 0027_pra_buyer_fields
Revises: d42ac2e7674d
Branch labels: None
Depends on: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_pra_buyer_fields"
down_revision = "d42ac2e7674d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    if "buyer_ntn" not in inv_cols:
        op.add_column("invoice", sa.Column("buyer_ntn", sa.String(), nullable=True))
    if "buyer_cnic" not in inv_cols:
        op.add_column("invoice", sa.Column("buyer_cnic", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoice", "buyer_cnic")
    op.drop_column("invoice", "buyer_ntn")
