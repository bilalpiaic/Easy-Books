"""Commit B: SequenceCounter for atomic per-tenant document numbering.

Revision ID: 0008_sequence_counter
Revises: 0007_account_balance
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_sequence_counter"
down_revision = "0007_account_balance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "sequencecounter" in insp.get_table_names():
        return
    op.create_table(
        "sequencecounter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="unique_seq_per_tenant_name"),
    )

    # Backfill: for existing tenants, seed (invoice, bill) counters at
    # max(existing_number) + 1 so new POSTs don't collide with pre-existing
    # invoice/bill numbers minted under the old COUNT(*)+1 scheme.
    conn = bind
    tenants = conn.execute(sa.text("SELECT id FROM tenant")).fetchall()
    for (tid,) in tenants:
        inv_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM invoice WHERE tenant_id = :tid"),
            {"tid": tid},
        ).scalar() or 0
        bill_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM bill WHERE tenant_id = :tid"),
            {"tid": tid},
        ).scalar() or 0
        conn.execute(
            sa.text(
                "INSERT INTO sequencecounter (tenant_id, name, next_value) "
                "VALUES (:tid, 'invoice', :v)"
            ),
            {"tid": tid, "v": inv_count + 1},
        )
        conn.execute(
            sa.text(
                "INSERT INTO sequencecounter (tenant_id, name, next_value) "
                "VALUES (:tid, 'bill', :v)"
            ),
            {"tid": tid, "v": bill_count + 1},
        )


def downgrade() -> None:
    op.drop_table("sequencecounter")
