"""add_external_auth_id_to_user

Revision ID: c4e2b1a7d9f0
Revises: 9a7c3f12d1ab
Create Date: 2026-04-15 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e2b1a7d9f0'
down_revision: Union[str, Sequence[str], None] = '9a7c3f12d1ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('external_auth_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_external_auth_id'), 'users', ['external_auth_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_external_auth_id'), table_name='users')
    op.drop_column('users', 'external_auth_id')
