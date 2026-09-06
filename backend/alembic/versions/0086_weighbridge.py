"""weighbridge mill workspace — wb_ticket (#391)

Revision ID: 0086_weighbridge
Revises: 0085_hot_path_indexes
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0086_weighbridge"
down_revision: Union[str, Sequence[str], None] = "0085_hot_path_indexes"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "wb_ticket"):
        return
    op.create_table(
        "wb_ticket",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("ticket_date", sa.String, nullable=False, index=True),
        sa.Column("direction", sa.String, nullable=False, server_default="inbound", index=True),
        sa.Column("vehicle_no", sa.String, nullable=False),
        sa.Column("driver_name", sa.String, nullable=True),
        sa.Column("party_type", sa.String, nullable=False, server_default="other"),
        sa.Column("party_id", sa.Integer, nullable=True, index=True),
        sa.Column("party_name", sa.String, nullable=True),
        sa.Column("commodity", sa.String, nullable=True),
        sa.Column("lot_ref", sa.String, nullable=True),
        sa.Column("gross_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("tare_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_kg", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("first_weigh_kind", sa.String, nullable=True),
        sa.Column("first_weigh_at", sa.DateTime, nullable=True),
        sa.Column("second_weigh_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("operator_id", sa.Integer, nullable=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("po_id", sa.Integer, nullable=True),
        sa.Column("gate_inward_id", sa.Integer, nullable=True),
        sa.Column("invoice_id", sa.Integer, nullable=True),
        sa.Column("sp_bale_receipt_id", sa.Integer, nullable=True),
        sa.Column("cancel_reason", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_wb_ticket_number"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "wb_ticket"):
        op.drop_table("wb_ticket")
