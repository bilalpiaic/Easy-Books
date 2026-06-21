"""payroll phase 1: employee + salary component tables

Revision ID: 0023_employees
Revises: 0022_promo_rules
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "0023_employees"
down_revision = "0025_product_cost_method"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "employee"):
        op.create_table(
            "employee",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("employee_code", sa.String, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("department", sa.String, nullable=True),
            sa.Column("designation", sa.String, nullable=True),
            sa.Column("join_date", sa.String, nullable=True),
            sa.Column("cnic", sa.String, nullable=True),
            sa.Column("bank_account", sa.String, nullable=True),
            sa.Column("bank_name", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )

    if not bind.dialect.has_table(bind, "salarycomponent"):
        op.create_table(
            "salarycomponent",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("code", sa.String, nullable=False),
            sa.Column("component_type", sa.String, nullable=False),
            sa.Column("is_taxable", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("is_fixed", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("gl_account_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        )

    if not bind.dialect.has_table(bind, "employeesalarystructure"):
        op.create_table(
            "employeesalarystructure",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("employee_id", sa.Integer, nullable=False, index=True),
            sa.Column("component_id", sa.Integer, nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("pct_of_basic", sa.Numeric(5, 2), nullable=True),
            sa.Column("effective_from", sa.String, nullable=True),
            sa.Column("effective_to", sa.String, nullable=True),
        )


def downgrade():
    op.drop_table("employeesalarystructure")
    op.drop_table("salarycomponent")
    op.drop_table("employee")
