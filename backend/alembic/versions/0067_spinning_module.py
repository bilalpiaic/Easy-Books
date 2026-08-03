"""Yarn Spinning module — sp_* tables + yarn_spinning business model.

Revision ID: 0067_spinning_module
Revises: 0066_wht_cit
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0067_spinning_module"
down_revision: Union[str, Sequence[str], None] = "0066_wht_cit"
branch_labels = None
depends_on = None

_NEW_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise',"
    "'pra_einvoice','hospital','yarn_spinning')"
)
_OLD_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise',"
    "'pra_einvoice','hospital')"
)

_COLS = (
    "id, name, base_currency, business_model, enabled_modules, created_at, "
    "cost_method, module_meta, is_suspended"
)


def _sqlite_rebuild(bind, check_expr: str) -> None:
    insp = sa.inspect(bind)
    tenant_cols = {c["name"] for c in insp.get_columns("tenant")}
    suspended = ", is_suspended BOOLEAN NOT NULL DEFAULT 0" if "is_suspended" in tenant_cols else ""
    bind.execute(sa.text(f"""
        CREATE TABLE tenant_new (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            base_currency VARCHAR NOT NULL,
            business_model VARCHAR DEFAULT 'simple' NOT NULL,
            enabled_modules VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            cost_method VARCHAR NOT NULL,
            module_meta VARCHAR DEFAULT '{{}}' NOT NULL
            {suspended},
            PRIMARY KEY (id),
            CONSTRAINT ck_tenant_business_model CHECK ({check_expr}),
            CONSTRAINT ck_tenant_cost_method CHECK (cost_method IN ('wavg','fifo'))
        )
    """))
    sel_cols = _COLS if "is_suspended" in tenant_cols else _COLS.replace(", is_suspended", "")
    bind.execute(sa.text(f"INSERT INTO tenant_new ({sel_cols}) SELECT {sel_cols} FROM tenant"))
    bind.execute(sa.text("DROP TABLE tenant"))
    bind.execute(sa.text("ALTER TABLE tenant_new RENAME TO tenant"))


def _money():
    return sa.Numeric(18, 4)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _NEW_CHECK)

    tables = {
        "sp_yarn_spec": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("count_ne", _money(), nullable=True),
            sa.Column("count_nm", _money(), nullable=True),
            sa.Column("twist_direction", sa.String, nullable=True),
            sa.Column("blend_cotton_pct", _money(), nullable=False, server_default="0"),
            sa.Column("blend_poly_pct", _money(), nullable=False, server_default="0"),
            sa.Column("output_product_id", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_yarn_spec_code"),
        ],
        "sp_fiber_grade": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("staple_mm", _money(), nullable=True),
            sa.Column("micronaire", _money(), nullable=True),
            sa.Column("grade", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_fiber_grade_code"),
        ],
        "sp_machine": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("machine_type", sa.String, nullable=True),
            sa.Column("spindle_count", sa.Integer, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_machine_code"),
        ],
        "sp_shift": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("start_time", sa.String, nullable=True),
            sa.Column("end_time", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_shift_code"),
        ],
        "sp_operator": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("phone", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_operator_code"),
        ],
        "sp_waste_type": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("code", sa.String, nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("gl_account_code", sa.String, nullable=False, server_default="5901"),
            sa.Column("default_stage", sa.String, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sp_waste_type_code"),
        ],
        "sp_recipe": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("yarn_spec_id", sa.Integer, nullable=False, index=True),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("tenant_id", "yarn_spec_id", "version", name="uq_sp_recipe_version"),
        ],
        "sp_recipe_line": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("recipe_id", sa.Integer, nullable=False, index=True),
            sa.Column("product_id", sa.Integer, nullable=False, index=True),
            sa.Column("qty_per_100kg_output", _money(), nullable=False, server_default="0"),
            sa.Column("stage", sa.String, nullable=True),
        ],
        "sp_production_plan": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("plan_date", sa.String, nullable=False, index=True),
            sa.Column("yarn_spec_id", sa.Integer, nullable=False, index=True),
            sa.Column("customer_id", sa.Integer, nullable=True),
            sa.Column("target_kg", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_production_plan_number"),
        ],
        "sp_spin_lot": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("yarn_spec_id", sa.Integer, nullable=False, index=True),
            sa.Column("recipe_id", sa.Integer, nullable=True),
            sa.Column("plan_id", sa.Integer, nullable=True),
            sa.Column("customer_id", sa.Integer, nullable=True),
            sa.Column("start_date", sa.String, nullable=False, index=True),
            sa.Column("target_output_kg", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("material_cost", _money(), nullable=False, server_default="0"),
            sa.Column("labour_cost", _money(), nullable=False, server_default="0"),
            sa.Column("overhead_cost", _money(), nullable=False, server_default="0"),
            sa.Column("waste_cost", _money(), nullable=False, server_default="0"),
            sa.Column("total_cost", _money(), nullable=False, server_default="0"),
            sa.Column("cost_per_kg", _money(), nullable=False, server_default="0"),
            sa.Column("output_kg", _money(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("started_at", sa.DateTime, nullable=True),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            sa.Column("closed_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_spin_lot_number"),
        ],
        "sp_bale_receipt": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("vendor_id", sa.Integer, nullable=True),
            sa.Column("bill_id", sa.Integer, nullable=True),
            sa.Column("gate_inward_id", sa.Integer, nullable=True),
            sa.Column("product_id", sa.Integer, nullable=False, index=True),
            sa.Column("spin_lot_id", sa.Integer, nullable=True, index=True),
            sa.Column("fiber_grade_id", sa.Integer, nullable=True),
            sa.Column("lot_no", sa.String, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("gross_kg", _money(), nullable=False, server_default="0"),
            sa.Column("tare_kg", _money(), nullable=False, server_default="0"),
            sa.Column("net_kg", _money(), nullable=False, server_default="0"),
            sa.Column("moisture_pct", _money(), nullable=False, server_default="0"),
            sa.Column("rate_per_kg", _money(), nullable=False, server_default="0"),
            sa.Column("total_value", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_bale_receipt_number"),
        ],
        "sp_stage_entry": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("spin_lot_id", sa.Integer, nullable=False, index=True),
            sa.Column("stage", sa.String, nullable=False, index=True),
            sa.Column("machine_id", sa.Integer, nullable=True),
            sa.Column("shift_id", sa.Integer, nullable=True),
            sa.Column("operator_id", sa.Integer, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("input_kg", _money(), nullable=False, server_default="0"),
            sa.Column("output_kg", _money(), nullable=False, server_default="0"),
            sa.Column("waste_kg", _money(), nullable=False, server_default="0"),
            sa.Column("yield_pct", _money(), nullable=False, server_default="0"),
            sa.Column("labour_cost", _money(), nullable=False, server_default="0"),
            sa.Column("overhead_cost", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_stage_entry_number"),
        ],
        "sp_cone_output": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("spin_lot_id", sa.Integer, nullable=False, index=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("cones_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("net_kg", _money(), nullable=False, server_default="0"),
            sa.Column("quality_grade", sa.String, nullable=True),
            sa.Column("lot_no", sa.String, nullable=True),
            sa.Column("machine_id", sa.Integer, nullable=True),
            sa.Column("shift_id", sa.Integer, nullable=True),
            sa.Column("operator_id", sa.Integer, nullable=True),
            sa.Column("unit_cost", _money(), nullable=False, server_default="0"),
            sa.Column("total_cost", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_cone_output_number"),
        ],
        "sp_waste_log": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("spin_lot_id", sa.Integer, nullable=False, index=True),
            sa.Column("stage", sa.String, nullable=False, index=True),
            sa.Column("waste_type_id", sa.Integer, nullable=False, index=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("qty_kg", _money(), nullable=False, server_default="0"),
            sa.Column("cost_value", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_waste_log_number"),
        ],
        "sp_yarn_dispatch": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("number", sa.String, nullable=False, index=True),
            sa.Column("customer_id", sa.Integer, nullable=False, index=True),
            sa.Column("yarn_spec_id", sa.Integer, nullable=False, index=True),
            sa.Column("product_id", sa.Integer, nullable=True),
            sa.Column("invoice_id", sa.Integer, nullable=True),
            sa.Column("date", sa.String, nullable=False, index=True),
            sa.Column("cones_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("net_kg", _money(), nullable=False, server_default="0"),
            sa.Column("rate_per_kg", _money(), nullable=False, server_default="0"),
            sa.Column("dispatch_value", _money(), nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
            sa.Column("transaction_id", sa.Integer, nullable=True),
            sa.Column("notes", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
            sa.UniqueConstraint("tenant_id", "number", name="uq_sp_yarn_dispatch_number"),
        ],
        "sp_calc_run": [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("spin_lot_id", sa.Integer, nullable=True, index=True),
            sa.Column("calc_type", sa.String, nullable=False, index=True),
            sa.Column("inputs", sa.JSON, nullable=False),
            sa.Column("outputs", sa.JSON, nullable=False),
            sa.Column("override_reason", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_id", sa.Integer, nullable=True),
        ],
    }

    for tname, cols in tables.items():
        if not bind.dialect.has_table(bind, tname):
            op.create_table(tname, *cols)


def downgrade() -> None:
    bind = op.get_bind()
    for t in reversed(list((
        "sp_calc_run", "sp_yarn_dispatch", "sp_waste_log", "sp_cone_output",
        "sp_stage_entry", "sp_bale_receipt", "sp_spin_lot", "sp_production_plan",
        "sp_recipe_line", "sp_recipe", "sp_waste_type", "sp_operator", "sp_shift",
        "sp_machine", "sp_fiber_grade", "sp_yarn_spec",
    ))):
        if bind.dialect.has_table(bind, t):
            op.drop_table(t)
    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _OLD_CHECK)
