"""Analytic dimensions + multi-slot JE analytics (#260).

Revision ID: 0061_analytic_dimensions
Revises: 0060_ifrs15_allocation
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0061_analytic_dimensions"
down_revision: Union[str, Sequence[str], None] = "0060_ifrs15_allocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "analyticdimension"):
        op.create_table(
            "analyticdimension",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.CheckConstraint(
                "sort_order >= 0 AND sort_order <= 2",
                name="ck_dimension_sort_order",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="unique_dimension_code_per_tenant"),
            sa.UniqueConstraint("tenant_id", "sort_order", name="unique_dimension_sort_per_tenant"),
        )
        op.create_index(
            op.f("ix_analyticdimension_tenant_id"),
            "analyticdimension",
            ["tenant_id"],
            unique=False,
        )

    aa_cols = {c["name"] for c in sa.inspect(bind).get_columns("analyticaccount")}
    if "dimension_id" not in aa_cols:
        with op.batch_alter_table("analyticaccount") as batch:
            batch.add_column(sa.Column("dimension_id", sa.Integer(), nullable=True))
        op.create_index(
            "ix_analyticaccount_dimension_id",
            "analyticaccount",
            ["dimension_id"],
            unique=False,
        )

    je_cols = {c["name"] for c in sa.inspect(bind).get_columns("journalentry")}
    with op.batch_alter_table("journalentry") as batch:
        if "analytic_2_id" not in je_cols:
            batch.add_column(sa.Column("analytic_2_id", sa.Integer(), nullable=True))
        if "analytic_3_id" not in je_cols:
            batch.add_column(sa.Column("analytic_3_id", sa.Integer(), nullable=True))

    for tbl in ("invoice", "bill", "paymentreceived", "billpayment", "storeissue"):
        if not bind.dialect.has_table(bind, tbl):
            continue
        cols = {c["name"] for c in sa.inspect(bind).get_columns(tbl)}
        with op.batch_alter_table(tbl) as batch:
            if "analytic_2_id" not in cols:
                batch.add_column(sa.Column("analytic_2_id", sa.Integer(), nullable=True))
            if "analytic_3_id" not in cols:
                batch.add_column(sa.Column("analytic_3_id", sa.Integer(), nullable=True))

    # Backfill: one "Cost Center" dimension per tenant that already has analytics.
    tenants = bind.execute(sa.text("SELECT DISTINCT tenant_id FROM analyticaccount")).fetchall()
    for (tenant_id,) in tenants:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM analyticdimension WHERE tenant_id = :t LIMIT 1"
            ),
            {"t": tenant_id},
        ).fetchone()
        if existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO analyticdimension (tenant_id, code, name, required, sort_order, is_active) "
                "VALUES (:t, 'CC', 'Cost Center', 0, 0, 1)"
            ),
            {"t": tenant_id},
        )
        dim_id = bind.execute(
            sa.text(
                "SELECT id FROM analyticdimension WHERE tenant_id = :t AND code = 'CC'"
            ),
            {"t": tenant_id},
        ).scalar()
        bind.execute(
            sa.text(
                "UPDATE analyticaccount SET dimension_id = :d "
                "WHERE tenant_id = :t AND dimension_id IS NULL"
            ),
            {"d": dim_id, "t": tenant_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for tbl in ("invoice", "bill", "paymentreceived", "billpayment", "storeissue", "journalentry"):
        if not bind.dialect.has_table(bind, tbl):
            continue
        cols = {c["name"] for c in sa.inspect(bind).get_columns(tbl)}
        with op.batch_alter_table(tbl) as batch:
            if "analytic_3_id" in cols:
                batch.drop_column("analytic_3_id")
            if "analytic_2_id" in cols:
                batch.drop_column("analytic_2_id")
    aa_cols = {c["name"] for c in sa.inspect(bind).get_columns("analyticaccount")}
    if "dimension_id" in aa_cols:
        op.drop_index("ix_analyticaccount_dimension_id", table_name="analyticaccount")
        with op.batch_alter_table("analyticaccount") as batch:
            batch.drop_column("dimension_id")
    if bind.dialect.has_table(bind, "analyticdimension"):
        op.drop_index(op.f("ix_analyticdimension_tenant_id"), table_name="analyticdimension")
        op.drop_table("analyticdimension")
