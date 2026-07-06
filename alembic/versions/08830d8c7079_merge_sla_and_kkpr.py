"""merge_sla_and_kkpr

Revision ID: 08830d8c7079
Revises: bd2be2c4e978, f8bb20134042
Create Date: 2026-07-06 15:09:07.652821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 


# revision identifiers, used by Alembic.
revision: str = '08830d8c7079'
down_revision: Union[str, Sequence[str], None] = ('bd2be2c4e978', 'f8bb20134042')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
