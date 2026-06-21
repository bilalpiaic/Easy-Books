"""payroll phase 2: payroll run + lines

Revision ID: 0024_payroll
Revises: 0023_employees
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_payroll"
down_revision = "0023_employees"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "payrollrun"):
        op.create_table(
            "payrollrun",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("period_start", sa.String, nullable=False),
            sa.Column("period_end", sa.String, nullable=False),
            sa.Column("pay_date", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False, server_default="draft"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("jv_number", sa.String, nullable=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "payrollline"):
        op.create_table(
            "payrollline",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("payroll_run_id", sa.Integer, nullable=False, index=True),
            sa.Column("employee_id", sa.Integer, nullable=False),
            sa.Column("gross_earnings", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_deductions", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("net_pay", sa.Numeric(18, 4), nullable=False, server_default="0"),
        )

    if not bind.dialect.has_table(bind, "payrolllinedetail"):
        op.create_table(
            "payrolllinedetail",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("payroll_line_id", sa.Integer, nullable=False, index=True),
            sa.Column("component_id", sa.Integer, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("is_override", sa.Boolean, nullable=False, server_default="0"),
        )


def downgrade():
    op.drop_table("payrolllinedetail")
    op.drop_table("payrollline")
    op.drop_table("payrollrun")
