"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Database Models [models.py] (REVISED v3)
============================================================================
Peran: Mendefinisikan skema tabel fisik database PostgreSQL & PostGIS
       menggunakan deklarasi tipe data statis SQLAlchemy 2.0 (Mapped).
       Diekspansi penuh untuk menampung seluruh detail formulir 10-tahap,
       metrik komparasi tiga sisi, dynamic checklist evaluasi, dan Master RDTR.
============================================================================
"""

from datetime import datetime, date, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Float, Integer, Date, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from src.infrastructure.database.connection import Base
from src.domain.entities.permohonan import KKPRVerdict  # Impor langsung dari domain (Single Source of Truth)

# Enum penampung status verifikasi satuan checklist dinas
import enum
class ChecklistStatus(str, enum.Enum):
    SESUAI = "Sesuai"
    SESUAI_BERSYARAT = "Sesuai Bersyarat"
    TIDAK_SESUAI = "Tidak Sesuai"
    PENDING = "Pending"

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="PEMOHON") # PEMOHON | ADMIN | TIM_TEKNIS | KABID_PUPR
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    nip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    permohonan: Mapped[List["PermohonanModel"]] = relationship("PermohonanModel", back_populates="user")


class PermohonanModel(Base):
    __tablename__ = "permohonan"

    # Relasi User
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="permohonan")

    # ─── KOORDINAT INTI & ADMINISTRASI ────────────────────────────────────────
    id_permohonan: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    submission_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    housing_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    developer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    land_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submission_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    buffer_sla: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sla_start_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    # ─── TAHAP 1: DATA PEMOHON (APPLICANT) ────────────────────────────────────
    applicant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="PERORANGAN") # PERORANGAN | BADAN_USAHA
    applicant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applicant_nik: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    applicant_nib: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applicant_npwp: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applicant_director_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applicant_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applicant_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applicant_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── TAHAP 2: DATA PENGAJUAN (SUBMISSION DETAILS) ─────────────────────────
    submission_type: Mapped[str] = mapped_column(String(50), nullable=False, default="BARU") # BARU | REVISI | PERPANJANGAN
    submission_category: Mapped[str] = mapped_column(String(50), nullable=False, default="PERUMAHAN") # PERUMAHAN | NON_PERUMAHAN | FASUM | INDUSTRI

    # ─── TAHAP 3: DATA LOKASI ADMINISTRATIF & TANAH (LOCATION) ───────────────
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_village: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="Kabupaten Bogor")
    location_province: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="Jawa Barat")
    location_full_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_ownership_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="SHM") # SHM | HGB | HAK_PAKAI | LAINNYA
    location_certificate_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_certificate_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ─── TAHAP 4: DATA KOORDINAT BATAS LUAR (OUTER BOUNDARY GEOM) ────────────
    # Menyimpan poligon batas luar bidang tanah BPN murni (SRID WGS84)
    geom: Mapped[Optional[Any]] = mapped_column(
        Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True), 
        nullable=True
    )
    # Parameter Kalibrasi Helmert 2D terhitung
    cad_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cad_param_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cad_param_b: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cad_param_tx: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cad_param_ty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cad_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cad_rotation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ─── TAHAP 5: DATA INFORMASI TATA RUANG (SPATIAL INFO) ────────────────────
    spatial_kkpr_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    spatial_land_use: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    spatial_green_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ─── TAHAP 6: PARAMETER TEKNIS BERSYARAT (TECHNICAL DETAILS) ─────────────
    # A. Kategori Perumahan
    tech_lot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_housing_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # SUBSIDI | NON_SUBSIDI | CAMPURAN
    tech_cemetery_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_road_row_main: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tech_road_row_local: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tech_water_system: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # B. Kategori Non-Perumahan (Gedung/Komersial)
    tech_building_blocks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_kdb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_klb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_kdh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_parking_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_max_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_total_floor_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # C. Kategori Fasilitas Umum (Fasum)
    tech_facility_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tech_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_disabled_access: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tech_special_parking: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tech_fire_protection: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # D. Kategori Industri
    tech_warehouse_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_road_load_mst: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tech_electricity_power: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tech_ipal_capacity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tech_green_buffer_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_tps_b3_provision: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ─── TAHAP 7: DATA KONSULTAN PERENCANA (CONSULTANT) ───────────────────────
    consultant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consultant_company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consultant_pic_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ─── TAHAP 10: PERNYATAAN KOMITMEN HUKUM (STATEMENT) ──────────────────────
    statement_agreed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Tambahkan kolom baru untuk menyimpan bukti hukum TTE
    signature_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    signed_pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    kabid_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── REVISI: METRIK INTENSITAS BANGUNAN (THREE-SIDED COMPARISON LEDGER) ──
    # A. Pengajuan Luas Fisik Mandiri Pemohon
    applicant_land_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicant_building_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # B. Parameter Teknis Pengajuan Pemohon (Proposed)
    applicant_kdb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicant_klb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicant_kdh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicant_gsb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicant_rth_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # C. Batas Baku Aturan RDTR (Bylaw - Auto-populated from MasterRDTR)
    bylaw_max_kdb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bylaw_max_klb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bylaw_min_kdh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bylaw_min_gsb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bylaw_min_rth_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # D. Hasil Hitung Manual Verifikator (Verified)
    verified_kdb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_klb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_kdh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_gsb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_rth_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # E. Hasil Kesimpulan KKPR Akhir
    kkpr_verdict: Mapped[Optional[KKPRVerdict]] = mapped_column(SQLEnum(KKPRVerdict), nullable=True)
    kkpr_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    kkpr_verifier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relasi Anak
    kompensasi: Mapped[List["LahanKompensasiModel"]] = relationship(
        "LahanKompensasiModel", 
        back_populates="permohonan", 
        cascade="all, delete-orphan"
    )
    files: Mapped[List["PermohonanFileModel"]] = relationship(
        "PermohonanFileModel", 
        back_populates="permohonan", 
        cascade="all, delete-orphan"
    )
    evaluasi_items: Mapped[List["EvaluasiChecklistItemModel"]] = relationship(
        "EvaluasiChecklistItemModel", 
        back_populates="permohonan", 
        cascade="all, delete-orphan"
    )


class EvaluasiChecklistItemModel(Base):
    """
    Menampung record aspek penilaian terverifikasi dinas secara individual.
    Menghilangkan hardcoded field demi prinsip Protected Variations.
    """
    __tablename__ = "evaluasi_checklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_permohonan: Mapped[str] = mapped_column(String(50), ForeignKey("permohonan.id_permohonan", ondelete="CASCADE"), nullable=False)
    
    aspek_code: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. 'REQ_ZONING', 'REQ_KDB'
    aspek_label: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "Kesesuaian dengan RTRW/RDTR"
    
    status_kelayakan: Mapped[ChecklistStatus] = mapped_column(
        SQLEnum(ChecklistStatus), nullable=False, default=ChecklistStatus.PENDING
    )
    catatan_verifikator: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True) # PDF coretan atau hitung dinas

    permohonan: Mapped["PermohonanModel"] = relationship("PermohonanModel", back_populates="evaluasi_items")


class MasterRDTRModel(Base):
    """
    Tabel Master batas regulasi (bylaw) RDTR Kabupaten Bogor secara dinamis.
    Bertindak sebagai Information Expert untuk membandingkan kepatuhan tata ruang.
    """
    __tablename__ = "master_rdtr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    village: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # PERUMAHAN | NON_PERUMAHAN | FASUM | INDUSTRI

    # Batas Regulasi Daerah Baku
    max_kdb: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    max_klb: Mapped[float] = mapped_column(Float, nullable=False, default=3.5)
    min_kdh: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    min_gsb: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    min_rth_area: Mapped[float] = mapped_column(Float, nullable=False, default=1400.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class LahanKompensasiModel(Base):
    __tablename__ = "lahan_kompensasi"

    id_kompensasi: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    id_permohonan: Mapped[str] = mapped_column(String(50), ForeignKey("permohonan.id_permohonan"), nullable=False)
    tipe_kompensasi: Mapped[str] = mapped_column(String(50), nullable=False)
    luas_kompensasi_m2: Mapped[float] = mapped_column(Float, nullable=False)

    # Poligon fisik spasial lahan pengganti (TPU / sawah)
    geom: Mapped[Optional[Any]] = mapped_column(
        Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True),
        nullable=True
    )

    status_pemenuhan: Mapped[str] = mapped_column(String(50), nullable=False)
    nilai_nominal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bukti_legalitas_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    permohonan: Mapped["PermohonanModel"] = relationship("PermohonanModel", back_populates="kompensasi")


class AuditTrailModel(Base):
    __tablename__ = "audit_trail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status_before: Mapped[str] = mapped_column(String(50), nullable=False)
    status_after: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    digital_signature_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SitePlanGeometryModel(Base):
    __tablename__ = "site_plan_geometries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_permohonan: Mapped[str] = mapped_column(String(50), ForeignKey("permohonan.id_permohonan", ondelete="CASCADE"), nullable=False)
    layer_name: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., 'PTSP_KDB', 'PTSP_KDH', 'PTSP_PSU_JALAN'

    # Menyimpan poligon rinci internal site plan (WGS84) hasil parsing DXF
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True),
        nullable=False
    )


class PermohonanFileModel(Base):
    __tablename__ = "permohonan_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_permohonan: Mapped[str] = mapped_column(String(50), ForeignKey("permohonan.id_permohonan", ondelete="CASCADE"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'document' or 'photo'
    file_key: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'legalDoc', 'photoNorth'
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    permohonan: Mapped["PermohonanModel"] = relationship("PermohonanModel", back_populates="files")