"""user dashboard layout

Revision ID: dashlayout01
Revises: e545b922a716
"""
from alembic import op
import sqlalchemy as sa

revision = "dashlayout01"
down_revision = "e545b922a716"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "userdashboardlayout"):
        op.create_table(
            "userdashboardlayout",
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id"), primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), primary_key=True),
            sa.Column("layout_json", sa.String, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("userdashboardlayout")
