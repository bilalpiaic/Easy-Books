"""attendance register

Revision ID: 0025_attendance
Revises: 0024_payroll
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_attendance"
down_revision = "0024_payroll"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "attendancerecord"):
        op.create_table(
            "attendancerecord",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("employee_id", sa.Integer, nullable=False, index=True),
            sa.Column("date", sa.String, nullable=False),
            sa.Column("time_in", sa.String, nullable=True),
            sa.Column("time_out", sa.String, nullable=True),
            sa.Column("hours_worked", sa.Numeric(5, 2), nullable=True),
            sa.Column("status", sa.String, nullable=False, server_default="present"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("source", sa.String, nullable=False, server_default="manual"),
            sa.Column("raw_data", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )


def downgrade():
    op.drop_table("attendancerecord")
