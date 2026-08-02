"""IFRS 16 lease contracts + schedule (#256).

Revision ID: 0058_leases_ifrs16
Revises: 0057_consolidation
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0058_leases_ifrs16"
down_revision: Union[str, Sequence[str], None] = "0057_consolidation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "leasecontract"):
        op.create_table(
            "leasecontract",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("number", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("lessor", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("commencement_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("term_months", sa.Integer(), nullable=False),
            sa.Column("payment_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("annual_discount_rate", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("payment_timing", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("initial_direct_costs", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("present_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("rou_cost", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("liability_opening", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("accumulated_depreciation", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("liability_carrying", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("rou_account_id", sa.Integer(), nullable=True),
            sa.Column("accum_depr_account_id", sa.Integer(), nullable=True),
            sa.Column("depr_expense_account_id", sa.Integer(), nullable=True),
            sa.Column("liability_account_id", sa.Integer(), nullable=True),
            sa.Column("interest_expense_account_id", sa.Integer(), nullable=True),
            sa.Column("payment_account_id", sa.Integer(), nullable=True),
            sa.Column("initial_transaction_id", sa.Integer(), nullable=True),
            sa.Column("terminated_at", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("termination_transaction_id", sa.Integer(), nullable=True),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_lease_number_per_tenant"),
            sa.CheckConstraint(
                "status IN ('draft','active','terminated')",
                name="ck_lease_status",
            ),
            sa.CheckConstraint(
                "payment_timing IN ('arrears','advance')",
                name="ck_lease_payment_timing",
            ),
        )
        op.create_index("ix_leasecontract_tenant_id", "leasecontract", ["tenant_id"])
        op.create_index("ix_leasecontract_number", "leasecontract", ["number"])
        op.create_index("ix_leasecontract_status", "leasecontract", ["status"])

    if not bind.dialect.has_table(bind, "leasescheduleline"):
        op.create_table(
            "leasescheduleline",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("lease_id", sa.Integer(), nullable=False),
            sa.Column("period_index", sa.Integer(), nullable=False),
            sa.Column("period_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("opening_liability", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("interest", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("payment", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("principal", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("closing_liability", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("depreciation", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("interest_transaction_id", sa.Integer(), nullable=True),
            sa.Column("payment_transaction_id", sa.Integer(), nullable=True),
            sa.Column("depr_transaction_id", sa.Integer(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("lease_id", "period_index", name="uq_lease_schedule_period"),
            sa.CheckConstraint(
                "status IN ('pending','posted')",
                name="ck_lease_schedule_status",
            ),
        )
        op.create_index("ix_leasescheduleline_tenant_id", "leasescheduleline", ["tenant_id"])
        op.create_index("ix_leasescheduleline_lease_id", "leasescheduleline", ["lease_id"])
        op.create_index("ix_leasescheduleline_status", "leasescheduleline", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("leasescheduleline", "leasecontract"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
