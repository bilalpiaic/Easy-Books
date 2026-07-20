"""weaving calculators — planned yarn fields + calc history (#196)

Revision ID: 0037_weaving_calculators
Revises: 0036_weaving
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_weaving_calculators"
down_revision = "0036_weaving"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if bind.dialect.has_table(bind, "wv_yarn_type"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("wv_yarn_type")}
        if "count_ne" not in cols:
            op.add_column("wv_yarn_type", sa.Column("count_ne", sa.Numeric(18, 4), nullable=True))

    if bind.dialect.has_table(bind, "wv_contract"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("wv_contract")}
        for name in (
            "planned_warp_kg",
            "planned_weft_kg",
            "planned_total_yarn_kg",
            "warp_count_ne",
            "weft_count_ne",
            "last_calc_at",
        ):
            if name not in cols:
                if name == "last_calc_at":
                    op.add_column("wv_contract", sa.Column(name, sa.DateTime(), nullable=True))
                else:
                    op.add_column("wv_contract", sa.Column(name, sa.Numeric(18, 4), nullable=True))

    if not bind.dialect.has_table(bind, "wv_calc_run"):
        op.create_table(
            "wv_calc_run",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("contract_id", sa.Integer, nullable=False, index=True),
            sa.Column("calc_type", sa.String, nullable=False, index=True),
            sa.Column("inputs", sa.JSON, nullable=False),
            sa.Column("outputs", sa.JSON, nullable=False),
            sa.Column("override_reason", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "wv_calc_run"):
        op.drop_table("wv_calc_run")
