"""Self-service password reset tokens (#390)

Revision ID: 0084_password_reset
Revises: 0083_field_source_extension
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0084_password_reset"
down_revision: Union[str, Sequence[str], None] = "0083_field_source_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Dev still bootstraps via create_all(); skip if the table already exists.
    if not bind.dialect.has_table(bind, "passwordresettoken"):
        op.create_table(
            "passwordresettoken",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_passwordresettoken_user_id", "passwordresettoken", ["user_id"])
        op.create_index("ix_passwordresettoken_tenant_id", "passwordresettoken", ["tenant_id"])
        op.create_index(
            "ix_passwordresettoken_token_hash",
            "passwordresettoken",
            ["token_hash"],
            unique=True,
        )
        op.create_index("ix_passwordresettoken_expires_at", "passwordresettoken", ["expires_at"])
    if not bind.dialect.has_table(bind, "passwordresetattempt"):
        op.create_table(
            "passwordresetattempt",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("ip", sa.String(), nullable=False),
            sa.Column("email_key", sa.String(), nullable=False),
            sa.Column("attempted_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_passwordresetattempt_ip", "passwordresetattempt", ["ip"])
        op.create_index("ix_passwordresetattempt_email_key", "passwordresetattempt", ["email_key"])
        op.create_index(
            "ix_passwordresetattempt_attempted_at",
            "passwordresetattempt",
            ["attempted_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "passwordresetattempt"):
        op.drop_table("passwordresetattempt")
    if bind.dialect.has_table(bind, "passwordresettoken"):
        op.drop_table("passwordresettoken")
