"""Tenant-scope UserPermission uniqueness (#299)

Revision ID: 0069_user_permission_tenant_unique
Revises: 0068_tenant_saas_repair
Create Date: 2026-08-04

Unique key becomes (tenant_id, user_id, resource_key) so practice users can
hold different overrides per client. SQLite cannot DROP/ADD CONSTRAINT via
ALTER — app-level upserts already filter by tenant_id; fresh create_all picks
up the model UniqueConstraint.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0069_user_permission_tenant_unique"
down_revision: Union[str, Sequence[str], None] = "0068_tenant_saas_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # App-level tenant filter + model UniqueConstraint on recreate is enough.
        return
    insp = sa.inspect(bind)
    if not bind.dialect.has_table(bind, "user_permission"):
        return
    uniques = {u["name"] for u in insp.get_unique_constraints("user_permission")}
    if "uq_user_permission" in uniques:
        op.drop_constraint("uq_user_permission", "user_permission", type_="unique")
    if "uq_user_permission_tenant" not in uniques:
        op.create_unique_constraint(
            "uq_user_permission_tenant",
            "user_permission",
            ["tenant_id", "user_id", "resource_key"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    insp = sa.inspect(bind)
    if not bind.dialect.has_table(bind, "user_permission"):
        return
    uniques = {u["name"] for u in insp.get_unique_constraints("user_permission")}
    if "uq_user_permission_tenant" in uniques:
        op.drop_constraint("uq_user_permission_tenant", "user_permission", type_="unique")
    if "uq_user_permission" not in uniques:
        op.create_unique_constraint(
            "uq_user_permission",
            "user_permission",
            ["user_id", "resource_key"],
        )
