"""add_drone_video_url

Revision ID: 2fd98bc703ce
Revises: b6994efb23ed
Create Date: 2026-07-17 16:44:32.661062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 


# revision identifiers, used by Alembic.
revision: str = '2fd98bc703ce'
down_revision: Union[str, Sequence[str], None] = 'b6994efb23ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('field_inspection_logs', sa.Column('drone_video_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('field_inspection_logs', 'drone_video_url')
