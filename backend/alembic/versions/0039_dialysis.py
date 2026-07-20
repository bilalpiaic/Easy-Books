"""Dialysis Treatment Unit — machines, shifts, sessions

Revision ID: 0039_dialysis
Revises: 0038_user_alerts
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_dialysis"
down_revision = "0038_user_alerts"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "hc_dialysis_unit"):
        op.create_table(
            "hc_dialysis_unit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False, server_default="Dialysis Treatment Unit"),
            sa.Column("open_time", sa.String(), nullable=False, server_default="08:00"),
            sa.Column("close_time", sa.String(), nullable=False, server_default="20:00"),
            sa.Column("shift_hours", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not bind.dialect.has_table(bind, "hc_dialysis_machine"):
        op.create_table(
            "hc_dialysis_machine",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("unit_id", sa.Integer(), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="available"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_hc_dialysis_machine_code"),
        )

    if not bind.dialect.has_table(bind, "hc_dialysis_shift"):
        op.create_table(
            "hc_dialysis_shift",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("unit_id", sa.Integer(), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("start_time", sa.String(), nullable=False),
            sa.Column("end_time", sa.String(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.UniqueConstraint("tenant_id", "unit_id", "code", name="uq_hc_dialysis_shift_code"),
        )

    if not bind.dialect.has_table(bind, "hc_dialysis_session"):
        op.create_table(
            "hc_dialysis_session",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("session_number", sa.String(), nullable=False, index=True),
            sa.Column("patient_id", sa.Integer(), nullable=False, index=True),
            sa.Column("doctor_id", sa.Integer(), nullable=True),
            sa.Column("machine_id", sa.Integer(), nullable=False, index=True),
            sa.Column("shift_id", sa.Integer(), nullable=False, index=True),
            sa.Column("session_date", sa.String(), nullable=False, index=True),
            sa.Column("status", sa.String(), nullable=False, server_default="scheduled"),
            sa.Column("fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("procedure_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.UniqueConstraint("tenant_id", "session_number", name="uq_hc_dialysis_session_number"),
        )


def downgrade():
    bind = op.get_bind()
    for table in (
        "hc_dialysis_session",
        "hc_dialysis_shift",
        "hc_dialysis_machine",
        "hc_dialysis_unit",
    ):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
