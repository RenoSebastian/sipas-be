"""
============================================================================
SIPAS DOMAIN ENTITY — Permohonan [permohonan.py] (REVISED v3 - TYPE SAFE)
============================================================================
Peran: Entitas domain murni (Pure Python) yang merepresentasikan data
       pengisian pengesahan site plan serta menegakkan aturan bisnis (invariants)
       terkait klasifikasi objek, durasi SLA, perbandingan metrik tiga sisi
       (Proposed vs Bylaw vs Verified), dan mutasi status [sipas-fe.txt].
============================================================================
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

class SubmissionStatus(str, Enum):
    DRAFT = 'Draft'
    MENUNGGU_VERIFIKASI = 'Menunggu Verifikasi'
    VERIFIKASI_ADMINISTRASI = 'Verifikasi Administrasi'
    VERIFIKASI_TEKNIS = 'Verifikasi Teknis'
    MENUNGGU_PERSETUJUAN = 'Menunggu Persetujuan'
    PROSES_TTE = 'Proses TTE'
    DISETUJUI = 'Disetujui'
    DITOLAK = 'Ditolak'

class DocumentCategory(str, Enum):
    GAMBAR_SITUASI = 'Gambar Situasi'
    SITE_PLAN = 'Site Plan'
    MASTER_PLAN = 'Master Plan'

class KKPRVerdict(str, Enum):
    SESUAI = "Sesuai"
    SESUAI_BERSYARAT = "Sesuai Bersyarat"
    PERLU_PERBAIKAN = "Perlu Perbaikan / Revisi"
    TIDAK_SESUAI = "Tidak Sesuai / Ditolak"

class Permohonan:
    def __init__(
        self,
        id_permohonan: str,
        submission_no: str,
        submission_date: date,
        housing_name: Optional[str] = None,
        developer_name: Optional[str] = None,
        land_area: Optional[float] = None,
        status: SubmissionStatus = SubmissionStatus.DRAFT,
        buffer_sla: int = 0,
        elapsed_days: int = 0,
        sla_start_date: Optional[date] = None,
        
        # ─── TAHAP 1: DATA PEMOHON (APPLICANT) ────────────────────────────────────
        applicant_type: Optional[str] = "PERORANGAN",
        applicant_name: Optional[str] = None,
        applicant_nik: Optional[str] = None,
        applicant_nib: Optional[str] = None,
        applicant_npwp: Optional[str] = None,
        applicant_director_name: Optional[str] = None,
        applicant_phone: Optional[str] = None,
        applicant_email: Optional[str] = None,
        applicant_address: Optional[str] = None,
        
        # ─── TAHAP 2: DATA PENGAJUAN (SUBMISSION DETAILS) ─────────────────────────
        submission_type: Optional[str] = "BARU",
        submission_category: Optional[str] = "PERUMAHAN",
        
        # ─── TAHAP 3: DATA LOKASI ADMINISTRATIF & TANAH (LOCATION) ───────────────
        location_name: Optional[str] = None,
        location_village: Optional[str] = None,
        location_district: Optional[str] = None,
        location_city: Optional[str] = "Kabupaten Bogor",
        location_province: Optional[str] = "Jawa Barat",
        location_full_address: Optional[str] = None,
        location_ownership_status: Optional[str] = "SHM",
        location_certificate_number: Optional[str] = None,
        location_certificate_owner: Optional[str] = None,
        
        # ─── TAHAP 4: DATA KOORDINAT BATAS LUAR (OUTER BOUNDARY GEOM) ────────────
        cad_file_name: Optional[str] = None,
        cad_param_a: Optional[float] = None,
        cad_param_b: Optional[float] = None,
        cad_param_tx: Optional[float] = None,
        cad_param_ty: Optional[float] = None,
        cad_scale: Optional[float] = None,
        cad_rotation: Optional[float] = None,
        
        # ─── TAHAP 5: DATA INFORMASI TATA RUANG (SPATIAL INFO) ────────────────────
        spatial_kkpr_number: Optional[str] = None,
        spatial_land_use: Optional[str] = None,
        spatial_green_area: Optional[float] = 0.0,
        
        # ─── TAHAP 6: PARAMETER TEKNIS BERSYARAT (TECHNICAL DETAILS) ─────────────
        tech_lot_count: Optional[int] = None,
        tech_housing_type: Optional[str] = None,
        tech_cemetery_area: Optional[float] = None,
        tech_road_row_main: Optional[str] = None,
        tech_road_row_local: Optional[str] = None,
        tech_water_system: Optional[str] = None,
        tech_water_source: Optional[str] = None,
        
        tech_building_blocks: Optional[int] = None,
        tech_kdb: Optional[float] = None,
        tech_klb: Optional[float] = None,
        tech_kdh: Optional[float] = None,
        tech_parking_capacity: Optional[int] = None,
        tech_max_floors: Optional[int] = None,
        tech_total_floor_area: Optional[float] = None,
        
        tech_facility_type: Optional[str] = None,
        tech_capacity: Optional[int] = None,
        tech_disabled_access: Optional[str] = None,
        tech_special_parking: Optional[str] = None,
        tech_fire_protection: Optional[str] = None,
        
        tech_warehouse_count: Optional[int] = None,
        tech_road_load_mst: Optional[str] = None,
        tech_electricity_power: Optional[str] = None,
        tech_ipal_capacity: Optional[str] = None,
        tech_green_buffer_area: Optional[float] = None,
        tech_tps_b3_provision: Optional[str] = None,
        
        # ─── TAHAP 7: DATA KONSULTAN PERENCANA (CONSULTANT) ───────────────────────
        consultant_name: Optional[str] = None,
        consultant_company_name: Optional[str] = None,
        consultant_pic_name: Optional[str] = None,
        
        # ─── TAHAP 10: PERNYATAAN KOMITMEN HUKUM (STATEMENT) ──────────────────────
        statement_agreed: bool = False,
        polygon: Optional[list] = None,
        user_id: Optional[int] = None,
        signature_hash: Optional[str] = None,
        signed_pdf_url: Optional[str] = None,
        kabid_signature: Optional[str] = None,

        # ─── REVISI: METRIK INTENSITAS BANGUNAN (THREE-SIDED COMPARISON LEDGER) ──
        applicant_land_area: Optional[float] = None,
        applicant_building_area: Optional[float] = None,
        applicant_kdb: Optional[float] = None,
        applicant_klb: Optional[float] = None,
        applicant_kdh: Optional[float] = None,
        applicant_gsb: Optional[float] = None,
        applicant_rth_area: Optional[float] = None,

        bylaw_max_kdb: Optional[float] = None,
        bylaw_max_klb: Optional[float] = None,
        bylaw_min_kdh: Optional[float] = None,
        bylaw_min_gsb: Optional[float] = None,
        bylaw_min_rth_area: Optional[float] = None,

        verified_kdb: Optional[float] = None,
        verified_klb: Optional[float] = None,
        verified_kdh: Optional[float] = None,
        verified_gsb: Optional[float] = None,
        verified_rth_area: Optional[float] = None,

        kkpr_verdict: Optional[KKPRVerdict] = None,
        kkpr_verified_at: Optional[datetime] = None,
        kkpr_verifier_name: Optional[str] = None
    ):
        self.id_permohonan = id_permohonan
        self.submission_no = submission_no
        self.housing_name = housing_name
        self.developer_name = developer_name
        
        resolved_land_area = applicant_land_area or land_area
        if resolved_land_area is not None and resolved_land_area <= 0:
            raise ValueError("Luas lahan harus bernilai positif.")
        self.land_area = resolved_land_area
        
        self.submission_date = submission_date
        self.status = status
        self.buffer_sla = buffer_sla
        self.elapsed_days = elapsed_days
        self.sla_start_date = sla_start_date or submission_date

        self.applicant_type = applicant_type
        self.applicant_name = applicant_name or developer_name
        self.applicant_nik = applicant_nik
        self.applicant_nib = applicant_nib
        self.applicant_npwp = applicant_npwp
        self.applicant_director_name = applicant_director_name
        self.applicant_phone = applicant_phone
        self.applicant_email = applicant_email
        self.applicant_address = applicant_address
        
        self.submission_type = submission_type
        self.submission_category = submission_category
        
        self.location_name = location_name or housing_name
        self.location_village = location_village
        self.location_district = location_district
        self.location_city = location_city
        self.location_province = location_province
        self.location_full_address = location_full_address
        self.location_ownership_status = location_ownership_status
        self.location_certificate_number = location_certificate_number
        self.location_certificate_owner = location_certificate_owner
        
        self.cad_file_name = cad_file_name
        self.cad_param_a = cad_param_a
        self.cad_param_b = cad_param_b
        self.cad_param_tx = cad_param_tx
        self.cad_param_ty = cad_param_ty
        self.cad_scale = cad_scale
        self.cad_rotation = cad_rotation
        
        self.spatial_kkpr_number = spatial_kkpr_number
        self.spatial_land_use = spatial_land_use
        self.spatial_green_area = spatial_green_area
        
        self.tech_lot_count = tech_lot_count
        self.tech_housing_type = tech_housing_type
        self.tech_cemetery_area = tech_cemetery_area
        self.tech_road_row_main = tech_road_row_main
        self.tech_road_row_local = tech_road_row_local
        self.tech_water_system = tech_water_system
        self.tech_water_source = tech_water_source
        
        self.tech_building_blocks = tech_building_blocks
        self.tech_kdb = tech_kdb
        self.tech_klb = tech_klb
        self.tech_kdh = tech_kdh
        self.tech_parking_capacity = tech_parking_capacity
        self.tech_max_floors = tech_max_floors
        self.tech_total_floor_area = tech_total_floor_area
        
        self.tech_facility_type = tech_facility_type
        self.tech_capacity = tech_capacity
        self.tech_disabled_access = tech_disabled_access
        self.tech_special_parking = tech_special_parking
        self.tech_fire_protection = tech_fire_protection
        
        self.tech_warehouse_count = tech_warehouse_count
        self.tech_road_load_mst = tech_road_load_mst
        self.tech_electricity_power = tech_electricity_power
        self.tech_ipal_capacity = tech_ipal_capacity
        self.tech_green_buffer_area = tech_green_buffer_area
        self.tech_tps_b3_provision = tech_tps_b3_provision
        
        self.consultant_name = consultant_name
        self.consultant_company_name = consultant_company_name
        self.consultant_pic_name = consultant_pic_name
        
        self.statement_agreed = statement_agreed
        self.polygon = polygon
        self.user_id = user_id
        self.signature_hash = signature_hash
        self.signed_pdf_url = signed_pdf_url
        self.kabid_signature = kabid_signature

        # ─── REVISI ATRIBUT BARU (METRIK KOMPARASI & KKPR VERDICT) ───
        self.applicant_land_area = applicant_land_area or resolved_land_area
        self.applicant_building_area = applicant_building_area
        self.applicant_kdb = applicant_kdb
        self.applicant_klb = applicant_klb
        self.applicant_kdh = applicant_kdh
        self.applicant_gsb = applicant_gsb
        self.applicant_rth_area = applicant_rth_area

        self.bylaw_max_kdb = bylaw_max_kdb
        self.bylaw_max_klb = bylaw_max_klb
        self.bylaw_min_kdh = bylaw_min_kdh
        self.bylaw_min_gsb = bylaw_min_gsb
        self.bylaw_min_rth_area = bylaw_min_rth_area

        self.verified_kdb = verified_kdb
        self.verified_klb = verified_klb
        self.verified_kdh = verified_kdh
        self.verified_gsb = verified_gsb
        self.verified_rth_area = verified_rth_area

        self.kkpr_verdict = kkpr_verdict
        self.kkpr_verified_at = kkpr_verified_at
        self.kkpr_verifier_name = kkpr_verifier_name

    @property
    def document_category(self) -> DocumentCategory:
        land_area_to_check = self.applicant_land_area or self.land_area
        if land_area_to_check is None:
            return DocumentCategory.SITE_PLAN
        if land_area_to_check <= 2500:
            return DocumentCategory.GAMBAR_SITUASI
        elif land_area_to_check < 500000:
            return DocumentCategory.SITE_PLAN
        else:
            return DocumentCategory.MASTER_PLAN

    @property
    def base_sla(self) -> int:
        """Menetapkan durasi SLA dasar dalam satuan hari (selalu 30 hari/1 bulan)."""
        return 30

    @property
    def remaining_sla_days(self) -> int:
        """
        Menghitung sisa hari pengerjaan SLA secara dinamis untuk tahap saat ini.
        Membekukan penghitungan waktu (Clock Pause) jika berkas membutuhkan revisi.
        Mendukung nilai negatif (terlambat) untuk menandakan SLA terlampaui.
        """
        from datetime import date
        # SLA dibekukan (paused) jika status DRAFT atau DITOLAK (revisi pemohon)
        if self.status in [SubmissionStatus.DRAFT, SubmissionStatus.DITOLAK]:
            total_allocated = self.base_sla + self.buffer_sla
            # Gunakan elapsed_days statis yang telah dikunci saat status berpindah ke DITOLAK
            return total_allocated - self.elapsed_days
            
        total_sla = self.base_sla + self.buffer_sla
        # Hitung elapsed days aktif secara dinamis sejak tanggal sla_start_date
        active_elapsed = (date.today() - self.sla_start_date).days
        return total_sla - active_elapsed

    def add_complexity_buffer(self, days: int) -> None:
        if days < 0:
            raise ValueError("Tambahan hari kompleksitas tidak boleh negatif.")
        self.buffer_sla += days

    def transition_status(self, new_status: SubmissionStatus) -> None:
        allowed_transitions = {
            SubmissionStatus.DRAFT: [SubmissionStatus.MENUNGGU_VERIFIKASI],
            SubmissionStatus.MENUNGGU_VERIFIKASI: [
                SubmissionStatus.VERIFIKASI_ADMINISTRASI,
                SubmissionStatus.VERIFIKASI_TEKNIS,
                SubmissionStatus.DITOLAK,
            ],
            SubmissionStatus.VERIFIKASI_ADMINISTRASI: [
                SubmissionStatus.VERIFIKASI_TEKNIS,
                SubmissionStatus.DITOLAK,
            ],
            SubmissionStatus.VERIFIKASI_TEKNIS: [
                SubmissionStatus.MENUNGGU_PERSETUJUAN,
                SubmissionStatus.DITOLAK,
                SubmissionStatus.VERIFIKASI_ADMINISTRASI,
            ],
            SubmissionStatus.MENUNGGU_PERSETUJUAN: [
                SubmissionStatus.PROSES_TTE,
                SubmissionStatus.DITOLAK,
                SubmissionStatus.VERIFIKASI_TEKNIS,
            ],
            SubmissionStatus.PROSES_TTE: [
                SubmissionStatus.DISETUJUI,
                SubmissionStatus.MENUNGGU_PERSETUJUAN,
            ],
            SubmissionStatus.DISETUJUI: [],
            SubmissionStatus.DITOLAK: [SubmissionStatus.MENUNGGU_VERIFIKASI],
        }

        if new_status not in allowed_transitions[self.status]:
            raise IllegalStateTransitionError(
                f"Ilegal: Tidak diizinkan melakukan transisi status dari '{self.status.value}' langsung ke '{new_status.value}'."
            )
        
        from datetime import date

        # Kunci penghitungan hari aktif (elapsed_days) saat status berpindah ke DITOLAK (paused)
        if new_status == SubmissionStatus.DITOLAK and self.status not in [SubmissionStatus.DRAFT, SubmissionStatus.DITOLAK]:
            self.elapsed_days = max(self.elapsed_days, (date.today() - self.sla_start_date).days)
        
        # Reset SLA (1 bulan/30 hari baru) saat berpindah ke tahap peninjauan yang berbeda
        RESET_SLA_STATUSES = [
            SubmissionStatus.MENUNGGU_VERIFIKASI,
            SubmissionStatus.VERIFIKASI_TEKNIS,
            SubmissionStatus.MENUNGGU_PERSETUJUAN,
            SubmissionStatus.PROSES_TTE
        ]
        if new_status in RESET_SLA_STATUSES:
            self.sla_start_date = date.today()
            self.elapsed_days = 0
            self.buffer_sla = 0

        self.status = new_status

    def attach_signature(self, hash: str, url: str) -> None:
        self.transition_status(SubmissionStatus.DISETUJUI)
        self.signature_hash = hash
        self.signed_pdf_url = url

    def compute_applicant_kdb_percentage(self) -> Optional[float]:
        if self.applicant_land_area and self.applicant_building_area:
            return (self.applicant_building_area / self.applicant_land_area) * 100.0
        return self.applicant_kdb

class IllegalStateTransitionError(Exception):
    pass