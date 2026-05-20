"""P4: idempotency key cache for safe POST retries.

Revision ID: 0004_idempotency_keys
Revises: 0003_p3_tax_alloc_recurring
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_idempotency_keys"
down_revision = "0003_p3_tax_alloc_recurring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "idempotencykey" in insp.get_table_names():
        return
    op.create_table(
        "idempotencykey",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
        sa.Column("key", sa.String(), nullable=False, index=True),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "key", name="unique_idemp_key_per_tenant"),
    )


def downgrade() -> None:
    op.drop_table("idempotencykey")
