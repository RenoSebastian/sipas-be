"""add_pkkpr_module_tables

Revision ID: a1b2c3d4e5f6
Revises: 8c94bf630111
Create Date: 2026-10-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8c94bf630111'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Buat Tabel pkkpr_submissions
    op.create_table(
        'pkkpr_submissions',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('submission_no', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), server_default='BERUSAHA_PENILAIAN', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='DRAFT', nullable=False),
        sa.Column('sla_start_date', sa.Date(), nullable=True),
        sa.Column('elapsed_days', sa.Integer(), server_default='0', nullable=False),
        sa.Column('buffer_sla', sa.Integer(), server_default='0', nullable=False),
        
        # Subjek Pemohon
        sa.Column('applicant_type', sa.String(length=50), server_default='BADAN_USAHA', nullable=False),
        sa.Column('applicant_name', sa.String(length=255), nullable=False),
        sa.Column('applicant_nik', sa.String(length=16), nullable=True),
        sa.Column('applicant_nib', sa.String(length=50), nullable=True),
        sa.Column('applicant_npwp', sa.String(length=50), nullable=True),
        sa.Column('applicant_phone', sa.String(length=50), nullable=True),
        sa.Column('applicant_email', sa.String(length=255), nullable=True),
        
        # Kegiatan & Lokasi
        sa.Column('activity_description', sa.Text(), nullable=False),
        sa.Column('kbli_code', sa.String(length=10), nullable=True),
        sa.Column('location_address', sa.Text(), nullable=False),
        sa.Column('location_village', sa.String(length=100), nullable=False),
        sa.Column('location_district', sa.String(length=100), nullable=False),
        sa.Column('location_city', sa.String(length=100), server_default='Kabupaten Bogor', nullable=False),
        
        # Geometri & Luas
        sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
        sa.Column('proposed_land_area_m2', sa.Float(), nullable=False),
        sa.Column('approved_land_area_m2', sa.Float(), nullable=True),
        
        # Ketetapan Parameter Ruang
        sa.Column('approved_kdb_max', sa.Float(), nullable=True),
        sa.Column('approved_klb_max', sa.Float(), nullable=True),
        sa.Column('approved_kdh_min', sa.Float(), nullable=True),
        sa.Column('approved_gsb_min', sa.Float(), nullable=True),
        sa.Column('approved_max_floors', sa.Integer(), nullable=True),
        sa.Column('spatial_zone_code', sa.String(length=50), nullable=True),
        sa.Column('spatial_zone_name', sa.String(length=255), nullable=True),
        
        # Locking Mekanisme Petugas
        sa.Column('admin_lock_id', sa.Integer(), nullable=True),
        sa.Column('technical_lock_id', sa.Integer(), nullable=True),
        
        # Legalitas & Penerbitan SK
        sa.Column('sk_number', sa.String(length=100), nullable=True),
        sa.Column('sk_issued_date', sa.Date(), nullable=True),
        sa.Column('signed_pdf_url', sa.Text(), nullable=True),
        sa.Column('qr_code_hash', sa.String(length=255), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['admin_lock_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['technical_lock_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_no'),
        sa.UniqueConstraint('sk_number')
    )
    op.create_index(op.f('ix_pkkpr_submissions_id'), 'pkkpr_submissions', ['id'], unique=False)
    op.create_index(op.f('ix_pkkpr_submissions_submission_no'), 'pkkpr_submissions', ['submission_no'], unique=True)
    op.create_index(op.f('ix_pkkpr_submissions_user_id'), 'pkkpr_submissions', ['user_id'], unique=False)
    op.create_index(op.f('ix_pkkpr_submissions_status'), 'pkkpr_submissions', ['status'], unique=False)
    # op.create_index('idx_pkkpr_submissions_geom', 'pkkpr_submissions', ['geom'], unique=False, postgresql_using='gist')

    # 2. Buat Tabel pkkpr_files
    op.create_table(
        'pkkpr_files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pkkpr_id', sa.String(length=50), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.ForeignKeyConstraint(['pkkpr_id'], ['pkkpr_submissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pkkpr_files_pkkpr_id'), 'pkkpr_files', ['pkkpr_id'], unique=False)

    # 3. Buat Tabel pkkpr_fpr_reviews
    op.create_table(
        'pkkpr_fpr_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pkkpr_id', sa.String(length=50), nullable=False),
        sa.Column('meeting_date', sa.Date(), nullable=False),
        sa.Column('official_report_no', sa.String(length=100), nullable=False),
        sa.Column('recommendation', sa.String(length=50), nullable=False),
        
        sa.Column('ptp_bpn_number', sa.String(length=100), nullable=True),
        sa.Column('ptp_bpn_date', sa.Date(), nullable=True),
        sa.Column('ptp_notes', sa.Text(), nullable=True),
        
        sa.Column('zoning_compliance_notes', sa.Text(), nullable=False),
        sa.Column('infrastructure_notes', sa.Text(), nullable=True),
        sa.Column('environmental_notes', sa.Text(), nullable=True),
        sa.Column('minutes_pdf_url', sa.Text(), nullable=True),
        
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.ForeignKeyConstraint(['pkkpr_id'], ['pkkpr_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pkkpr_fpr_reviews_pkkpr_id'), 'pkkpr_fpr_reviews', ['pkkpr_id'], unique=False)

    # 4. Buat Tabel pkkpr_sk_draft
    op.create_table(
        'pkkpr_sk_draft',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pkkpr_id', sa.String(length=50), nullable=False),
        sa.Column('draft_sk_number', sa.String(length=100), nullable=False),
        sa.Column('considerations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('legal_bases', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('dictum_clauses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('obligations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('prepared_by_id', sa.Integer(), nullable=False),
        sa.Column('kabid_notes', sa.Text(), nullable=True),
        sa.Column('kabid_paraf_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.ForeignKeyConstraint(['pkkpr_id'], ['pkkpr_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prepared_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pkkpr_id')
    )

    # 5. Modifikasi Tabel permohonan yang ada: Tambahkan relasi pkkpr_id & pkkpr_origin
    op.add_column('permohonan', sa.Column('pkkpr_id', sa.String(length=50), nullable=True))
    op.add_column('permohonan', sa.Column('pkkpr_origin', sa.String(length=30), server_default='INTERNAL', nullable=False))
    op.create_foreign_key(
        'fk_permohonan_pkkpr_id',
        'permohonan',
        'pkkpr_submissions',
        ['pkkpr_id'],
        ['id'],
        ondelete='RESTRICT'
    )
    op.create_index(op.f('ix_permohonan_pkkpr_id'), 'permohonan', ['pkkpr_id'], unique=False)


def downgrade() -> None:
    # 1. Hapus relasi dari permohonan
    op.drop_constraint('fk_permohonan_pkkpr_id', 'permohonan', type_='foreignkey')
    op.drop_index(op.f('ix_permohonan_pkkpr_id'), table_name='permohonan')
    op.drop_column('permohonan', 'pkkpr_origin')
    op.drop_column('permohonan', 'pkkpr_id')

    # 2. Hapus pkkpr_sk_draft
    op.drop_table('pkkpr_sk_draft')

    # 3. Hapus pkkpr_fpr_reviews
    op.drop_index(op.f('ix_pkkpr_fpr_reviews_pkkpr_id'), table_name='pkkpr_fpr_reviews')
    op.drop_table('pkkpr_fpr_reviews')

    # 4. Hapus pkkpr_files
    op.drop_index(op.f('ix_pkkpr_files_pkkpr_id'), table_name='pkkpr_files')
    op.drop_table('pkkpr_files')

    # op.drop_index('idx_pkkpr_submissions_geom', table_name='pkkpr_submissions', postgresql_using='gist')
    op.drop_index(op.f('ix_pkkpr_submissions_status'), table_name='pkkpr_submissions')
    op.drop_index(op.f('ix_pkkpr_submissions_user_id'), table_name='pkkpr_submissions')
    op.drop_index(op.f('ix_pkkpr_submissions_submission_no'), table_name='pkkpr_submissions')
    op.drop_index(op.f('ix_pkkpr_submissions_id'), table_name='pkkpr_submissions')
    op.drop_table('pkkpr_submissions')
