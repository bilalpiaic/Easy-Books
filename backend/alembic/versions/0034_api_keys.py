"""api keys (#113 part 2)

Revision ID: 0034_api_keys
Revises: dfde4f3290aa
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0034_api_keys'
down_revision: Union[str, Sequence[str], None] = 'dfde4f3290aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Guarded: dev still bootstraps via SQLModel.metadata.create_all(), so a
    # fresh DB already has this table when the migration runs.
    if not bind.dialect.has_table(bind, 'apikey'):
        op.create_table(
            'apikey',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('key_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('key_hint', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('scopes', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('last_used', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_apikey_tenant_id'), 'apikey', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_apikey_user_id'), 'apikey', ['user_id'], unique=False)
        op.create_index(op.f('ix_apikey_key_hash'), 'apikey', ['key_hash'], unique=True)


def downgrade() -> None:
    op.drop_table('apikey')
