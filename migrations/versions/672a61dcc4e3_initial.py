"""initial

Revision ID: 672a61dcc4e3
Revises: 6773c46f2edb
Create Date: 2026-02-28 07:14:11.774639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '672a61dcc4e3'
down_revision: Union[str, Sequence[str], None] = '6773c46f2edb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
