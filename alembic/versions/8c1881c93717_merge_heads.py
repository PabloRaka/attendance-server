"""merge heads

Revision ID: 8c1881c93717
Revises: 6a6f8f3e953d, 9a7c3f12d1ab
Create Date: 2026-04-15 13:55:58.351454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c1881c93717'
down_revision: Union[str, Sequence[str], None] = ('6a6f8f3e953d', '9a7c3f12d1ab')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
