"""PLC shop-floor device registry + mill event log.

Revision ID: 0090_plc_shop_floor
Revises: 0089_pra_di_v112
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0090_plc_shop_floor"
down_revision: Union[str, Sequence[str], None] = "0089_pra_di_v112"
branch_labels = None
depends_on = None


def _add(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "plc_device"):
        op.create_table(
            "plc_device",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("protocol", sa.String, nullable=False, server_default="http_gateway"),
            sa.Column("event_type", sa.String, nullable=False, index=True),
            sa.Column("binding", sa.JSON, nullable=False),
            sa.Column("auto_apply", sa.Boolean, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("last_seen_at", sa.DateTime, nullable=True),
            sa.Column("last_error", sa.String, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "code", name="uq_plc_device_code"),
        )
    if not bind.dialect.has_table(bind, "plc_event"):
        op.create_table(
            "plc_event",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("device_id", sa.Integer, nullable=True, index=True),
            sa.Column("idempotency_key", sa.String, nullable=False, index=True),
            sa.Column("event_type", sa.String, nullable=False, index=True),
            sa.Column("machine_code", sa.String, nullable=False, index=True),
            sa.Column("occurred_at", sa.DateTime, nullable=True),
            sa.Column("received_at", sa.DateTime, nullable=False, index=True),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("status", sa.String, nullable=False, server_default="received", index=True),
            sa.Column("result_doc_type", sa.String, nullable=True),
            sa.Column("result_doc_id", sa.Integer, nullable=True),
            sa.Column("result_number", sa.String, nullable=True),
            sa.Column("error_message", sa.String, nullable=True),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_plc_event_idem"),
        )

    for table in ("wv_production", "sp_stage_entry", "sp_cone_output", "tp_stage_entry", "wb_ticket"):
        if bind.dialect.has_table(bind, table):
            _add(table, "source", sa.Column("source", sa.String(), nullable=True, server_default="manual"))
            _add(table, "plc_event_id", sa.Column("plc_event_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("wv_production", "sp_stage_entry", "sp_cone_output", "tp_stage_entry", "wb_ticket"):
        if bind.dialect.has_table(bind, table):
            cols = {c["name"] for c in inspect(bind).get_columns(table)}
            if "plc_event_id" in cols:
                op.drop_column(table, "plc_event_id")
            if "source" in cols:
                op.drop_column(table, "source")
    if bind.dialect.has_table(bind, "plc_event"):
        op.drop_table("plc_event")
    if bind.dialect.has_table(bind, "plc_device"):
        op.drop_table("plc_device")
