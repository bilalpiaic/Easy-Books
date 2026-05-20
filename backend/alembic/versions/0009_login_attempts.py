"""Commit C: DB-backed per-IP login throttle.

Revision ID: 0009_login_attempts
Revises: 0008_sequence_counter
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_login_attempts"
down_revision = "0008_sequence_counter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "loginattempt" in insp.get_table_names():
        return
    op.create_table(
        "loginattempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False, index=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False, index=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("loginattempt")
