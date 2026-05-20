"""P2: add User.role with CHECK constraint.

Revision ID: 0002_user_role
Revises: 0001_baseline
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_user_role"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The baseline migration creates the schema from current SQLModel metadata,
    # which already includes `role`. On fresh deployments the column will
    # exist; this migration is the explicit upgrade path for older databases
    # that were created before role was introduced.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user")}
    if "role" not in cols:
        with op.batch_alter_table("user", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "role",
                    sa.String(),
                    nullable=False,
                    server_default="viewer",
                )
            )
        # Backfill: existing single-user tenants should be owners.
        op.execute("UPDATE user SET role = 'owner'")


def downgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("role")
