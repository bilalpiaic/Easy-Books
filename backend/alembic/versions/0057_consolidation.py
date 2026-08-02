"""Multi-entity consolidation tables (#255).

Revision ID: 0057_consolidation
Revises: 0056_close_audit
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0057_consolidation"
down_revision: Union[str, Sequence[str], None] = "0056_close_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "consolidationmember"):
        op.create_table(
            "consolidationmember",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("holding_tenant_id", sa.Integer(), nullable=False),
            sa.Column("member_tenant_id", sa.Integer(), nullable=False),
            sa.Column("relationship", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("ownership_pct", sa.Numeric(18, 2), nullable=False, server_default="100"),
            sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("ic_ar_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("ic_ap_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("holding_tenant_id", "member_tenant_id", name="uq_consol_member"),
            sa.CheckConstraint(
                "relationship IN ('parent','subsidiary','associate')",
                name="ck_consol_member_relationship",
            ),
        )
        op.create_index("ix_consolidationmember_holding_tenant_id", "consolidationmember", ["holding_tenant_id"])
        op.create_index("ix_consolidationmember_member_tenant_id", "consolidationmember", ["member_tenant_id"])
        op.create_index("ix_consolidationmember_relationship", "consolidationmember", ["relationship"])

    if not bind.dialect.has_table(bind, "consolidationrun"):
        op.create_table(
            "consolidationrun",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("holding_tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("period_start", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("period_end", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("package_json", sa.JSON(), nullable=True),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("posted_by_id", sa.Integer(), nullable=True),
            sa.Column("voided_at", sa.DateTime(), nullable=True),
            sa.Column("voided_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "status IN ('draft','posted','void')",
                name="ck_consol_run_status",
            ),
        )
        op.create_index("ix_consolidationrun_holding_tenant_id", "consolidationrun", ["holding_tenant_id"])
        op.create_index("ix_consolidationrun_status", "consolidationrun", ["status"])

    if not bind.dialect.has_table(bind, "consolidationelimination"):
        op.create_table(
            "consolidationelimination",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("holding_tenant_id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("account_code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("account_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("account_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("member_tenant_id", sa.Integer(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "kind IN ('ic_balance','ic_sales','unrealised_stock','nci','manual')",
                name="ck_consol_elim_kind",
            ),
        )
        op.create_index("ix_consolidationelimination_holding_tenant_id", "consolidationelimination", ["holding_tenant_id"])
        op.create_index("ix_consolidationelimination_run_id", "consolidationelimination", ["run_id"])
        op.create_index("ix_consolidationelimination_kind", "consolidationelimination", ["kind"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("consolidationelimination", "consolidationrun", "consolidationmember"):
        if bind.dialect.has_table(bind, table):
            op.drop_table(table)
