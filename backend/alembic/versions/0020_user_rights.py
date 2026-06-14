"""user rights module: user_permission table, created_by_id columns, my_data_only

Revision ID: 0020_user_rights
Revises: 1af1ee747edb
Create Date: 2026-06-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0020_user_rights"
down_revision = "1af1ee747edb"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # user_permission table (sparse overrides; bulk of enforcement is in services/permissions.py)
    if not bind.dialect.has_table(bind, "user_permission"):
        op.create_table(
            "user_permission",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
            sa.Column("user_id", sa.Integer, nullable=False, index=True),
            sa.Column("resource_key", sa.String, nullable=False, index=True),
            sa.Column("access_level", sa.String, nullable=False, server_default="edit"),
            sa.UniqueConstraint("user_id", "resource_key", name="uq_user_permission"),
        )

    # my_data_only on user
    with op.batch_alter_table("user") as batch_op:
        cols = [c["name"] for c in sa.inspect(bind).get_columns("user")]
        if "my_data_only" not in cols:
            batch_op.add_column(
                sa.Column("my_data_only", sa.Boolean, nullable=False, server_default="0")
            )

    # created_by_id on transaction, invoice, bill, paymentreceived, billpayment
    for table in ("transaction", "invoice", "bill", "paymentreceived", "billpayment"):
        with op.batch_alter_table(table) as batch_op:
            cols = [c["name"] for c in sa.inspect(bind).get_columns(table)]
            if "created_by_id" not in cols:
                batch_op.add_column(
                    sa.Column("created_by_id", sa.Integer, nullable=True, index=True)
                )


def downgrade():
    pass
