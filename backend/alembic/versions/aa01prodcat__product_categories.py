"""product_categories

Revision ID: aa01prodcat
Revises: 520ea8c9ea33
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "aa01prodcat"
down_revision: Union[str, Sequence[str], None] = "520ea8c9ea33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "productcategory"):
        op.create_table(
            "productcategory",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "parent_id", "name", name="unique_category_name_per_parent"),
        )
        op.create_index(op.f("ix_productcategory_tenant_id"), "productcategory", ["tenant_id"])
        op.create_index(op.f("ix_productcategory_parent_id"), "productcategory", ["parent_id"])

    cols = {c["name"] for c in sa.inspect(bind).get_columns("product")}
    if "category_id" not in cols:
        op.add_column("product", sa.Column("category_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_product_category_id"), "product", ["category_id"])
    # FK on product.category_id omitted: SQLite cannot ADD CONSTRAINT via ALTER.


def downgrade() -> None:
    op.drop_index(op.f("ix_product_category_id"), table_name="product")
    op.drop_column("product", "category_id")
    op.drop_index(op.f("ix_productcategory_parent_id"), table_name="productcategory")
    op.drop_index(op.f("ix_productcategory_tenant_id"), table_name="productcategory")
    op.drop_table("productcategory")
