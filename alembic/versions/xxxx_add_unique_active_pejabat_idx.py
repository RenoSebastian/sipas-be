"""add unique active pejabat idx

Revision ID: add_unique_active_pejabat_idx
Revises: None
Create Date: 2026-07-15 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identitas revisi Alembic. 
# Catatan: Harap sesuaikan 'down_revision' dengan ID revisi terakhir di proyek Anda jika ada.
revision: str = 'add_unique_active_pejabat_idx'
down_revision: Union[str, None] = '117953917193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Menerapkan Partial Unique Index pada PostgreSQL."""
    # Menambahkan indeks unik parsial pada tabel 'users' untuk kolom 'role'.
    # Indeks ini hanya aktif jika 'is_active' bernilai True DAN 'role' bernilai 'KADIS' atau 'KABID_PUPR'.
    op.create_index(
        'idx_unique_active_pejabat',
        'users',
        ['role'],
        unique=True,
        postgresql_where=sa.text("is_active = true AND role IN ('KADIS', 'KABID_PUPR')")
    )


def downgrade() -> None:
    """Menghapus Partial Unique Index jika migrasi dibatalkan."""
    op.drop_index(
        'idx_unique_active_pejabat',
        table_name='users'
    )