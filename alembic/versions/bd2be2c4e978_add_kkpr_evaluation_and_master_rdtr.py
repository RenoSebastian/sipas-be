"""add_kkpr_evaluation_and_master_rdtr

Revision ID: bd2be2c4e978
Revises: 09cc0aaa2a7d
Create Date: 2026-07-06 13:45:21.270776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# Impor enum python untuk mendaftarkan type mapping ke postgres
import enum

# revision identifiers, used by Alembic.
revision: str = 'bd2be2c4e978'
down_revision: Union[str, Sequence[str], None] = '09cc0aaa2a7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ambil koneksi database aktif untuk pengecekan tipe kustom
    bind = op.get_bind()

    # ─── TAHAP 1: CHECK-FIRST & CREATE ENUM TYPES DI POSTGRESQL ───
    # Memeriksa apakah tipe 'kkprverdict' sudah ada di pg_type PostgreSQL sebelum dibuat
    has_kkpr = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'kkprverdict')")).scalar()
    if not has_kkpr:
        kkpr_verdict_enum = postgresql.ENUM(
            'SESUAI', 'SESUAI_BERSYARAT', 'PERLU_PERBAIKAN', 'TIDAK_SESUAI', 
            name='kkprverdict'
        )
        kkpr_verdict_enum.create(bind, checkfirst=True)

    # Memeriksa apakah tipe 'checkliststatus' sudah ada di pg_type PostgreSQL sebelum dibuat
    has_checklist = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'checkliststatus')")).scalar()
    if not has_checklist:
        checklist_status_enum = postgresql.ENUM(
            'SESUAI', 'SESUAI_BERSYARAT', 'TIDAK_SESUAI', 'PENDING', 
            name='checkliststatus'
        )
        checklist_status_enum.create(bind, checkfirst=True)

    # ─── TAHAP 2: EKSEKUSI PEMBUATAN TABEL DAN KOLOM BARU ───
    # Pembuatan Tabel Master RDTR
    op.create_table('master_rdtr',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('district', sa.String(length=255), nullable=False),
        sa.Column('village', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('max_kdb', sa.Float(), nullable=False),
        sa.Column('max_klb', sa.Float(), nullable=False),
        sa.Column('min_kdh', sa.Float(), nullable=False),
        sa.Column('min_gsb', sa.Float(), nullable=False),
        sa.Column('min_rth_area', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_master_rdtr_category'), 'master_rdtr', ['category'], unique=False)
    op.create_index(op.f('ix_master_rdtr_district'), 'master_rdtr', ['district'], unique=False)
    op.create_index(op.f('ix_master_rdtr_village'), 'master_rdtr', ['village'], unique=False)

    # Pembuatan Tabel Evaluasi Checklist dengan 'create_type=False'
    op.create_table('evaluasi_checklist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_permohonan', sa.String(length=50), nullable=False),
        sa.Column('aspek_code', sa.String(length=50), nullable=False),
        sa.Column('aspek_label', sa.String(length=255), nullable=False),
        sa.Column('status_kelayakan', postgresql.ENUM('SESUAI', 'SESUAI_BERSYARAT', 'TIDAK_SESUAI', 'PENDING', name='checkliststatus', create_type=False), nullable=False),
        sa.Column('catatan_verifikator', sa.Text(), nullable=True),
        sa.Column('attachment_url', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['id_permohonan'], ['permohonan.id_permohonan'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Penambahan Kolom Baru ke Tabel Permohonan
    op.add_column('permohonan', sa.Column('applicant_land_area', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_building_area', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_kdb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_klb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_kdh', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_gsb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('applicant_rth_area', sa.Float(), nullable=True))
    
    op.add_column('permohonan', sa.Column('bylaw_max_kdb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('bylaw_max_klb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('bylaw_min_kdh', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('bylaw_min_gsb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('bylaw_min_rth_area', sa.Float(), nullable=True))
    
    op.add_column('permohonan', sa.Column('verified_kdb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('verified_klb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('verified_kdh', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('verified_gsb', sa.Float(), nullable=True))
    op.add_column('permohonan', sa.Column('verified_rth_area', sa.Float(), nullable=True))
    
    # Penambahan kkpr_verdict dengan 'create_type=False'
    op.add_column('permohonan', sa.Column('kkpr_verdict', postgresql.ENUM('SESUAI', 'SESUAI_BERSYARAT', 'PERLU_PERBAIKAN', 'TIDAK_SESUAI', name='kkprverdict', create_type=False), nullable=True))
    op.add_column('permohonan', sa.Column('kkpr_verified_at', sa.DateTime(), nullable=True))
    op.add_column('permohonan', sa.Column('kkpr_verifier_name', sa.String(length=255), nullable=True))

    # Pengubahan Batasan Kolom Permohonan (Altering Constraints)
    op.alter_column('permohonan', 'housing_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'developer_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'land_area', existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('permohonan', 'applicant_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'applicant_npwp', existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column('permohonan', 'applicant_phone', existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column('permohonan', 'applicant_email', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'applicant_address', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('permohonan', 'location_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_village', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_district', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_city', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_province', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_full_address', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('permohonan', 'location_ownership_status', existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column('permohonan', 'location_certificate_number', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'location_certificate_owner', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'spatial_kkpr_number', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'spatial_land_use', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'consultant_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'consultant_company_name', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('permohonan', 'consultant_pic_name', existing_type=sa.VARCHAR(length=255), nullable=True)


def downgrade() -> None:
    # Mengembalikan Batasan Kolom Permohonan (Altering Constraints)
    op.alter_column('permohonan', 'consultant_pic_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'consultant_company_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'consultant_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'spatial_land_use', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'spatial_kkpr_number', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_certificate_owner', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_certificate_number', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_ownership_status', existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column('permohonan', 'location_full_address', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('permohonan', 'location_province', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_city', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_district', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_village', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'location_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'applicant_address', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('permohonan', 'applicant_email', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'applicant_phone', existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column('permohonan', 'applicant_npwp', existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column('permohonan', 'applicant_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'land_area', existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('permohonan', 'developer_name', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('permohonan', 'housing_name', existing_type=sa.VARCHAR(length=255), nullable=False)

    # Drop Kolom Tambahan Permohonan
    op.drop_column('permohonan', 'kkpr_verifier_name')
    op.drop_column('permohonan', 'kkpr_verified_at')
    op.drop_column('permohonan', 'kkpr_verdict')
    op.drop_column('permohonan', 'verified_rth_area')
    op.drop_column('permohonan', 'verified_gsb')
    op.drop_column('permohonan', 'verified_kdh')
    op.drop_column('permohonan', 'verified_klb')
    op.drop_column('permohonan', 'verified_kdb')
    op.drop_column('permohonan', 'bylaw_min_rth_area')
    op.drop_column('permohonan', 'bylaw_min_gsb')
    op.drop_column('permohonan', 'bylaw_min_kdh')
    op.drop_column('permohonan', 'bylaw_max_klb')
    op.drop_column('permohonan', 'bylaw_max_kdb')
    op.drop_column('permohonan', 'applicant_rth_area')
    op.drop_column('permohonan', 'applicant_gsb')
    op.drop_column('permohonan', 'applicant_kdh')
    op.drop_column('permohonan', 'applicant_klb')
    op.drop_column('permohonan', 'applicant_kdb')
    op.drop_column('permohonan', 'applicant_building_area')
    op.drop_column('permohonan', 'applicant_land_area')

    # Drop Tabel Evaluasi & Master RDTR
    op.drop_table('evaluasi_checklist')
    op.drop_index(op.f('ix_master_rdtr_village'), table_name='master_rdtr')
    op.drop_index(op.f('ix_master_rdtr_district'), table_name='master_rdtr')
    op.drop_index(op.f('ix_master_rdtr_category'), table_name='master_rdtr')
    op.drop_table('master_rdtr')

    # ─── TAHAP 3: HAPUS CUSTOM ENUM TYPES DARI DATABASE POSTGRESQL ───
    sa.Enum(name='kkprverdict').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='checkliststatus').drop(op.get_bind(), checkfirst=True)