"""Textile Processing module — tp_* tables + textile_processing business model.

Revision ID: 0070_textile_processing
Revises: 0069_user_permission_tenant_unique
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0070_textile_processing"
down_revision: Union[str, Sequence[str], None] = "0069_user_permission_tenant_unique"
branch_labels = None
depends_on = None

_NEW_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise',"
    "'pra_einvoice','hospital','yarn_spinning','textile_processing')"
)
_OLD_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise',"
    "'pra_einvoice','hospital','yarn_spinning')"
)

_COLS = (
    "id, name, base_currency, business_model, enabled_modules, created_at, "
    "cost_method, module_meta, plan, max_users, max_documents, storage_quota_mb, "
    "is_suspended, trial_ends_at, stripe_customer_id, stripe_subscription_id, "
    "subscription_status"
)


def _sqlite_rebuild(bind, check_expr: str) -> None:
    insp = sa.inspect(bind)
    tenant_cols = {c["name"] for c in insp.get_columns("tenant")}

    bind.execute(sa.text(f"""
        CREATE TABLE tenant_new (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            base_currency VARCHAR NOT NULL,
            business_model VARCHAR DEFAULT 'simple' NOT NULL,
            enabled_modules VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            cost_method VARCHAR NOT NULL,
            module_meta VARCHAR DEFAULT '{{}}' NOT NULL,
            plan VARCHAR NOT NULL DEFAULT 'free',
            max_users INTEGER NOT NULL DEFAULT 2,
            max_documents INTEGER NOT NULL DEFAULT 50,
            storage_quota_mb INTEGER NOT NULL DEFAULT 100,
            is_suspended BOOLEAN NOT NULL DEFAULT 0,
            trial_ends_at DATETIME,
            stripe_customer_id VARCHAR,
            stripe_subscription_id VARCHAR,
            subscription_status VARCHAR,
            PRIMARY KEY (id),
            CONSTRAINT ck_tenant_business_model CHECK ({check_expr}),
            CONSTRAINT ck_tenant_cost_method CHECK (cost_method IN ('wavg','fifo'))
        )
    """))
    copy_cols = [
        c for c in _COLS.replace("\n", "").replace(" ", "").split(",")
        if c in tenant_cols
    ]
    col_list = ", ".join(copy_cols)
    bind.execute(sa.text(f"INSERT INTO tenant_new ({col_list}) SELECT {col_list} FROM tenant"))
    bind.execute(sa.text("DROP TABLE tenant"))
    bind.execute(sa.text("ALTER TABLE tenant_new RENAME TO tenant"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_tenant_plan ON tenant (plan)"))


def _money():
    return sa.Numeric(18, 4)


def _create_if_missing(bind, name: str, cols: list) -> None:
    if bind.dialect.has_table(bind, name):
        return
    op.create_table(name, *cols)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _NEW_CHECK)
    else:
        try:
            op.drop_constraint("ck_tenant_business_model", "tenant", type_="check")
        except Exception:
            pass
        op.create_check_constraint("ck_tenant_business_model", "tenant", _NEW_CHECK)

    m = _money()
    _create_if_missing(bind, "tp_quality", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("code", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("blend", sa.String, nullable=True),
        sa.Column("width", sa.String, nullable=True),
        sa.Column("unit", sa.String, nullable=False, server_default="MTR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tp_quality_code"),
    ])
    _create_if_missing(bind, "tp_process", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("seq", sa.Integer, nullable=False, server_default="0", index=True),
        sa.Column("code", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("is_billing", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("default_sale_rate", m, nullable=False, server_default="0"),
        sa.Column("contractor_expense_account_id", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tp_process_code"),
    ])
    _create_if_missing(bind, "tp_contractor", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("code", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("vendor_id", sa.Integer, nullable=False, index=True),
        sa.Column("default_process_id", sa.Integer, nullable=True),
        sa.Column("phone", sa.String, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tp_contractor_code"),
    ])
    _create_if_missing(bind, "tp_sales_order", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("expected_mtr", m, nullable=False, server_default="0"),
        sa.Column("grey_rate", m, nullable=False, server_default="0"),
        sa.Column("process_rates", sa.JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="open", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_sales_order_number"),
    ])
    _create_if_missing(bind, "tp_grey_lot", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("sales_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("godown_location_id", sa.Integer, nullable=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("received_mtr", m, nullable=False, server_default="0"),
        sa.Column("than_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ready_mtr", m, nullable=False, server_default="0"),
        sa.Column("rejection_mtr", m, nullable=False, server_default="0"),
        sa.Column("visible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("invisible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("dispatched_mtr", m, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="received", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_grey_lot_number"),
    ])
    _create_if_missing(bind, "tp_grey_than", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("than_no", sa.String, nullable=False),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("width", sa.String, nullable=True),
        sa.Column("notes", sa.String, nullable=True),
    ])
    _create_if_missing(bind, "tp_kachi_parchi", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("than_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_kachi_parchi_number"),
    ])
    _create_if_missing(bind, "tp_mending", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("grey_mtr", m, nullable=False, server_default="0"),
        sa.Column("l_kami_mtr", m, nullable=False, server_default="0"),
        sa.Column("rejection_mtr", m, nullable=False, server_default="0"),
        sa.Column("safai_mtr", m, nullable=False, server_default="0"),
        sa.Column("ready_mtr", m, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_mending_number"),
        sa.UniqueConstraint("tenant_id", "lot_id", name="uq_tp_mending_lot"),
    ])
    _create_if_missing(bind, "tp_pakki_parchi", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("mending_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("than_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_pakki_parchi_number"),
        sa.UniqueConstraint("tenant_id", "lot_id", name="uq_tp_pakki_parchi_lot"),
    ])
    _create_if_missing(bind, "tp_rejection_issue_note", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("mending_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("issued_mtr", m, nullable=False, server_default="0"),
        sa.Column("lifted_mtr", m, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="issued", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_rej_note_number"),
        sa.UniqueConstraint("tenant_id", "lot_id", name="uq_tp_rej_note_lot"),
    ])
    _create_if_missing(bind, "tp_rejection_ogp", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("rejection_issue_note_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("qty_mtr", m, nullable=False, server_default="0"),
        sa.Column("vehicle", sa.String, nullable=True),
        sa.Column("challan", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="posted", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_rej_ogp_number"),
    ])
    _create_if_missing(bind, "tp_production_order", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("sales_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("issued_mtr", m, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_prod_order_number"),
        sa.UniqueConstraint("tenant_id", "lot_id", name="uq_tp_prod_order_lot"),
    ])
    _create_if_missing(bind, "tp_stage_entry", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("production_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("process_id", sa.Integer, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("quality_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("input_mtr", m, nullable=False, server_default="0"),
        sa.Column("output_mtr", m, nullable=False, server_default="0"),
        sa.Column("visible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("invisible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("rejection_mtr", m, nullable=False, server_default="0"),
        sa.Column("contractor_id", sa.Integer, nullable=True),
        sa.Column("labor_qty", m, nullable=False, server_default="0"),
        sa.Column("labor_rate", m, nullable=False, server_default="0"),
        sa.Column("labor_amount", m, nullable=False, server_default="0"),
        sa.Column("started_at", sa.String, nullable=True),
        sa.Column("ended_at", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_stage_entry_number"),
    ])
    _create_if_missing(bind, "tp_packing", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("production_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("pieces", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_packing_number"),
    ])
    _create_if_missing(bind, "tp_baling", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("production_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("bale_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_baling_number"),
    ])
    _create_if_missing(bind, "tp_dispatch", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("production_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("sales_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("meters", m, nullable=False, server_default="0"),
        sa.Column("vehicle", sa.String, nullable=True),
        sa.Column("challan", sa.String, nullable=True),
        sa.Column("invoice_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_dispatch_number"),
    ])
    _create_if_missing(bind, "tp_grey_settlement", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("lot_id", sa.Integer, nullable=False, index=True),
        sa.Column("sales_order_id", sa.Integer, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("total_grey_received", m, nullable=False, server_default="0"),
        sa.Column("fresh_dispatch_mtr", m, nullable=False, server_default="0"),
        sa.Column("visible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("invisible_wastage_mtr", m, nullable=False, server_default="0"),
        sa.Column("credit_qty_mtr", m, nullable=False, server_default="0"),
        sa.Column("grey_rate", m, nullable=False, server_default="0"),
        sa.Column("credit_value", m, nullable=False, server_default="0"),
        sa.Column("credit_note_id", sa.Integer, nullable=True),
        sa.Column("wastage_invoice_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_grey_settlement_number"),
        sa.UniqueConstraint("tenant_id", "lot_id", name="uq_tp_grey_settlement_lot"),
    ])
    _create_if_missing(bind, "tp_labor_bill", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("contractor_id", sa.Integer, nullable=False, index=True),
        sa.Column("vendor_id", sa.Integer, nullable=False, index=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("stage_entry_ids", sa.JSON, nullable=False),
        sa.Column("labor_amount", m, nullable=False, server_default="0"),
        sa.Column("bill_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_labor_bill_number"),
    ])
    _create_if_missing(bind, "tp_inspection", [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("number", sa.String, nullable=False, index=True),
        sa.Column("gate_inward_id", sa.Integer, nullable=False, index=True),
        sa.Column("production_order_id", sa.Integer, nullable=True),
        sa.Column("date", sa.String, nullable=False, index=True),
        sa.Column("accepted_qty", m, nullable=False, server_default="0"),
        sa.Column("rejected_qty", m, nullable=False, server_default="0"),
        sa.Column("hold_qty", m, nullable=False, server_default="0"),
        sa.Column("status", sa.String, nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "number", name="uq_tp_inspection_number"),
    ])


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "tp_inspection", "tp_labor_bill", "tp_grey_settlement", "tp_dispatch",
        "tp_baling", "tp_packing", "tp_stage_entry", "tp_production_order",
        "tp_rejection_ogp", "tp_rejection_issue_note", "tp_pakki_parchi",
        "tp_mending", "tp_kachi_parchi", "tp_grey_than", "tp_grey_lot",
        "tp_sales_order", "tp_contractor", "tp_process", "tp_quality",
    ):
        if bind.dialect.has_table(bind, name):
            op.drop_table(name)
    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _OLD_CHECK)
    else:
        try:
            op.drop_constraint("ck_tenant_business_model", "tenant", type_="check")
        except Exception:
            pass
        op.create_check_constraint("ck_tenant_business_model", "tenant", _OLD_CHECK)
