"""Telecom franchise: TrackerAccount, TrackerTransaction, RSOAgent,
RetailOutlet, LoadTransfer, SimBatch, SimActivation, RSODailyCollection,
FCAEvent, KPITarget tables + telecom_franchise added to tenant CHECK.

Revision ID: 0014_telecom_franchise
Revises: 0013_grn_production_order
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_telecom_franchise"
down_revision = "0013_grn_production_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # ------------------------------------------------------------------
    # tracker_account
    # ------------------------------------------------------------------
    if "tracker_account" not in tables:
        op.create_table(
            "tracker_account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("operator_name", sa.String(), nullable=False),
            sa.Column("operator_code", sa.String(), nullable=False),
            sa.Column("account_reference", sa.String(), nullable=False),
            sa.Column("deposit_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("load_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("deposit_account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
            sa.Column("load_account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "account_reference", name="uq_tracker_account_ref"),
        )
        op.create_index("ix_tracker_account_tenant_id", "tracker_account", ["tenant_id"])

    # ------------------------------------------------------------------
    # tracker_transaction
    # ------------------------------------------------------------------
    if "tracker_transaction" not in tables:
        op.create_table(
            "tracker_transaction",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("tracker_account_id", sa.Integer(), sa.ForeignKey("tracker_account.id"), nullable=False),
            sa.Column("txn_date", sa.String(), nullable=False),
            sa.Column("txn_type", sa.String(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("load_disbursed", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("commission_earned", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("tracker_reference", sa.String(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("is_reconciled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "txn_type IN ('deposit','load_order','stock_debit',"
                "'commission_credit','penalty_debit','adjustment')",
                name="ck_tracker_txn_type",
            ),
            sa.CheckConstraint("amount > 0", name="ck_tracker_txn_amount_positive"),
        )
        op.create_index("ix_tracker_transaction_tenant_id", "tracker_transaction", ["tenant_id"])
        op.create_index("ix_tracker_transaction_account_id", "tracker_transaction", ["tracker_account_id"])

    # ------------------------------------------------------------------
    # rso_agent
    # ------------------------------------------------------------------
    if "rso_agent" not in tables:
        op.create_table(
            "rso_agent",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("phone", sa.String(), nullable=False),
            sa.Column("cnic", sa.String(), nullable=False),
            sa.Column("territory", sa.String(), nullable=True),
            sa.Column("receivable_account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "cnic", name="uq_rso_agent_cnic"),
        )
        op.create_index("ix_rso_agent_tenant_id", "rso_agent", ["tenant_id"])

    # ------------------------------------------------------------------
    # retail_outlet
    # ------------------------------------------------------------------
    if "retail_outlet" not in tables:
        op.create_table(
            "retail_outlet",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("rso_id", sa.Integer(), sa.ForeignKey("rso_agent.id"), nullable=False),
            sa.Column("shop_name", sa.String(), nullable=False),
            sa.Column("owner_name", sa.String(), nullable=True),
            sa.Column("phone", sa.String(), nullable=True),
            sa.Column("address", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_retail_outlet_tenant_id", "retail_outlet", ["tenant_id"])
        op.create_index("ix_retail_outlet_rso_id", "retail_outlet", ["rso_id"])

    # ------------------------------------------------------------------
    # load_transfer
    # ------------------------------------------------------------------
    if "load_transfer" not in tables:
        op.create_table(
            "load_transfer",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("transfer_date", sa.String(), nullable=False),
            sa.Column("from_type", sa.String(), nullable=False),
            sa.Column("from_ref_id", sa.Integer(), nullable=True),
            sa.Column("to_type", sa.String(), nullable=False),
            sa.Column("to_ref_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("is_settled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("from_type IN ('msr','rso')", name="ck_load_transfer_from_type"),
            sa.CheckConstraint("to_type IN ('rso','retail')", name="ck_load_transfer_to_type"),
            sa.CheckConstraint("amount > 0", name="ck_load_transfer_amount_positive"),
        )
        op.create_index("ix_load_transfer_tenant_id", "load_transfer", ["tenant_id"])

    # ------------------------------------------------------------------
    # sim_batch
    # ------------------------------------------------------------------
    if "sim_batch" not in tables:
        op.create_table(
            "sim_batch",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("operator_name", sa.String(), nullable=False),
            sa.Column("batch_reference", sa.String(), nullable=False),
            sa.Column("series_from", sa.String(), nullable=True),
            sa.Column("series_to", sa.String(), nullable=True),
            sa.Column("qty_received", sa.Integer(), nullable=False),
            sa.Column("qty_activated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("qty_issued_rso", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("received_date", sa.String(), nullable=False),
            sa.Column("tracker_txn_id", sa.Integer(), sa.ForeignKey("tracker_transaction.id"), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "batch_reference", name="uq_sim_batch_ref"),
            sa.CheckConstraint("qty_received > 0", name="ck_sim_batch_qty_positive"),
        )
        op.create_index("ix_sim_batch_tenant_id", "sim_batch", ["tenant_id"])

    # ------------------------------------------------------------------
    # sim_activation
    # ------------------------------------------------------------------
    if "sim_activation" not in tables:
        op.create_table(
            "sim_activation",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("sim_batch_id", sa.Integer(), sa.ForeignKey("sim_batch.id"), nullable=False),
            sa.Column("sim_number", sa.String(), nullable=True),
            sa.Column("activation_date", sa.String(), nullable=False),
            sa.Column("customer_name", sa.String(), nullable=True),
            sa.Column("customer_cnic", sa.String(), nullable=True),
            sa.Column("activation_type", sa.String(), nullable=False),
            sa.Column("rso_id", sa.Integer(), sa.ForeignKey("rso_agent.id"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'pending'"),
            sa.Column("sale_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "activation_type IN ('counter_sale','rso_issue')",
                name="ck_sim_activation_type",
            ),
            sa.CheckConstraint(
                "status IN ('pending','active','rejected')",
                name="ck_sim_activation_status",
            ),
        )
        op.create_index("ix_sim_activation_tenant_id", "sim_activation", ["tenant_id"])
        op.create_index("ix_sim_activation_batch_id", "sim_activation", ["sim_batch_id"])
        op.create_index("ix_sim_activation_rso_id", "sim_activation", ["rso_id"])

    # ------------------------------------------------------------------
    # rso_daily_collection
    # ------------------------------------------------------------------
    if "rso_daily_collection" not in tables:
        op.create_table(
            "rso_daily_collection",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("rso_id", sa.Integer(), sa.ForeignKey("rso_agent.id"), nullable=False),
            sa.Column("collection_date", sa.String(), nullable=False),
            sa.Column("load_portion", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("stock_portion", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_deposited", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("variance", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("is_reconciled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_rso_daily_collection_tenant_id", "rso_daily_collection", ["tenant_id"])
        op.create_index("ix_rso_daily_collection_rso_id", "rso_daily_collection", ["rso_id"])

    # ------------------------------------------------------------------
    # kpi_target  (created before fca_event because fca_event references it)
    # ------------------------------------------------------------------
    if "kpi_target" not in tables:
        op.create_table(
            "kpi_target",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("tracker_account_id", sa.Integer(), sa.ForeignKey("tracker_account.id"), nullable=False),
            sa.Column("target_month", sa.String(), nullable=False),
            sa.Column("target_fca_count", sa.Integer(), nullable=False),
            sa.Column("actual_fca_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("incentive_earned", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("penalty_applied", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("commission_txn_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="'open'"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "tracker_account_id", "target_month",
                name="uq_kpi_target_month",
            ),
            sa.CheckConstraint("status IN ('open','closed')", name="ck_kpi_target_status"),
        )
        op.create_index("ix_kpi_target_tenant_id", "kpi_target", ["tenant_id"])

    # ------------------------------------------------------------------
    # fca_event
    # ------------------------------------------------------------------
    if "fca_event" not in tables:
        op.create_table(
            "fca_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False),
            sa.Column("kpi_target_id", sa.Integer(), sa.ForeignKey("kpi_target.id"), nullable=False),
            sa.Column("sim_number", sa.String(), nullable=True),
            sa.Column("event_date", sa.String(), nullable=False),
            sa.Column("source_channel", sa.String(), nullable=False),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "source_channel IN ('counter','rso_retail','direct')",
                name="ck_fca_event_channel",
            ),
        )
        op.create_index("ix_fca_event_tenant_id", "fca_event", ["tenant_id"])
        op.create_index("ix_fca_event_kpi_target_id", "fca_event", ["kpi_target_id"])

    # ------------------------------------------------------------------
    # Extend tenant.business_model CHECK to include telecom_franchise
    # ------------------------------------------------------------------
    # SQLite does not support ALTER COLUMN CHECK in-place, but the Alembic
    # batch_alter_table context handles the recreate-table approach for SQLite.
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_constraint("ck_tenant_business_model", type_="check")
        batch_op.create_check_constraint(
            "ck_tenant_business_model",
            "business_model IN ('simple','services','trader','manufacturing','telecom_franchise')",
        )


def downgrade() -> None:
    # Drop in reverse FK-safe order
    op.drop_table("fca_event")
    op.drop_table("kpi_target")
    op.drop_table("rso_daily_collection")
    op.drop_table("sim_activation")
    op.drop_table("sim_batch")
    op.drop_table("load_transfer")
    op.drop_table("retail_outlet")
    op.drop_table("rso_agent")
    op.drop_table("tracker_transaction")
    op.drop_table("tracker_account")

    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_constraint("ck_tenant_business_model", type_="check")
        batch_op.create_check_constraint(
            "ck_tenant_business_model",
            "business_model IN ('simple','services','trader','manufacturing')",
        )
