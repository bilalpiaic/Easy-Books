"""add 'hospital' (and pra_einvoice) to tenant.business_model CHECK constraint

Revision ID: 0028_tenant_hospital_model
Revises: 0027_healthcare
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_tenant_hospital_model"
down_revision = "0027_healthcare"
branch_labels = None
depends_on = None

_NEW_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise','pra_einvoice','hospital')"
)
_OLD_CHECK = (
    "business_model IN "
    "('simple','services','trader','manufacturing','telecom_franchise')"
)

# Full column list of the tenant table (order must match SELECT below)
_COLS = "id, name, base_currency, business_model, enabled_modules, created_at, cost_method, module_meta"


def _sqlite_rebuild(bind, check_expr: str) -> None:
    """SQLite can't ALTER a CHECK constraint — rebuild the table."""
    bind.execute(sa.text(f"""
        CREATE TABLE tenant_new (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            base_currency VARCHAR NOT NULL,
            business_model VARCHAR DEFAULT 'simple' NOT NULL,
            enabled_modules VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            cost_method VARCHAR NOT NULL,
            module_meta VARCHAR DEFAULT '{{}}' NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT ck_tenant_business_model CHECK ({check_expr}),
            CONSTRAINT ck_tenant_cost_method CHECK (cost_method IN ('wavg','fifo'))
        )
    """))
    bind.execute(sa.text(f"INSERT INTO tenant_new ({_COLS}) SELECT {_COLS} FROM tenant"))
    bind.execute(sa.text("DROP TABLE tenant"))
    bind.execute(sa.text("ALTER TABLE tenant_new RENAME TO tenant"))


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _NEW_CHECK)
    else:
        op.drop_constraint("ck_tenant_business_model", "tenant", type_="check")
        op.create_check_constraint("ck_tenant_business_model", "tenant", _NEW_CHECK)


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, _OLD_CHECK)
    else:
        op.drop_constraint("ck_tenant_business_model", "tenant", type_="check")
        op.create_check_constraint("ck_tenant_business_model", "tenant", _OLD_CHECK)
