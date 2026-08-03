"""Fixed-asset depth (#258): components, impairment, disposal GL fields.

Revision ID: 0059_fixed_asset_depth
Revises: 0058_leases_ifrs16
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0059_fixed_asset_depth"
down_revision: Union[str, Sequence[str], None] = "0058_leases_ifrs16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("fixedasset")}
    with op.batch_alter_table("fixedasset") as batch:
        if "parent_id" not in cols:
            batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        if "accum_impairment" not in cols:
            batch.add_column(
                sa.Column("accum_impairment", sa.Numeric(18, 4), server_default="0", nullable=False)
            )
        if "disposal_date" not in cols:
            batch.add_column(sa.Column("disposal_date", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        if "disposal_proceeds" not in cols:
            batch.add_column(
                sa.Column("disposal_proceeds", sa.Numeric(18, 4), server_default="0", nullable=False)
            )
        if "disposal_transaction_id" not in cols:
            batch.add_column(sa.Column("disposal_transaction_id", sa.Integer(), nullable=True))
    # Index for parent_id (SQLite-safe create after column exists)
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("fixedasset")}
    if "ix_fixedasset_parent_id" not in indexes:
        op.create_index("ix_fixedasset_parent_id", "fixedasset", ["parent_id"])

    if not bind.dialect.has_table(bind, "assetimpairment"):
        op.create_table(
            "assetimpairment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("impairment_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("recoverable_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("carrying_before", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_assetimpairment_tenant_id", "assetimpairment", ["tenant_id"])
        op.create_index("ix_assetimpairment_asset_id", "assetimpairment", ["asset_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "assetimpairment"):
        op.drop_table("assetimpairment")
    cols = {c["name"] for c in sa.inspect(bind).get_columns("fixedasset")}
    with op.batch_alter_table("fixedasset") as batch:
        for c in ("disposal_transaction_id", "disposal_proceeds", "disposal_date",
                  "accum_impairment", "parent_id"):
            if c in cols:
                batch.drop_column(c)
