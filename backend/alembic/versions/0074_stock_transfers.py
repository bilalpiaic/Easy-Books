"""Stock transfers + in_transit location type (#302)

Revision ID: 0074_stock_transfers
Revises: 0073_pos_module
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0074_stock_transfers"
down_revision: Union[str, Sequence[str], None] = "0073_pos_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if not bind.dialect.has_table(bind, "stocklocation"):
        # Stub DBs used by 0068 repair tests have no locations table.
        pass
    elif dialect == "postgresql":
        op.execute("ALTER TABLE stocklocation DROP CONSTRAINT IF EXISTS ck_stock_location_type")
        op.execute(
            "ALTER TABLE stocklocation ADD CONSTRAINT ck_stock_location_type "
            "CHECK (type IN ('own','customer_custodial','wip','in_transit'))"
        )
        op.execute("ALTER TABLE stockmovement DROP CONSTRAINT IF EXISTS ck_stock_movement_direction")
        op.execute(
            "ALTER TABLE stockmovement ADD CONSTRAINT ck_stock_movement_direction "
            "CHECK (direction IN ("
            "'RECEIPT','CUSTODIAL_RECEIPT','ISSUE','CUSTODIAL_ISSUE',"
            "'COMPLETION','CUSTODIAL_COMPLETION','DELIVERY','SHIPMENT','ADJUSTMENT',"
            "'TRANSFER_OUT','TRANSFER_IN'))"
        )
    elif dialect == "sqlite":
        with op.batch_alter_table("stocklocation") as batch:
            batch.alter_column("type", existing_type=sa.String(), nullable=False)
        # SQLite CHECK recreation is unreliable via batch; app validates types.

    if not bind.dialect.has_table(bind, "stocktransfer"):
        op.create_table(
            "stocktransfer",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("number", sa.String(), nullable=False, index=True),
            sa.Column("transfer_date", sa.String(), nullable=False),
            sa.Column("from_location_id", sa.Integer(), nullable=False, index=True),
            sa.Column("to_location_id", sa.Integer(), nullable=False, index=True),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("shipped_by_id", sa.Integer(), nullable=True),
            sa.Column("shipped_at", sa.DateTime(), nullable=True),
            sa.Column("received_by_id", sa.Integer(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("cancel_reason", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_stocktransfer_status", "stocktransfer", ["status"])

    if not bind.dialect.has_table(bind, "stocktransferline"):
        op.create_table(
            "stocktransferline",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_id", sa.Integer(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("lot_no", sa.String(), nullable=True),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("stocktransferline", "stocktransfer"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
