"""user_alert — per-user in-app ops alerts

Revision ID: 0038_user_alerts
Revises: 0037_weaving_calculators
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_user_alerts"
down_revision = "0037_weaving_calculators"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "user_alert"):
        return
    op.create_table(
        "user_alert",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False, index=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="warning"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("href", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        # SQLite can't ADD CONSTRAINT via ALTER; unique is created with the table.
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_user_alert_dedupe"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "user_alert"):
        op.drop_table("user_alert")
