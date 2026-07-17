"""
============================================================================
SIPAS USE CASE — Submit Permohonan [submit_permohonan.py] (REVISED v5.2)
============================================================================
Peran: Mengorkestrasikan alur pendaftaran permohonan baru satu pintu,
       menegakkan validasi skema dasar, menyimpan entitas ke repositori,
       menyimpan metrik komparasi tata ruang awal (KDB, KLB, KDH, GSB, RTH),
       mendaftarkan silsilah permohonan revisi (Self-Referential/Legacy),
       dan mendaftarkan log audit perdana [Bogor 4, 7, sipas-fe.txt].
       Mendukung auto-fill otomatis data diri & lokasi dari SK induk (parent)
       jika parent_id_permohonan telah terdefinisi.
============================================================================
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, List, Any, Tuple
from dataclasses import dataclass
import os
import urllib.parse

from src.domain.entities.permohonan import Permohonan, SubmissionStatus, KKPRVerdict

def extract_filename_and_clean_url(url: str) -> tuple[str, str]:
    if not url:
        return "", ""
    parsed = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed.query)
    original_name = query_params.get("name")
    if original_name:
        name = original_name[0]
    else:
        name = os.path.basename(parsed.path)
    # Reconstruct clean url without query parameters
    clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return name, clean_url

# ─── SECTION: PORT ABSTRAKSI (DEPENDENCY INVERSION) ───────────────────────

class PermohonanRepositoryPort(ABC):
    @abstractmethod
    def save(self, permohonan: Permohonan, commit: bool = True) -> Permohonan:
        pass

    @abstractmethod
    def save_files(self, id_permohonan: str, files: List[dict], commit: bool = True) -> None:
        pass

    @abstractmethod
    def find_by_id(self, id_permohonan: str) -> Optional[Permohonan]:
        pass

    @abstractmethod
    def find_all(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        user_id: Optional[int] = None
    ) -> Tuple[List[Permohonan], int]:
        """Mendapatkan seluruh daftar permohonan ter-paginasi dengan filter [Liskov Substitution Compliant]."""
        pass

    @abstractmethod
    def find_kompensasi_by_permohonan_id(self, id_permohonan: str) -> List[Any]:
        pass

    @abstractmethod
    def save_kompensasi(self, kompensasi: Any, commit: bool = True) -> None:
        pass

    @abstractmethod
    def save_siteplan_geometries(self, id_permohonan: str, geometries: List[Tuple[str, Any]], commit: bool = True) -> None:
        """Menyimpan atau memperbarui data spasial detail secara transaksional [Fase 3]."""
        pass

    @abstractmethod
    def generate_internal_geometries(
        self,
        id_permohonan: str,
        base_lon: float,
        base_lat: float,
        rotation_deg: float,
        is_type_1: bool = True,
        commit: bool = True
    ) -> None:
        """Menghasilkan poligon detail rencana tapak secara otomatis [Fase 3/Decoupled]."""
        pass

    @abstractmethod
    def expire_all(self) -> None:
        """Mengosongkan cache sesi untuk memastikan reload data yang bersih setelah rollback."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit transaksi database yang sedang aktif secara eksplisit."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback transaksi database yang sedang aktif secara atomik."""
        pass


class AuditTrailRepositoryPort(ABC):
    @abstractmethod
    def log_action(
        self,
        submission_id: str,
        actor_name: str,
        role: str,
        action: str,
        status_before: str,
        status_after: str,
        notes: str,
        digital_signature_hash: Optional[str] = None,
        commit: bool = True
    ) -> None:
        pass

# ─── SECTION: INPUT DATA TRANSFER OBJECT (DTO) ────────────────────────────

@dataclass(frozen=True)
class SubmitPermohonanInputDto:
    id_permohonan: str
    submission_no: str
    housing_name: Optional[str] = None
    developer_name: Optional[str] = None
    land_area: Optional[float] = None
    actor_name: str = ""
    role: str = ""

    # Tahap 1
    applicant_type: Optional[str] = "PERORANGAN"
    applicant_name: Optional[str] = None
    applicant_nik: Optional[str] = None
    applicant_nib: Optional[str] = None
    applicant_npwp: Optional[str] = None
    applicant_director_name: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_address: Optional[str] = None

    # Tahap 2
    submission_type: Optional[str] = "BARU"
    submission_category: Optional[str] = "PERUMAHAN"

    # Tahap 3
    location_name: Optional[str] = None
    location_village: Optional[str] = None
    location_district: Optional[str] = None
    location_city: Optional[str] = "Kabupaten Bogor"
    location_province: Optional[str] = "Jawa Barat"
    location_full_address: Optional[str] = None
    location_ownership_status: Optional[str] = "SHM"
    location_certificate_number: Optional[str] = None
    location_certificate_owner: Optional[str] = None

    # Tahap 4
    cad_file_name: Optional[str] = None
    cad_param_a: Optional[float] = None
    cad_param_b: Optional[float] = None
    cad_param_tx: Optional[float] = None
    cad_param_ty: Optional[float] = None
    cad_scale: Optional[float] = None
    cad_rotation: Optional[float] = None

    # Tahap 5
    spatial_kkpr_number: Optional[str] = None
    spatial_land_use: Optional[str] = None
    spatial_green_area: Optional[float] = 0.0

    # Tahap 6
    tech_lot_count: Optional[int] = None
    tech_housing_type: Optional[str] = None
    tech_cemetery_area: Optional[float] = None
    tech_road_row_main: Optional[str] = None
    tech_road_row_local: Optional[str] = None
    tech_water_system: Optional[str] = None
    tech_water_source: Optional[str] = None

    tech_building_blocks: Optional[int] = None
    tech_kdb: Optional[float] = None
    tech_klb: Optional[float] = None
    tech_kdh: Optional[float] = None
    tech_parking_capacity: Optional[int] = None
    tech_max_floors: Optional[int] = None
    tech_total_floor_area: Optional[float] = None

    tech_facility_type: Optional[str] = None
    tech_capacity: Optional[int] = None
    tech_disabled_access: Optional[str] = None
    tech_special_parking: Optional[str] = None
    tech_fire_protection: Optional[str] = None

    tech_warehouse_count: Optional[int] = None
    tech_road_load_mst: Optional[str] = None
    tech_electricity_power: Optional[str] = None
    tech_ipal_capacity: Optional[str] = None
    tech_green_buffer_area: Optional[float] = None
    tech_tps_b3_provision: Optional[str] = None

    # Tahap 7
    consultant_name: Optional[str] = None
    consultant_company_name: Optional[str] = None
    consultant_pic_name: Optional[str] = None

    # Tahap 10
    statement_agreed: bool = False
    polygon: Optional[list] = None
    user_id: Optional[int] = None
    is_draft: bool = False

    # Tahap 8 (Lampiran Berkas)
    document_legal_doc: Optional[str] = None
    document_technical_doc: Optional[str] = None
    document_support_doc: Optional[str] = None
    document_support_doc2: Optional[str] = None
    document_ska_doc: Optional[str] = None
    document_cad_doc: Optional[str] = None
    document_ktp_doc: Optional[str] = None
    document_nib_doc: Optional[str] = None

    # Tahap 9 (Foto-foto)
    photo_north: Optional[str] = None
    photo_south: Optional[str] = None
    photo_east: Optional[str] = None
    photo_west: Optional[str] = None
    photo_access: Optional[str] = None

    # REVISI: METRIK INTENSITAS SPASIAL PEMOHON & BATAS RDTR
    applicant_land_area: Optional[float] = None
    applicant_building_area: Optional[float] = None
    applicant_kdb: Optional[float] = None
    applicant_klb: Optional[float] = None
    applicant_kdh: Optional[float] = None
    applicant_gsb: Optional[float] = None
    applicant_rth_area: Optional[float] = None

    bylaw_max_kdb: Optional[float] = None
    bylaw_max_klb: Optional[float] = None
    bylaw_min_kdh: Optional[float] = None
    bylaw_min_gsb: Optional[float] = None
    bylaw_min_rth_area: Optional[float] = None

    # TPU & Kompensasi Mandiri (Self-Declaration)
    tpu_method: Optional[str] = None
    tpu_area: Optional[float] = None
    tpu_nama: Optional[str] = None
    tpu_pengurus: Optional[str] = None
    tpu_no_pks: Optional[str] = None
    tpu_nominal: Optional[float] = None
    tpu_address: Optional[str] = None
    tpu_koordinat: Optional[str] = None
    tpu_bukti_dokumen: Optional[str] = None
    self_declared_compensations: Optional[List[dict]] = None

    # ─── SILSILAH PERMOHONAN INPUT DTO ────────────────
    baseline_source: Optional[str] = None         # "DIGITAL" | "LEGACY"
    parent_id_permohonan: Optional[str] = None    # ID Permohonan lama (jika ada di DB)
    replaced_sk_number: Optional[str] = None      # Nomor SK Fisik Lama
    replaced_sk_date: Optional[date] = None       # Tanggal SK Fisik Lama
    replaced_sk_doc_url: Optional[str] = None     # URL Berkas SK Fisik Lama

# ─── SECTION: USE CASE INTERACTOR ─────────────────────────────────────────

from src.use_cases.ports.integration_ports import BpnValidationPort, OssSyncPort, SimtaruSyncPort

class SubmitPermohonanUseCase:
    def __init__(
        self,
        permohonan_repo: PermohonanRepositoryPort,
        audit_trail_repo: AuditTrailRepositoryPort,
        bpn_port: Optional[BpnValidationPort] = None,
        oss_port: Optional[OssSyncPort] = None,
        simtaru_port: Optional[SimtaruSyncPort] = None
    ):
        """Suntikkan abstraksi ketergantungan (Dependency Injection)."""
        self.permohonan_repo = permohonan_repo
        self.audit_trail_repo = audit_trail_repo
        self.bpn_port = bpn_port
        self.oss_port = oss_port
        self.simtaru_port = simtaru_port

    def execute(self, input_dto: SubmitPermohonanInputDto) -> Permohonan:
        """Menjalankan orkestrasi pendaftaran permohonan satu pintu [Bogor 4]."""

        # ─── RESOLVE FIELD AUTOFILL LOGIC (GRASP INFORMATION EXPERT) ───────────────
        parent_record = None
        if input_dto.parent_id_permohonan:
            parent_record = self.permohonan_repo.find_by_id(input_dto.parent_id_permohonan)

        def resolve_field(dto_val: Any, parent_val: Any, default: Any = None) -> Any:
            """Memprioritaskan nilai input_dto, lalu fallback ke parent_record jika kosong."""
            if dto_val is not None and str(dto_val).strip() != "":
                return dto_val
            if parent_val is not None:
                return parent_val
            return default

        # Pengaitan transaksional data diri pemohon (Tahap 1)
        resolved_app_type = resolve_field(input_dto.applicant_type, getattr(parent_record, "applicant_type", None), "PERORANGAN")
        resolved_app_name = resolve_field(input_dto.applicant_name, getattr(parent_record, "applicant_name", None))
        if not resolved_app_name:
            resolved_app_name = resolve_field(input_dto.developer_name, getattr(parent_record, "developer_name", None))
            
        resolved_app_nik = resolve_field(input_dto.applicant_nik, getattr(parent_record, "applicant_nik", None))
        resolved_app_nib = resolve_field(input_dto.applicant_nib, getattr(parent_record, "applicant_nib", None))
        resolved_app_npwp = resolve_field(input_dto.applicant_npwp, getattr(parent_record, "applicant_npwp", None))
        resolved_app_director = resolve_field(input_dto.applicant_director_name, getattr(parent_record, "applicant_director_name", None))
        resolved_app_phone = resolve_field(input_dto.applicant_phone, getattr(parent_record, "applicant_phone", None))
        resolved_app_email = resolve_field(input_dto.applicant_email, getattr(parent_record, "applicant_email", None))
        resolved_app_address = resolve_field(input_dto.applicant_address, getattr(parent_record, "applicant_address", None))

        # Pengaitan transaksional lokasi permohonan (Tahap 3)
        resolved_loc_name = resolve_field(input_dto.location_name, getattr(parent_record, "location_name", None))
        if not resolved_loc_name:
            resolved_loc_name = resolved_app_name  # Fallback nama kegiatan ke nama pemohon jika kosong

        resolved_loc_village = resolve_field(input_dto.location_village, getattr(parent_record, "location_village", None))
        resolved_loc_district = resolve_field(input_dto.location_district, getattr(parent_record, "location_district", None))
        resolved_loc_city = resolve_field(input_dto.location_city, getattr(parent_record, "location_city", None), "Kabupaten Bogor")
        resolved_loc_province = resolve_field(input_dto.location_province, getattr(parent_record, "location_province", None), "Jawa Barat")
        resolved_loc_full_address = resolve_field(input_dto.location_full_address, getattr(parent_record, "location_full_address", None))
        resolved_loc_ownership = resolve_field(input_dto.location_ownership_status, getattr(parent_record, "location_ownership_status", None), "SHM")
        resolved_loc_certificate_no = resolve_field(input_dto.location_certificate_number, getattr(parent_record, "location_certificate_number", None))
        resolved_loc_certificate_owner = resolve_field(input_dto.location_certificate_owner, getattr(parent_record, "location_certificate_owner", None))

        permohonan = Permohonan(
            id_permohonan=input_dto.id_permohonan,
            submission_no=input_dto.submission_no,
            housing_name=input_dto.housing_name,
            developer_name=input_dto.developer_name,
            land_area=input_dto.applicant_land_area or input_dto.land_area,
            submission_date=date.today(),
            status=SubmissionStatus.DRAFT,
            buffer_sla=0,
            elapsed_days=0,

            # Tahap 1 (Resolved)
            applicant_type=resolved_app_type,
            applicant_name=resolved_app_name,
            applicant_nik=resolved_app_nik,
            applicant_nib=resolved_app_nib,
            applicant_npwp=resolved_app_npwp,
            applicant_director_name=resolved_app_director,
            applicant_phone=resolved_app_phone,
            applicant_email=resolved_app_email,
            applicant_address=resolved_app_address,

            # Tahap 2
            submission_type=input_dto.submission_type,
            submission_category=input_dto.submission_category,

            # Tahap 3 (Resolved)
            location_name=resolved_loc_name,
            location_village=resolved_loc_village,
            location_district=resolved_loc_district,
            location_city=resolved_loc_city,
            location_province=resolved_loc_province,
            location_full_address=resolved_loc_full_address,
            location_ownership_status=resolved_loc_ownership,
            location_certificate_number=resolved_loc_certificate_no,
            location_certificate_owner=resolved_loc_certificate_owner,

            # Tahap 4
            cad_file_name=input_dto.cad_file_name,
            cad_param_a=input_dto.cad_param_a,
            cad_param_b=input_dto.cad_param_b,
            cad_param_tx=input_dto.cad_param_tx,
            cad_param_ty=input_dto.cad_param_ty,
            cad_scale=input_dto.cad_scale,
            cad_rotation=input_dto.cad_rotation,

            # Tahap 5
            spatial_kkpr_number=input_dto.spatial_kkpr_number,
            spatial_land_use=input_dto.spatial_land_use,
            spatial_green_area=input_dto.spatial_green_area,

            # Tahap 6
            tech_lot_count=input_dto.tech_lot_count,
            tech_housing_type=input_dto.tech_housing_type,
            tech_cemetery_area=input_dto.tech_cemetery_area,
            tech_road_row_main=input_dto.tech_road_row_main,
            tech_road_row_local=input_dto.tech_road_row_local,
            tech_water_system=input_dto.tech_water_system,
            tech_water_source=input_dto.tech_water_source,

            tech_building_blocks=input_dto.tech_building_blocks,
            tech_kdb=input_dto.tech_kdb,
            tech_klb=input_dto.tech_klb,
            tech_kdh=input_dto.tech_kdh,
            tech_parking_capacity=input_dto.tech_parking_capacity,
            tech_max_floors=input_dto.tech_max_floors,
            tech_total_floor_area=input_dto.tech_total_floor_area,

            # Tahap 7
            consultant_name=input_dto.consultant_name,
            consultant_company_name=input_dto.consultant_company_name,
            consultant_pic_name=input_dto.consultant_pic_name,

            # Tahap 10
            statement_agreed=input_dto.statement_agreed,
            polygon=input_dto.polygon,
            user_id=input_dto.user_id,

            # REVISI: METRIK INTENSITAS SPASIAL PEMOHON & BATAS RDTR
            applicant_land_area=input_dto.applicant_land_area,
            applicant_building_area=input_dto.applicant_building_area,
            applicant_kdb=input_dto.applicant_kdb,
            applicant_klb=input_dto.applicant_klb,
            applicant_kdh=input_dto.applicant_kdh,
            applicant_gsb=input_dto.applicant_gsb,
            applicant_rth_area=input_dto.applicant_rth_area,

            bylaw_max_kdb=input_dto.bylaw_max_kdb,
            bylaw_max_klb=input_dto.bylaw_max_klb,
            bylaw_min_kdh=input_dto.bylaw_min_kdh,
            bylaw_min_gsb=input_dto.bylaw_min_gsb,
            bylaw_min_rth_area=input_dto.bylaw_min_rth_area,

            # ─── SILSILAH DOMAIN MAPPING KPD ENTIAS DOMAIN ───
            parents_lineage=[]
        )

        # ─── LOGIKA VERIFIKASI SEJARAH SK SECARA PRESISI (HUKUM DAN SPASIAL) ───
        is_revisi = str(permohonan.submission_type).upper() == "REVISI"
        if is_revisi:
            if not input_dto.is_draft:
                if not input_dto.baseline_source:
                    raise ValueError("Proses revisi dibatalkan. Bukti SK Lama mutlak diperlukan.")

            from src.domain.entities.permohonan import SilsilahPermohonan
            if input_dto.baseline_source == "DIGITAL":
                if not input_dto.is_draft and (not input_dto.parent_id_permohonan or not parent_record):
                    raise ValueError("Proses revisi dibatalkan. Bukti SK Lama rujukan digital tidak ditemukan.")
                
                # Validasi: Ikat sejarah spasial dan legal dari data digital internal (Optimasi database fetch)
                if parent_record:
                    permohonan.parents_lineage = [
                        SilsilahPermohonan(
                            id_silsilah=None,
                            child_id=permohonan.id_permohonan,
                            baseline_source="DIGITAL",
                            parent_id=parent_record.id_permohonan,
                            legacy_sk_number=parent_record.sk_number,
                            legacy_sk_date=parent_record.submission_date,
                            legacy_sk_doc_url=parent_record.signed_pdf_url
                        )
                    ]

            elif input_dto.baseline_source == "LEGACY":
                if not input_dto.is_draft and (not input_dto.replaced_sk_number or not input_dto.replaced_sk_date or not input_dto.replaced_sk_doc_url):
                    raise ValueError("Proses revisi dibatalkan. Bukti SK Lama mutlak diperlukan.")
                
                # Validasi: Ikat sejarah spasial dan legal dari data fisik manual
                if input_dto.replaced_sk_number:
                    permohonan.parents_lineage = [
                        SilsilahPermohonan(
                            id_silsilah=None,
                            child_id=permohonan.id_permohonan,
                            baseline_source="LEGACY",
                            legacy_sk_number=input_dto.replaced_sk_number,
                            legacy_sk_date=input_dto.replaced_sk_date,
                            legacy_sk_doc_url=input_dto.replaced_sk_doc_url
                        )
                    ]

        tpu_detail = None
        if input_dto.tpu_method:
            from src.domain.entities.permohonan import PermohonanTpu
            tpu_detail = PermohonanTpu(
                id_tpu=f"tpu-{input_dto.id_permohonan}",
                id_permohonan=input_dto.id_permohonan,
                metode=input_dto.tpu_method,
                luas=input_dto.tpu_area,
                nama_tpu=input_dto.tpu_nama,
                pengurus_tpu=input_dto.tpu_pengurus,
                no_pks=input_dto.tpu_no_pks,
                nominal_kompensasi=input_dto.tpu_nominal,
                alamat=input_dto.tpu_address,
                koordinat=input_dto.tpu_koordinat,
                bukti_dokumen_url=input_dto.tpu_bukti_dokumen,
                status_verifikasi="PENDING"
            )
        permohonan.tpu_detail = tpu_detail

        action_name = "SAVE_DRAFT"
        status_after = SubmissionStatus.DRAFT.value
        audit_notes = f"Draf permohonan tipe '{permohonan.document_category.value}' berhasil disimpan secara mandiri."

        if not input_dto.is_draft:
            permohonan.transition_status(SubmissionStatus.MENUNGGU_VERIFIKASI)
            action_name = "SUBMIT_UNIFIED_FORM"
            status_after = SubmissionStatus.MENUNGGU_VERIFIKASI.value
            audit_notes = f"Berkas permohonan tipe '{permohonan.document_category.value}' didaftarkan secara mandiri."

            if self.bpn_port:
                self.bpn_port.validate_land_boundary(input_dto.polygon or [])
            if self.simtaru_port:
                self.simtaru_port.check_zoning_compliance(input_dto.polygon or [])
            if self.oss_port:
                self.oss_port.sync_licensing_status(input_dto.id_permohonan, status_after)

        saved_permohonan = permohonan
        try:
            saved_permohonan = self.permohonan_repo.save(permohonan, commit=False)

            # Proses penyimpanan deklarasi kompensasi mandiri
            if input_dto.self_declared_compensations:
                from src.domain.entities.kompensasi import LahanKompensasi, CompensationType, FulfillmentStatus
                import uuid
                for comp in input_dto.self_declared_compensations:
                    comp_id = f"comp-{uuid.uuid4().hex[:8]}"
                    lahan_comp = LahanKompensasi(
                        id_kompensasi=comp_id,
                        id_permohonan=input_dto.id_permohonan,
                        tipe_kompensasi=CompensationType(comp["type"]),
                        luas_kompensasi_m2=float(comp["requiredAreaM2"]),
                        status_pemenuhan=FulfillmentStatus.PROSES_VERIFIKASI,
                        nilai_nominal=float(comp.get("nominalAmount") or 0.0),
                        bukti_legalitas_url=comp.get("documentUrl"),
                        alamat_lokasi=comp.get("locationAddress")
                    )
                    self.permohonan_repo.save_kompensasi(lahan_comp, commit=False)

            files_to_save = []
            if input_dto.document_legal_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_legal_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "legalDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_technical_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_technical_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "technicalDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_support_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_support_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "supportDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_support_doc2:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_support_doc2)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "supportDoc2",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_ska_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_ska_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "skaDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_cad_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_cad_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "cadDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_ktp_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_ktp_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "ktpDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.document_nib_doc:
                name, clean_url = extract_filename_and_clean_url(input_dto.document_nib_doc)
                files_to_save.append({
                    "file_type": "document",
                    "file_key": "nibDoc",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })

            if input_dto.photo_north:
                name, clean_url = extract_filename_and_clean_url(input_dto.photo_north)
                files_to_save.append({
                    "file_type": "photo",
                    "file_key": "photoNorth",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.photo_south:
                name, clean_url = extract_filename_and_clean_url(input_dto.photo_south)
                files_to_save.append({
                    "file_type": "photo",
                    "file_key": "photoSouth",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.photo_east:
                name, clean_url = extract_filename_and_clean_url(input_dto.photo_east)
                files_to_save.append({
                    "file_type": "photo",
                    "file_key": "photoEast",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.photo_west:
                name, clean_url = extract_filename_and_clean_url(input_dto.photo_west)
                files_to_save.append({
                    "file_type": "photo",
                    "file_key": "photoWest",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            if input_dto.photo_access:
                name, clean_url = extract_filename_and_clean_url(input_dto.photo_access)
                files_to_save.append({
                    "file_type": "photo",
                    "file_key": "photoAccess",
                    "file_name": name,
                    "file_path": clean_url,
                    "file_url": clean_url
                })
            self.permohonan_repo.save_files(saved_permohonan.id_permohonan, files_to_save, commit=False)

            # ─── DECOUPLED EVENT LISTENER: AUTOMATIC GEOMETRIZATION ───────────────
            if input_dto.polygon and len(input_dto.polygon) >= 3:
                # Hitung centroid dari input polygon
                base_lon = sum(pt[0] for pt in input_dto.polygon) / len(input_dto.polygon)
                base_lat = sum(pt[1] for pt in input_dto.polygon) / len(input_dto.polygon)
                
                # Konversi rotasi dari radian ke derajat jika tersedia
                rotation_deg = 12.0
                if input_dto.cad_rotation is not None:
                    import math
                    rotation_deg = math.degrees(input_dto.cad_rotation)
                
                # Hasilkan poligon detail site plan menggunakan repositori terabstraksi
                self.permohonan_repo.generate_internal_geometries(
                    id_permohonan=saved_permohonan.id_permohonan,
                    base_lon=base_lon,
                    base_lat=base_lat,
                    rotation_deg=rotation_deg,
                    is_type_1=True,
                    commit=False
                )

            self.audit_trail_repo.log_action(
                submission_id=saved_permohonan.id_permohonan,
                actor_name=input_dto.actor_name,
                role=input_dto.role,
                action=action_name,
                status_before=SubmissionStatus.DRAFT.value,
                status_after=status_after,
                notes=audit_notes,
                commit=False
            )

            # Selesaikan transaksi atomik di akhir secara eksplisit
            self.permohonan_repo.commit()
        except Exception as e:
            # Batalkan transaksi jika terjadi kesalahan
            self.permohonan_repo.rollback()
            raise e

        return saved_permohonan