"""add tte columns

Revision ID: f2eb518d6a89
Revises: 1ddfa8438d38
Create Date: 2026-07-01 13:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2eb518d6a89'
down_revision: Union[str, Sequence[str], None] = 'c08f9a4ddb34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to permohonan table
    op.add_column('permohonan', sa.Column('signature_hash', sa.String(length=255), nullable=True))
    op.add_column('permohonan', sa.Column('signed_pdf_url', sa.String(length=500), nullable=True))
    
    # Add column to audit_trail table
    op.add_column('audit_trail', sa.Column('digital_signature_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Remove column from audit_trail table
    op.drop_column('audit_trail', 'digital_signature_hash')
    
    # Remove columns from permohonan table
    op.drop_column('permohonan', 'signed_pdf_url')
    op.drop_column('permohonan', 'signature_hash')
