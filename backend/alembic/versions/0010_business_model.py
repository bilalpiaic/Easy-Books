"""V2.1: Tenant.business_model + enabled_modules + Account.is_memo.

Revision ID: 0010_business_model
Revises: 0009_login_attempts
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_business_model"
down_revision = "0009_login_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Tenant.business_model + enabled_modules
    tenant_cols = {c["name"] for c in insp.get_columns("tenant")}
    if "business_model" not in tenant_cols:
        with op.batch_alter_table("tenant", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "business_model", sa.String(),
                    nullable=False, server_default="simple",
                )
            )
    if "enabled_modules" not in tenant_cols:
        with op.batch_alter_table("tenant", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "enabled_modules", sa.String(),
                    nullable=False, server_default="[]",
                )
            )

    # Account.is_memo
    acct_cols = {c["name"] for c in insp.get_columns("account")}
    if "is_memo" not in acct_cols:
        with op.batch_alter_table("account", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_memo", sa.Boolean(),
                    nullable=False, server_default=sa.false(),
                )
            )

    # Backfill: existing tenants stay on 'simple' (already defaulted), but seed
    # the matching enabled_modules JSON for them so the SPA can read it.
    op.execute(
        "UPDATE tenant SET enabled_modules = "
        "'[\"invoicing\", \"billing\", \"manual_jv\"]' "
        "WHERE enabled_modules = '[]' OR enabled_modules IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("account", schema=None) as batch_op:
        batch_op.drop_column("is_memo")
    with op.batch_alter_table("tenant", schema=None) as batch_op:
        batch_op.drop_column("enabled_modules")
        batch_op.drop_column("business_model")
