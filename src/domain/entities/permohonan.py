"""
============================================================================
SIPAS DOMAIN ENTITY — Permohonan [permohonan.py] (REVISED v5.4 - TYPE SAFE)
============================================================================
Peran: Entitas domain murni (Pure Python) yang merepresentasikan berkas
       pengajuan pengesahan site plan. Menegakkan aturan transisi status (SLA),
       matriks perbandingan tiga sisi berbasis dimensi fisik absolut (m²),
       perhitungan galat input spasial, pengamanan veto Kabid, perpindahan
       hak otorisasi TTE akhir ke Kepala Dinas (Kadis) secara legal, serta
       riwayat silsilah dokumen pengesahan terdahulu (Revisi/Perubahan).
       
Pembaruan v5.4: Pemisahan Ground Inspection (titik darat) dan 
               Aerial Inspection (drone video) untuk kepatuhan GRASP.
============================================================================
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional


class SubmissionStatus(str, Enum):
    """Representasi mutlak status berkas permohonan dalam alur birokrasi dinas."""
    DRAFT = 'Draft'
    MENUNGGU_VERIFIKASI = 'Pengajuan Dokumen'
    VERIFIKASI_ADMINISTRASI = 'Verifikasi Administrasi'
    VERIFIKASI_TEKNIS = 'Verifikasi Teknis'
    MENUNGGU_REKOMENDASI = 'Menunggu Rekomendasi'  # Tahap Peninjauan & Veto Kabid
    MENUNGGU_PERSETUJUAN = 'Menunggu Persetujuan'  # Tahap Pemeriksaan Draf SK oleh Kadis
    PROSES_TTE = 'Proses TTE'                      # Kunci Transaksi TTE Kadis Aktif
    DISETUJUI = 'Disetujui'                        # SK Berhasil Ditandatangani Kadis (Final)
    DITOLAK = 'Ditolak'                            # Berkas dikembalikan ke Pemohon untuk Revisi
    TIDAK_BERLAKU = 'Tidak Berlaku'                # SK Lama yang dinonaktifkan karena revisi baru


class DocumentCategory(str, Enum):
    """Kategorisasi tipe dokumen berdasarkan rentang luas bidang tanah terukur."""
    GAMBAR_SITUASI = 'Gambar Situasi'
    SITE_PLAN = 'Site Plan'
    MASTER_PLAN = 'Master Plan'


class KKPRVerdict(str, Enum):
    """Kesimpulan penilaian tata ruang yang dirumuskan oleh Tim Teknis."""
    SESUAI = "SESUAI"
    SESUAI_BERSYARAT = "SESUAI_BERSYARAT"
    PERLU_PERBAIKAN = "PERLU_PERBAIKAN"
    TIDAK_SESUAI = "TIDAK_SESUAI"


class PermohonanTpu:
    """Entitas domain murni untuk detail pemenuhan Tempat Pemakaman Umum (TPU)."""
    def __init__(
        self,
        id_tpu: str,
        id_permohonan: str,
        metode: str,
        luas: Optional[float] = None,
        nama_tpu: Optional[str] = None,
        pengurus_tpu: Optional[str] = None,
        no_pks: Optional[str] = None,
        nominal_kompensasi: Optional[float] = None,
        alamat: Optional[str] = None,
        koordinat: Optional[str] = None,
        bukti_dokumen_url: Optional[str] = None,
        status_verifikasi: str = "PENDING",
        catatan_verifikasi: Optional[str] = None,
        diverifikasi_oleh: Optional[str] = None,
        diverifikasi_pada: Optional[datetime] = None
    ):
        self.id_tpu = id_tpu
        self.id_permohonan = id_permohonan
        self.metode = metode
        self.luas = luas
        self.nama_tpu = nama_tpu
        self.pengurus_tpu = pengurus_tpu
        self.no_pks = no_pks
        self.nominal_kompensasi = nominal_kompensasi
        self.alamat = alamat
        self.koordinat = koordinat
        self.bukti_dokumen_url = bukti_dokumen_url
        self.status_verifikasi = status_verifikasi
        self.catatan_verifikasi = catatan_verifikasi
        self.diverifikasi_oleh = diverifikasi_oleh
        self.diverifikasi_pada = diverifikasi_pada


class SilsilahPermohonan:
    """Entitas domain murni untuk merepresentasikan hubungan silsilah pengesahan (Split/Merge)."""
    def __init__(
        self,
        id_silsilah: Optional[int],
        child_id: str,
        baseline_source: str,  # DIGITAL | LEGACY
        parent_id: Optional[str] = None,
        legacy_sk_number: Optional[str] = None,
        legacy_sk_date: Optional[date] = None,
        legacy_sk_doc_url: Optional[str] = None,
        parent_sk_number: Optional[str] = None,
        parent_housing_name: Optional[str] = None,
        parent_developer_name: Optional[str] = None
    ):
        self.id_silsilah = id_silsilah
        self.child_id = child_id
        self.baseline_source = baseline_source
        self.parent_id = parent_id
        self.legacy_sk_number = legacy_sk_number
        self.legacy_sk_date = legacy_sk_date
        self.legacy_sk_doc_url = legacy_sk_doc_url

        # Read-only attributes mapped for UI rendering and searchability
        self.parent_sk_number = parent_sk_number
        self.parent_housing_name = parent_housing_name
        self.parent_developer_name = parent_developer_name


class FieldInspectionLog:
    """Entitas domain murni untuk merepresentasikan log sidak titik fisik darat (Ground Inspection)."""
    def __init__(
        self,
        id: int,
        id_permohonan: str,
        inspector_name: str,
        timestamp: datetime,
        latitude: float,
        longitude: float,
        photo_url: str,
        is_verified: bool = True,
        distance_from_boundary_meters: Optional[float] = None,
        notes: Optional[str] = None
    ):
        self.id = id
        self.id_permohonan = id_permohonan
        self.inspector_name = inspector_name
        self.timestamp = timestamp
        self.latitude = latitude
        self.longitude = longitude
        self.photo_url = photo_url
        self.is_verified = is_verified
        self.distance_from_boundary_meters = distance_from_boundary_meters
        self.notes = notes


class AerialInspectionLog:
    """Entitas domain murni untuk merepresentasikan dokumentasi video udara drone (Aerial Inspection)."""
    def __init__(
        self,
        id: int,
        id_permohonan: str,
        pilot_name: str,
        timestamp: datetime,
        drone_video_url: str,
        flight_metadata: Optional[dict] = None,
        notes: Optional[str] = None
    ):
        self.id = id
        self.id_permohonan = id_permohonan
        self.pilot_name = pilot_name
        self.timestamp = timestamp
        self.drone_video_url = drone_video_url
        self.flight_metadata = flight_metadata or {}
        self.notes = notes


class Permohonan:
    """
    Entitas Bisnis Utama e-Siteplan.
    Mengatur siklus hidup administrasi, validasi data, komputasi galat spasial,
    pemeriksaan standar kepatuhan Perda secara terpadu, serta pembekuan SLA.
    """
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
        
        # Penanggung Jawab TTE Teknis & Legalitas Dinas
        kabid_signature: Optional[str] = None,       # Paraf verifikasi teknis Kabid
        kadis_signature: Optional[str] = None,       # Visual TTE Final Kepala Dinas

        # ─── REVISI: METRIK INTENSITAS TATA RUANG KOMPARASI (PEMOHON) ────────────
        applicant_land_area: Optional[float] = None,
        applicant_building_area: Optional[float] = None,
        applicant_kdb: Optional[float] = None,
        applicant_klb: Optional[float] = None,
        applicant_kdh: Optional[float] = None,
        applicant_gsb: Optional[float] = None,
        applicant_rth_area: Optional[float] = None,

        # BATAS MAKSIMAL / MINIMAL SESUAI ATURAN PERDA RDTR
        bylaw_max_kdb: Optional[float] = None,
        bylaw_max_klb: Optional[float] = None,
        bylaw_min_kdh: Optional[float] = None,
        bylaw_min_gsb: Optional[float] = None,
        bylaw_min_rth_area: Optional[float] = None,

        # HISTORICAL / MANUAL METRICS (FALLBACK VALUE)
        verified_kdb: Optional[float] = None,
        verified_klb: Optional[float] = None,
        verified_kdh: Optional[float] = None,
        verified_gsb: Optional[float] = None,
        verified_rth_area: Optional[float] = None,

        # ─── BARU: RAW DIMENSION METRICS TERVERIFIKASI TIM TEKNIS (m² / meter) ───
        verified_land_area: Optional[float] = None,         # Luas Lahan Hasil Plotting Riil (m²)
        verified_building_area: Optional[float] = None,     # Luas Tapak/Dasar Bangunan Terverifikasi (m²)
        verified_total_floor_area: Optional[float] = None,  # Luas Akumulasi Seluruh Lantai Terverifikasi (m²)
        
        # KEPUTUSAN VERIFIKASI
        kkpr_verdict: Optional[KKPRVerdict] = None,
        kkpr_verified_at: Optional[datetime] = None,
        kkpr_verifier_name: Optional[str] = None,

        # REFERENSI NOMOR SK TER-GENERATE DI ENTITAS PERMOHONAN
        sk_number: Optional[str] = None,

        # SILSILAH PERMOHONAN RELATIONSHIP (MANY-TO-MANY LEDGER)
        parents_lineage: Optional[List["SilsilahPermohonan"]] = None,

        tpu_detail: Optional["PermohonanTpu"] = None,
        baseline_source: Optional[str] = None,
        admin_lock_id: Optional[int] = None,
        admin_lock_name: Optional[str] = None,
        teknisi_lock_id: Optional[int] = None,
        teknisi_lock_name: Optional[str] = None,

        # PEMBARUAN v5.4: Relasi Inspeksi Darat & Udara Terpisah
        inspection_logs: Optional[List[FieldInspectionLog]] = None,
        aerial_inspection: Optional[AerialInspectionLog] = None,
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
        
        # Atribut Integrasi Keamanan TTE BSrE (Kepala Dinas)
        self.signature_hash = signature_hash
        self.signed_pdf_url = signed_pdf_url
        self.kabid_signature = kabid_signature
        self.kadis_signature = kadis_signature

        # Atribut Metrik Intensitas Tata Ruang Komparasi (Proposed)
        self.applicant_land_area = applicant_land_area or resolved_land_area
        self.applicant_building_area = applicant_building_area
        self.applicant_kdb = applicant_kdb
        self.applicant_klb = applicant_klb
        self.applicant_kdh = applicant_kdh
        self.applicant_gsb = applicant_gsb
        self.applicant_rth_area = applicant_rth_area

        # Atribut Aturan Perda
        self.bylaw_max_kdb = bylaw_max_kdb
        self.bylaw_max_klb = bylaw_max_klb
        self.bylaw_min_kdh = bylaw_min_kdh
        self.bylaw_min_gsb = bylaw_min_gsb
        self.bylaw_min_rth_area = bylaw_min_rth_area

        # Atribut Verifikasi Manual (Fallback)
        self.verified_kdb = verified_kdb
        self.verified_klb = verified_klb
        self.verified_kdh = verified_kdh
        self.verified_gsb = verified_gsb
        self.verified_rth_area = verified_rth_area

        # Atribut Verifikasi Spasial Riil (m²)
        self.verified_land_area = verified_land_area
        self.verified_building_area = verified_building_area
        self.verified_total_floor_area = verified_total_floor_area

        self.kkpr_verdict = kkpr_verdict
        self.kkpr_verified_at = kkpr_verified_at
        self.kkpr_verifier_name = kkpr_verifier_name

        self.sk_number = sk_number

        # SILSILAH PERMOHONAN RELATIONSHIP
        self.parents_lineage = parents_lineage or []

        self.tpu_detail = tpu_detail
        self.baseline_source = baseline_source
        self.admin_lock_id = admin_lock_id
        self.admin_lock_name = admin_lock_name
        self.teknisi_lock_id = teknisi_lock_id
        self.teknisi_lock_name = teknisi_lock_name

        # PEMBARUAN v5.4: Inisialisasi Sidak Darat & Udara
        self.inspection_logs = inspection_logs or []
        self.aerial_inspection = aerial_inspection

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
        """
        if self.status in [SubmissionStatus.DRAFT, SubmissionStatus.DITOLAK]:
            total_allocated = self.base_sla + self.buffer_sla
            return total_allocated - self.elapsed_days
            
        total_sla = self.base_sla + self.buffer_sla
        active_elapsed = (date.today() - self.sla_start_date).days
        return total_sla - active_elapsed

    def add_complexity_buffer(self, days: int) -> None:
        if days < 0:
            raise ValueError("Tambahan hari kompleksitas tidak boleh negatif.")
        self.buffer_sla += days

    def transition_status(self, new_status: SubmissionStatus) -> None:
        """
        State Machine Aturan Transisi Status Berkas Resmi.
        Menegakkan Segregation of Duties (SoD), aturan kelengkapan sidak fisik,
        dan keamanan birokrasi penataan ruang daerah.
        """
        allowed_transitions = {
            SubmissionStatus.DRAFT: [
                SubmissionStatus.MENUNGGU_VERIFIKASI
            ],
            
            SubmissionStatus.MENUNGGU_VERIFIKASI: [
                SubmissionStatus.VERIFIKASI_ADMINISTRASI,
                SubmissionStatus.VERIFIKASI_TEKNIS,
                SubmissionStatus.DITOLAK
            ],
            
            SubmissionStatus.VERIFIKASI_ADMINISTRASI: [
                SubmissionStatus.VERIFIKASI_TEKNIS,
                SubmissionStatus.DITOLAK
            ],
            
            SubmissionStatus.VERIFIKASI_TEKNIS: [
                SubmissionStatus.MENUNGGU_REKOMENDASI,
                SubmissionStatus.DITOLAK,
                SubmissionStatus.VERIFIKASI_ADMINISTRASI
            ],
            
            SubmissionStatus.MENUNGGU_REKOMENDASI: [
                SubmissionStatus.MENUNGGU_PERSETUJUAN,
                SubmissionStatus.VERIFIKASI_TEKNIS,
                SubmissionStatus.DITOLAK
            ],
            
            SubmissionStatus.MENUNGGU_PERSETUJUAN: [
                SubmissionStatus.PROSES_TTE,
                SubmissionStatus.MENUNGGU_REKOMENDASI,
                SubmissionStatus.DITOLAK
            ],
            
            SubmissionStatus.PROSES_TTE: [
                SubmissionStatus.DISETUJUI,
                SubmissionStatus.DITOLAK,
                SubmissionStatus.MENUNGGU_PERSETUJUAN
            ],
            
            SubmissionStatus.DISETUJUI: [],
            
            SubmissionStatus.DITOLAK: [
                SubmissionStatus.MENUNGGU_VERIFIKASI,
                SubmissionStatus.VERIFIKASI_TEKNIS
            ]
        }

        if new_status not in allowed_transitions[self.status]:
            raise IllegalStateTransitionError(
                f"Ilegal: Tidak diizinkan melakukan transisi status dari '{self.status.value}' langsung ke '{new_status.value}'."
            )

        # PEMBARUAN v5.4: Penegakan aturan kelengkapan sidak darat & udara sebelum Telaah Staf diajukan ke Kabid
        if new_status == SubmissionStatus.MENUNGGU_REKOMENDASI:
            # Skenario kategori wajib yang memiliki dampak tata ruang masif
            if self.submission_category in ["PERUMAHAN", "INDUSTRI", "NON_PERUMAHAN"]:
                if not self.inspection_logs or len(self.inspection_logs) == 0:
                    raise ValueError(
                        f"Gagal: Minimal harus terdapat 1 data log kunjungan lapangan darat (Ground Inspection) "
                        f"sebelum berkas '{self.submission_no}' dapat diajukan rekomendasi."
                    )
                # Video drone udara wajib mutlak untuk perumahan & industri
                if self.submission_category in ["PERUMAHAN", "INDUSTRI"] and not self.aerial_inspection:
                    raise ValueError(
                        f"Gagal: Rekaman video udara (Aerial Drone Inspection) wajib diunggah untuk kategori "
                        f"'{self.submission_category}' sebelum draf Telaah Staf diajukan ke Kepala Bidang."
                    )

        if new_status == SubmissionStatus.DITOLAK and self.status not in [SubmissionStatus.DRAFT, SubmissionStatus.DITOLAK]:
            self.elapsed_days = max(self.elapsed_days, (date.today() - self.sla_start_date).days)
        
        RESET_SLA_STATUSES = [
            SubmissionStatus.MENUNGGU_VERIFIKASI,
            SubmissionStatus.VERIFIKASI_TEKNIS,
            SubmissionStatus.MENUNGGU_REKOMENDASI,
            SubmissionStatus.MENUNGGU_PERSETUJUAN,
            SubmissionStatus.PROSES_TTE
        ]
        if new_status in RESET_SLA_STATUSES:
            self.sla_start_date = date.today()
            self.elapsed_days = 0
            self.buffer_sla = 0

        self.status = new_status

    def attach_signature(self, hash: str, url: str, is_approved: bool = True) -> None:
        """Membubuhkan TTE Dinas Resmi milik Kepala Dinas pada draf SK Pengesahan final."""
        target_status = SubmissionStatus.DISETUJUI if is_approved else SubmissionStatus.DITOLAK
        self.transition_status(target_status)
        self.signature_hash = hash
        self.signed_pdf_url = url

    # ─── SECTION: AUTOCALCULATED METRICS & ERROR DETECTORS (INFORMATION EXPERT) ───

    def compute_applicant_kdb_percentage(self) -> Optional[float]:
        """Menghitung persentase KDB usulan pemohon berdasarkan input luas fisik."""
        if self.applicant_land_area and self.applicant_building_area:
            return (self.applicant_building_area / self.applicant_land_area) * 100.0
        return self.applicant_kdb

    @property
    def proposed_kdb_percentage(self) -> Optional[float]:
        """Properti pemohon untuk persentase KDB usulan."""
        return self.compute_applicant_kdb_percentage()

    @property
    def proposed_klb_ratio(self) -> Optional[float]:
        """Menghitung rasio KLB usulan pemohon."""
        if self.applicant_land_area and self.tech_total_floor_area:
            return self.tech_total_floor_area / self.applicant_land_area
        return self.applicant_klb

    @property
    def proposed_kdh_percentage(self) -> Optional[float]:
        """Menghitung persentase KDH usulan pemohon."""
        if self.applicant_land_area and self.applicant_rth_area:
            return (self.applicant_rth_area / self.applicant_land_area) * 100.0
        return self.applicant_kdh

    @property
    def verified_kdb_percentage(self) -> Optional[float]:
        """
        Menghitung otomatis persentase KDB hasil verifikasi fisik dinas.
        Fungsi ini melakukan perhitungan dinamis dari raw data luasan verified jika tersedia,
        dan secara aman jatuh ke fallback manual (verified_kdb) jika field kosong.
        """
        if self.verified_building_area is not None and self.verified_land_area:
            return (self.verified_building_area / self.verified_land_area) * 100.0
        return self.verified_kdb

    @property
    def verified_klb_ratio(self) -> Optional[float]:
        """
        Menghitung otomatis rasio KLB hasil verifikasi fisik dinas.
        Secara aman jatuh ke fallback manual (verified_klb) jika field kosong.
        """
        if self.verified_total_floor_area is not None and self.verified_land_area:
            return self.verified_total_floor_area / self.verified_land_area
        return self.verified_klb

    @property
    def verified_kdh_percentage(self) -> Optional[float]:
        """
        Menghitung otomatis persentase KDH hasil verifikasi fisik dinas.
        Secara aman jatuh ke fallback manual (verified_kdh) jika field kosong.
        """
        if self.verified_rth_area is not None and self.verified_land_area:
            return (self.verified_rth_area / self.verified_land_area) * 100.0
        return self.verified_kdh

    # ─── SUB-SECTION: QUANTITATIVE ERROR / GALAT SPASIAL (m² & %) ───

    @property
    def land_area_error_sqm(self) -> Optional[float]:
        """Menghitung selisih absolut luas lahan terverifikasi dengan deklarasi pemohon (Verified - Proposed)."""
        if self.verified_land_area is not None and self.applicant_land_area is not None:
            return self.verified_land_area - self.applicant_land_area
        return None

    @property
    def land_area_error_percent(self) -> Optional[float]:
        """Menghitung selisih relatif luas lahan dalam bentuk persentase (%) terhadap usulan pemohon."""
        error = self.land_area_error_sqm
        if error is not None and self.applicant_land_area:
            return (error / self.applicant_land_area) * 100.0
        return None

    @property
    def building_area_error_sqm(self) -> Optional[float]:
        """Menghitung selisih absolut luas dasar tapak bangunan (Verified - Proposed)."""
        if self.verified_building_area is not None and self.applicant_building_area is not None:
            return self.verified_building_area - self.applicant_building_area
        return None

    @property
    def building_area_error_percent(self) -> Optional[float]:
        """Menghitung selisih relatif luas dasar bangunan dalam bentuk persentase (%)."""
        error = self.building_area_error_sqm
        if error is not None and self.applicant_building_area:
            return (error / self.applicant_building_area) * 100.0
        return None

    @property
    def total_floor_area_error_sqm(self) -> Optional[float]:
        """Menghitung selisih absolut luas total lantai bangunan (Verified - Proposed)."""
        proposed_total_floor_area = self.tech_total_floor_area
        if self.verified_total_floor_area is not None and proposed_total_floor_area is not None:
            return self.verified_total_floor_area - proposed_total_floor_area
        return None

    @property
    def total_floor_area_error_percent(self) -> Optional[float]:
        """Menghitung selisih relatif luas total lantai bangunan dalam bentuk persentase (%)."""
        error = self.total_floor_area_error_sqm
        proposed_total_floor_area = self.tech_total_floor_area
        if error is not None and proposed_total_floor_area:
            return (error / proposed_total_floor_area) * 100.0
        return None

    @property
    def rth_area_error_sqm(self) -> Optional[float]:
        """Menghitung selisih absolut luas RTH (Verified - Proposed)."""
        if self.verified_rth_area is not None and self.applicant_rth_area is not None:
            return self.verified_rth_area - self.applicant_rth_area
        return None

    @property
    def rth_area_error_percent(self) -> Optional[float]:
        """Menghitung selisih relatif luas RTH dalam bentuk persentase (%)."""
        error = self.rth_area_error_sqm
        if error is not None and self.applicant_rth_area:
            return (error / self.applicant_rth_area) * 100.0
        return None

    # ─── SUB-SECTION: AUTOMATED BYLAWS AUDIT (COMPLIANCE FLAGS) ───

    @property
    def is_kdb_compliant(self) -> Optional[bool]:
        """Menilai kepatuhan teknis KDB terhadap aturan batas atas Perda RDTR."""
        kdb = self.verified_kdb_percentage
        if kdb is not None and self.bylaw_max_kdb is not None:
            return kdb <= self.bylaw_max_kdb
        return None

    @property
    def is_klb_compliant(self) -> Optional[bool]:
        """Menilai kepatuhan teknis KLB terhadap aturan batas atas Perda RDTR."""
        klb = self.verified_klb_ratio
        if klb is not None and self.bylaw_max_klb is not None:
            return klb <= self.bylaw_max_klb
        return None

    @property
    def is_kdh_compliant(self) -> Optional[bool]:
        """Menilai kepatuhan teknis KDH terhadap aturan batas bawah Perda RDTR."""
        kdh = self.verified_kdh_percentage
        if kdh is not None and self.bylaw_min_kdh is not None:
            return kdh >= self.bylaw_min_kdh
        return None

    @property
    def is_gsb_compliant(self) -> Optional[bool]:
        """Menilai kepatuhan teknis GSB terhadap aturan batas bawah Perda RDTR."""
        gsb = self.verified_gsb
        if gsb is not None and self.bylaw_min_gsb is not None:
            return gsb >= self.bylaw_min_gsb
        return None

    @property
    def is_rth_area_compliant(self) -> Optional[bool]:
        """Menilai kepatuhan teknis luas wilayah RTH terhadap aturan batas bawah Perda RDTR."""
        rth = self.verified_rth_area
        if rth is not None and self.bylaw_min_rth_area is not None:
            return rth >= self.bylaw_min_rth_area
        return None

    # ─── BARU: PROPERTIES UNTUK READ-ONLY METADATA RUJUKAN SILSILAH SK LAMA (ANTI PYLANCE UNBOUND) ───
    @property
    def replaced_sk_number(self) -> Optional[str]:
        """Menyisir silsilah permohonan (parents_lineage) untuk mendapatkan nomor SK lama rujukan."""
        for silsilah in self.parents_lineage:
            if silsilah.baseline_source == "DIGITAL":
                return silsilah.parent_sk_number or silsilah.legacy_sk_number
            elif silsilah.baseline_source == "LEGACY":
                return silsilah.legacy_sk_number
        return None

    @property
    def replaced_sk_date(self) -> Optional[date]:
        """Menyisir silsilah permohonan (parents_lineage) untuk mendapatkan tanggal terbit SK rujukan."""
        for silsilah in self.parents_lineage:
            return silsilah.legacy_sk_date
        return None

    @property
    def replaced_sk_doc_url(self) -> Optional[str]:
        """Menyisir silsilah permohonan (parents_lineage) untuk mendapatkan URL dokumen SK rujukan."""
        for silsilah in self.parents_lineage:
            return silsilah.legacy_sk_doc_url
        return None

    # ─── PEMBARUAN v5.4: INDIKATOR KELENGKAPAN DRONE ──────────────────────────
    @property
    def has_aerial_inspection(self) -> bool:
        """Menilai ketersediaan video udara drone terpasang."""
        return self.aerial_inspection is not None


class IllegalStateTransitionError(Exception):
    pass