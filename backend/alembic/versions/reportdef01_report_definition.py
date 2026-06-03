"""report definition

Revision ID: reportdef01
Revises: aa01prodcat
"""
from alembic import op
import sqlalchemy as sa

revision = "reportdef01"
down_revision = "aa01prodcat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "reportdefinition"):
        op.create_table(
            "reportdefinition",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), index=True, nullable=False),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("source_key", sa.String, nullable=False),
            sa.Column("config", sa.JSON, nullable=False),
            sa.Column("visibility", sa.String, nullable=False, server_default="private"),
            sa.Column("owner_id", sa.Integer, sa.ForeignKey("user.id"), index=True, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("reportdefinition")
