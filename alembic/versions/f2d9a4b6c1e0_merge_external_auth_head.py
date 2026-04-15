"""merge external auth head

Revision ID: f2d9a4b6c1e0
Revises: 8c1881c93717, c4e2b1a7d9f0
Create Date: 2026-04-15 15:20:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'f2d9a4b6c1e0'
down_revision: Union[str, Sequence[str], None] = ('8c1881c93717', 'c4e2b1a7d9f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
