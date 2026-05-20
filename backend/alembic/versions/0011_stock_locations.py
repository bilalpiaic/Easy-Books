"""V2.2: StockLocation + StockMovement + lot/location on InventoryLayer.

Revision ID: 0011_stock_locations
Revises: 0010_business_model
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_stock_locations"
down_revision = "0010_business_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # ── stocklocation table ────────────────────────────────────────────────
    if "stocklocation" not in tables:
        op.create_table(
            "stocklocation",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("code", sa.String(), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="unique_stock_location_code"),
            sa.CheckConstraint(
                "type IN ('own','customer_custodial','wip')",
                name="ck_stock_location_type",
            ),
        )

    # ── stockmovement table ────────────────────────────────────────────────
    if "stockmovement" not in tables:
        op.create_table(
            "stockmovement",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id"), nullable=False, index=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), nullable=False, index=True),
            sa.Column("direction", sa.String(), nullable=False),
            sa.Column("qty", sa.Numeric(18, 4), nullable=False),
            sa.Column("from_location_id", sa.Integer(), sa.ForeignKey("stocklocation.id"), nullable=True),
            sa.Column("to_location_id", sa.Integer(), sa.ForeignKey("stocklocation.id"), nullable=True),
            sa.Column("lot_no", sa.String(), nullable=True, index=True),
            sa.Column("owner_customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=True),
            sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("total_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("source_doc_type", sa.String(), nullable=True),
            sa.Column("source_doc_id", sa.Integer(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transaction.id"), nullable=True),
            sa.Column("posted_to_gl", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("notes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "direction IN ('RECEIPT','CUSTODIAL_RECEIPT','ISSUE','CUSTODIAL_ISSUE',"
                "'COMPLETION','CUSTODIAL_COMPLETION','DELIVERY','SHIPMENT','ADJUSTMENT')",
                name="ck_stock_movement_direction",
            ),
            sa.CheckConstraint("qty > 0", name="ck_stock_movement_qty_positive"),
        )

    # ── inventorylayer extensions ──────────────────────────────────────────
    # Use raw ADD COLUMN rather than batch_alter_table because the legacy
    # SQLModel.metadata.create_all baseline produced anonymous CHECK / FK
    # constraints that batch-mode can't rename when reconstructing the table.
    # Plain ADD COLUMN is supported by SQLite and Postgres without needing
    # to drop & recreate.
    layer_cols = {c["name"] for c in insp.get_columns("inventorylayer")}
    if "location_id" not in layer_cols:
        op.execute("ALTER TABLE inventorylayer ADD COLUMN location_id INTEGER")
    if "owner_customer_id" not in layer_cols:
        op.execute("ALTER TABLE inventorylayer ADD COLUMN owner_customer_id INTEGER")
    if "lot_no" not in layer_cols:
        op.execute("ALTER TABLE inventorylayer ADD COLUMN lot_no VARCHAR")

    # ── Backfill: every existing tenant gets a Main Store, and existing
    # InventoryLayer rows attach to it so legacy behaviour is preserved.
    bind.execute(sa.text(
        "INSERT INTO stocklocation (tenant_id, code, name, type, is_active) "
        "SELECT id, 'MAIN', 'Main Store', 'own', 1 FROM tenant "
        "WHERE id NOT IN (SELECT tenant_id FROM stocklocation WHERE code='MAIN')"
    ))
    bind.execute(sa.text(
        "UPDATE inventorylayer SET location_id = ("
        "  SELECT id FROM stocklocation "
        "  WHERE stocklocation.tenant_id = inventorylayer.tenant_id "
        "  AND stocklocation.code = 'MAIN' LIMIT 1) "
        "WHERE location_id IS NULL"
    ))

    # Manufacturing tenants also get GODOWN and WIP
    bind.execute(sa.text(
        "INSERT INTO stocklocation (tenant_id, code, name, type, is_active) "
        "SELECT id, 'GODOWN', 'Customer Goods Godown', 'customer_custodial', 1 "
        "FROM tenant WHERE business_model = 'manufacturing' "
        "AND id NOT IN (SELECT tenant_id FROM stocklocation WHERE code='GODOWN')"
    ))
    bind.execute(sa.text(
        "INSERT INTO stocklocation (tenant_id, code, name, type, is_active) "
        "SELECT id, 'WIP', 'Work-in-Progress Floor', 'wip', 1 "
        "FROM tenant WHERE business_model = 'manufacturing' "
        "AND id NOT IN (SELECT tenant_id FROM stocklocation WHERE code='WIP')"
    ))


def downgrade() -> None:
    # SQLite < 3.35 can't DROP COLUMN; the V2.2 columns are nullable so
    # downgrade leaves them in place. Drop the new tables to reclaim them.
    op.drop_table("stockmovement")
    op.drop_table("stocklocation")
