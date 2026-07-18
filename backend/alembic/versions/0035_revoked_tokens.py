"""revoked tokens (#113 part 3)

Revision ID: 0035_revoked_tokens
Revises: 0034_api_keys
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0035_revoked_tokens'
down_revision: Union[str, Sequence[str], None] = '0034_api_keys'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Guarded: dev still bootstraps via SQLModel.metadata.create_all(), so a
    # fresh DB already has this table when the migration runs.
    if not bind.dialect.has_table(bind, 'revokedtoken'):
        op.create_table(
            'revokedtoken',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('jti', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_revokedtoken_jti'), 'revokedtoken', ['jti'], unique=True)
        op.create_index(op.f('ix_revokedtoken_tenant_id'), 'revokedtoken', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_revokedtoken_expires_at'), 'revokedtoken', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_table('revokedtoken')
