"""Portal dispute + custom-domain settings (#270)

Revision ID: 0053_portal_harden
Revises: 0052_bank_feeds
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0053_portal_harden"
down_revision: Union[str, Sequence[str], None] = "0052_bank_feeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "portaldispute"):
        op.create_table(
            "portaldispute",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("invoice_id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=True),
            sa.Column("body", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_portaldispute_tenant_id", "portaldispute", ["tenant_id"])
        op.create_index("ix_portaldispute_invoice_id", "portaldispute", ["invoice_id"])
        op.create_index("ix_portaldispute_status", "portaldispute", ["status"])

    # Expand user_alert.kind CHECK when present (create_all / Postgres).
    # Alembic 0038 created user_alert without the CHECK; recreate_all DBs have it.
    if bind.dialect.name == "sqlite":
        # SQLite CHECK is table-DDL-only; recreate only if constraint exists.
        row = bind.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_alert'"
        )).fetchone()
        ddl = (row[0] if row else "") or ""
        if "ck_user_alert_kind" in ddl and "invoice_dispute" not in ddl:
            bind.execute(sa.text("""
                CREATE TABLE user_alert_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    kind VARCHAR NOT NULL,
                    severity VARCHAR DEFAULT 'warning' NOT NULL,
                    title VARCHAR NOT NULL,
                    body VARCHAR,
                    href VARCHAR,
                    entity_type VARCHAR,
                    entity_id INTEGER,
                    dedupe_key VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    read_at DATETIME,
                    CONSTRAINT uq_user_alert_dedupe UNIQUE (user_id, dedupe_key),
                    CONSTRAINT ck_user_alert_kind CHECK (
                        kind IN ('overdue_invoice','low_stock','approval_needed','system','invoice_dispute')
                    ),
                    CONSTRAINT ck_user_alert_severity CHECK (
                        severity IN ('info','warning','critical')
                    )
                )
            """))
            bind.execute(sa.text("""
                INSERT INTO user_alert_new
                (id, tenant_id, user_id, kind, severity, title, body, href,
                 entity_type, entity_id, dedupe_key, created_at, read_at)
                SELECT id, tenant_id, user_id, kind, severity, title, body, href,
                       entity_type, entity_id, dedupe_key, created_at, read_at
                FROM user_alert
            """))
            bind.execute(sa.text("DROP TABLE user_alert"))
            bind.execute(sa.text("ALTER TABLE user_alert_new RENAME TO user_alert"))
            bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_alert_tenant_id ON user_alert (tenant_id)"))
            bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_alert_user_id ON user_alert (user_id)"))
            bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_alert_kind ON user_alert (kind)"))
            bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_alert_dedupe_key ON user_alert (dedupe_key)"))
    else:
        try:
            op.drop_constraint("ck_user_alert_kind", "user_alert", type_="check")
        except Exception:
            pass
        op.create_check_constraint(
            "ck_user_alert_kind",
            "user_alert",
            "kind IN ('overdue_invoice','low_stock','approval_needed','system','invoice_dispute')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "portaldispute"):
        op.drop_table("portaldispute")
