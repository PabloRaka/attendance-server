"""add_has_seen_tutorial_to_user

Revision ID: 9a7c3f12d1ab
Revises: bf3001c83c8b
Create Date: 2026-04-15 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a7c3f12d1ab'
down_revision: Union[str, Sequence[str], None] = 'bf3001c83c8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('has_seen_tutorial', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('users', 'has_seen_tutorial')
