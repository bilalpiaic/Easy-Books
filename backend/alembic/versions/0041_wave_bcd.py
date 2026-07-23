"""totp/sso + saas tenant columns + portal/approvals/plaid/agent (#118–#125)

Revision ID: 0041_wave_bcd
Revises: 0040_webhooks
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0041_wave_bcd"
down_revision: Union[str, Sequence[str], None] = "0040_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Tenant SaaS columns (#119)
    tcols = {c["name"] for c in insp.get_columns("tenant")}
    with op.batch_alter_table("tenant") as batch:
        for name, col in [
            ("plan", sa.Column("plan", sa.String(), server_default="free", nullable=False)),
            ("max_users", sa.Column("max_users", sa.Integer(), server_default="2", nullable=False)),
            ("max_documents", sa.Column("max_documents", sa.Integer(), server_default="50", nullable=False)),
            ("storage_quota_mb", sa.Column("storage_quota_mb", sa.Integer(), server_default="100", nullable=False)),
            ("is_suspended", sa.Column("is_suspended", sa.Boolean(), server_default=sa.false(), nullable=False)),
            ("trial_ends_at", sa.Column("trial_ends_at", sa.DateTime(), nullable=True)),
            ("stripe_customer_id", sa.Column("stripe_customer_id", sa.String(), nullable=True)),
            ("stripe_subscription_id", sa.Column("stripe_subscription_id", sa.String(), nullable=True)),
            ("subscription_status", sa.Column("subscription_status", sa.String(), nullable=True)),
        ]:
            if name not in tcols:
                batch.add_column(col)

    # User 2FA/SSO (#118)
    ucols = {c["name"] for c in insp.get_columns("user")}
    with op.batch_alter_table("user") as batch:
        for name, col in [
            ("totp_enabled", sa.Column("totp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False)),
            ("totp_secret", sa.Column("totp_secret", sa.String(), nullable=True)),
            ("totp_verified_at", sa.Column("totp_verified_at", sa.DateTime(), nullable=True)),
            ("oauth_provider", sa.Column("oauth_provider", sa.String(), nullable=True)),
            ("oauth_sub", sa.Column("oauth_sub", sa.String(), nullable=True)),
        ]:
            if name not in ucols:
                batch.add_column(col)

    # Customer dunning opt-out (#120)
    ccols = {c["name"] for c in insp.get_columns("customer")}
    if "dunning_opt_out" not in ccols:
        with op.batch_alter_table("customer") as batch:
            batch.add_column(sa.Column("dunning_opt_out", sa.Boolean(), server_default=sa.false(), nullable=False))

    for table, col in [("invoice", "approval_status"), ("bill", "approval_status")]:
        cols = {c["name"] for c in insp.get_columns(table)}
        if col not in cols:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column(col, sa.String(), nullable=True))
                batch.create_index(f"ix_{table}_{col}", [col])

    def _create(name, *cols, indexes=()):
        if bind.dialect.has_table(bind, name):
            return
        op.create_table(name, *cols)
        for ix_name, ix_cols in indexes:
            op.create_index(ix_name, name, ix_cols)

    _create(
        "portaltoken",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column("last_accessed", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        indexes=[
            ("ix_portaltoken_tenant_id", ["tenant_id"]),
            ("ix_portaltoken_entity_id", ["entity_id"]),
            ("ix_portaltoken_token_hash", ["token_hash"]),
        ],
    )
    _create(
        "dunningrule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("days_overdue", sa.Integer(), nullable=False),
        sa.Column("subject_template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("body_template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        indexes=[("ix_dunningrule_tenant_id", ["tenant_id"])],
    )
    _create(
        "approvalworkflow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        indexes=[("ix_approvalworkflow_tenant_id", ["tenant_id"])],
    )
    _create(
        "approvalstep",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_role", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("min_amount", sa.Float(), nullable=True),
        sa.Column("timeout_hours", sa.Integer(), nullable=True),
        indexes=[("ix_approvalstep_workflow_id", ["workflow_id"])],
    )
    _create(
        "approvalrequest",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        indexes=[
            ("ix_approvalrequest_tenant_id", ["tenant_id"]),
            ("ix_approvalrequest_document_id", ["document_id"]),
            ("ix_approvalrequest_status", ["status"]),
        ],
    )
    _create(
        "plaidconnection",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("access_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("item_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("institution_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("last_sync", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        indexes=[
            ("ix_plaidconnection_tenant_id", ["tenant_id"]),
            ("ix_plaidconnection_item_id", ["item_id"]),
        ],
    )
    _create(
        "categorizationrule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("pattern", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        indexes=[("ix_categorizationrule_tenant_id", ["tenant_id"])],
    )
    _create(
        "agentsuggestion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("action_href", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("action_label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("dismissed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        indexes=[
            ("ix_agentsuggestion_tenant_id", ["tenant_id"]),
            ("ix_agentsuggestion_kind", ["kind"]),
        ],
    )
    _create(
        "agentautomation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("trigger", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("agent_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("dry_run_only", sa.Boolean(), nullable=False),
        indexes=[("ix_agentautomation_tenant_id", ["tenant_id"])],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for name in [
        "agentautomation", "agentsuggestion", "categorizationrule", "plaidconnection",
        "approvalrequest", "approvalstep", "approvalworkflow", "dunningrule", "portaltoken",
    ]:
        if bind.dialect.has_table(bind, name):
            op.drop_table(name)
