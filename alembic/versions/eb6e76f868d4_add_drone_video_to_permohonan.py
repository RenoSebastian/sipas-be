"""add_drone_video_to_permohonan

Revision ID: eb6e76f868d4
Revises: 2fd98bc703ce
Create Date: 2026-07-17 17:04:24.577574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 


# revision identifiers, used by Alembic.
revision: str = 'eb6e76f868d4'
down_revision: Union[str, Sequence[str], None] = '2fd98bc703ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
