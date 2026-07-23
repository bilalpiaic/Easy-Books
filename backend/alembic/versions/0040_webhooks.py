"""webhook endpoints + delivery outbox (#114)

Revision ID: 0040_webhooks
Revises: 0039_dialysis
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0040_webhooks"
down_revision: Union[str, Sequence[str], None] = "0039_dialysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Guarded: dev still bootstraps via SQLModel.metadata.create_all(), so a
    # fresh DB already has these tables when the migration runs.
    if not bind.dialect.has_table(bind, "webhookendpoint"):
        op.create_table(
            "webhookendpoint",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("secret", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("events", sa.JSON(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_webhookendpoint_tenant_id"), "webhookendpoint", ["tenant_id"], unique=False)

    if not bind.dialect.has_table(bind, "webhookdelivery"):
        op.create_table(
            "webhookdelivery",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("endpoint_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("payload_json", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("next_retry", sa.DateTime(), nullable=True),
            sa.Column("response_code", sa.Integer(), nullable=True),
            sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.ForeignKeyConstraint(["endpoint_id"], ["webhookendpoint.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_webhookdelivery_tenant_id"), "webhookdelivery", ["tenant_id"], unique=False)
        op.create_index(op.f("ix_webhookdelivery_endpoint_id"), "webhookdelivery", ["endpoint_id"], unique=False)
        op.create_index(op.f("ix_webhookdelivery_event_type"), "webhookdelivery", ["event_type"], unique=False)
        op.create_index(op.f("ix_webhookdelivery_status"), "webhookdelivery", ["status"], unique=False)
        op.create_index(op.f("ix_webhookdelivery_next_retry"), "webhookdelivery", ["next_retry"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "webhookdelivery"):
        op.drop_table("webhookdelivery")
    if bind.dialect.has_table(bind, "webhookendpoint"):
        op.drop_table("webhookendpoint")
