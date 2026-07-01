"""
============================================================================
SIPAS USE CASE — Submit Permohonan [submit_permohonan.py]
============================================================================
Peran: Mengorkestrasikan alur pendaftaran permohonan baru satu pintu,
       menegakkan validasi skema dasar, menyimpan entitas ke repositori,
       dan mendaftarkan log audit perdana [Bogor 4, 7, sipas-fe.txt].
============================================================================
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, List, Any
from dataclasses import dataclass

from src.domain.entities.permohonan import Permohonan, SubmissionStatus

# ─── SECTION: PORT ABSTRAKSI (DEPENDENCY INVERSION) ───────────────────────

class PermohonanRepositoryPort(ABC):
    @abstractmethod
    def save(self, permohonan: Permohonan) -> Permohonan:
        pass

    @abstractmethod
    def find_by_id(self, id_permohonan: str) -> Optional[Permohonan]:
        pass

    @abstractmethod
    def find_all(self) -> List[Permohonan]:
        pass

    @abstractmethod
    def find_kompensasi_by_permohonan_id(self, id_permohonan: str) -> List[Any]:
        pass

    @abstractmethod
    def save_kompensasi(self, kompensasi: Any) -> None:
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
        notes: str
    ) -> None:
        pass

# ─── SECTION: INPUT DATA TRANSFER OBJECT (DTO) ────────────────────────────

@dataclass(frozen=True)
class SubmitPermohonanInputDto:
    id_permohonan: str
    submission_no: str
    housing_name: Optional[str]
    developer_name: Optional[str]
    land_area: Optional[float]
    actor_name: str
    role: str

    # Tahap 1
    applicant_type: Optional[str]
    applicant_nik: Optional[str]
    applicant_nib: Optional[str]
    applicant_npwp: Optional[str]
    applicant_director_name: Optional[str]
    applicant_phone: Optional[str]
    applicant_email: Optional[str]
    applicant_address: Optional[str]

    # Tahap 2
    submission_type: Optional[str]
    submission_category: Optional[str]

    # Tahap 3
    location_name: Optional[str]
    location_village: Optional[str]
    location_district: Optional[str]
    location_city: Optional[str]
    location_province: Optional[str]
    location_full_address: Optional[str]
    location_ownership_status: Optional[str]
    location_certificate_number: Optional[str]
    location_certificate_owner: Optional[str]

    # Tahap 4
    cad_file_name: Optional[str]
    cad_param_a: Optional[float]
    cad_param_b: Optional[float]
    cad_param_tx: Optional[float]
    cad_param_ty: Optional[float]
    cad_scale: Optional[float]
    cad_rotation: Optional[float]

    # Tahap 5
    spatial_kkpr_number: Optional[str]
    spatial_land_use: Optional[str]
    spatial_green_area: Optional[float]

    # Tahap 6
    tech_lot_count: Optional[int]
    tech_housing_type: Optional[str]
    tech_cemetery_area: Optional[float]
    tech_road_row_main: Optional[str]
    tech_road_row_local: Optional[str]
    tech_water_system: Optional[str]

    # (tech non-perumahan)
    tech_building_blocks: Optional[int]
    tech_kdb: Optional[float]
    tech_klb: Optional[float]
    tech_kdh: Optional[float]
    tech_parking_capacity: Optional[int]
    tech_max_floors: Optional[int]
    tech_total_floor_area: Optional[float]

    tech_facility_type: Optional[str]
    tech_capacity: Optional[int]
    tech_disabled_access: Optional[str]
    tech_special_parking: Optional[str]
    tech_fire_protection: Optional[str]

    tech_warehouse_count: Optional[int]
    tech_road_load_mst: Optional[str]
    tech_electricity_power: Optional[str]
    tech_ipal_capacity: Optional[str]
    tech_green_buffer_area: Optional[float]
    tech_tps_b3_provision: Optional[str]

    # Tahap 7
    consultant_name: Optional[str]
    consultant_company_name: Optional[str]
    consultant_pic_name: Optional[str]

    # Tahap 10
    statement_agreed: bool
    polygon: Optional[list] = None
    user_id: Optional[int] = None
    is_draft: bool = False

# ─── SECTION: USE CASE INTERACTOR ─────────────────────────────────────────

class SubmitPermohonanUseCase:
    def __init__(
        self,
        permohonan_repo: PermohonanRepositoryPort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        """Suntikkan abstraksi ketergantungan (Dependency Injection)."""
        self.permohonan_repo = permohonan_repo
        self.audit_trail_repo = audit_trail_repo

    def execute(self, input_dto: SubmitPermohonanInputDto) -> Permohonan:
        """Menjalankan orkestrasi pendaftaran permohonan satu pintu [Bogor 4]."""
        
        # 1. Inisialisasi Entitas Domain Murni (Kalkulasi Kategori & SLA berjalan otomatis)
        permohonan = Permohonan(
            id_permohonan=input_dto.id_permohonan,
            submission_no=input_dto.submission_no,
            housing_name=input_dto.housing_name,
            developer_name=input_dto.developer_name,
            land_area=input_dto.land_area,
            submission_date=date.today(),
            status=SubmissionStatus.DRAFT,
            buffer_sla=0,
            elapsed_days=0,
            
            # Tahap 1
            applicant_type=input_dto.applicant_type,
            applicant_nik=input_dto.applicant_nik,
            applicant_nib=input_dto.applicant_nib,
            applicant_npwp=input_dto.applicant_npwp,
            applicant_director_name=input_dto.applicant_director_name,
            applicant_phone=input_dto.applicant_phone,
            applicant_email=input_dto.applicant_email,
            applicant_address=input_dto.applicant_address,
            
            # Tahap 2
            submission_type=input_dto.submission_type,
            submission_category=input_dto.submission_category,
            
            # Tahap 3
            location_name=input_dto.location_name,
            location_village=input_dto.location_village,
            location_district=input_dto.location_district,
            location_city=input_dto.location_city,
            location_province=input_dto.location_province,
            location_full_address=input_dto.location_full_address,
            location_ownership_status=input_dto.location_ownership_status,
            location_certificate_number=input_dto.location_certificate_number,
            location_certificate_owner=input_dto.location_certificate_owner,
            
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
            
            tech_building_blocks=input_dto.tech_building_blocks,
            tech_kdb=input_dto.tech_kdb,
            tech_klb=input_dto.tech_klb,
            tech_kdh=input_dto.tech_kdh,
            tech_parking_capacity=input_dto.tech_parking_capacity,
            tech_max_floors=input_dto.tech_max_floors,
            tech_total_floor_area=input_dto.tech_total_floor_area,
            
            tech_facility_type=input_dto.tech_facility_type,
            tech_capacity=input_dto.tech_capacity,
            tech_disabled_access=input_dto.tech_disabled_access,
            tech_special_parking=input_dto.tech_special_parking,
            tech_fire_protection=input_dto.tech_fire_protection,
            
            tech_warehouse_count=input_dto.tech_warehouse_count,
            tech_road_load_mst=input_dto.tech_road_load_mst,
            tech_electricity_power=input_dto.tech_electricity_power,
            tech_ipal_capacity=input_dto.tech_ipal_capacity,
            tech_green_buffer_area=input_dto.tech_green_buffer_area,
            tech_tps_b3_provision=input_dto.tech_tps_b3_provision,
            
            # Tahap 7
            consultant_name=input_dto.consultant_name,
            consultant_company_name=input_dto.consultant_company_name,
            consultant_pic_name=input_dto.consultant_pic_name,
            
            # Tahap 10
            statement_agreed=input_dto.statement_agreed,
            polygon=input_dto.polygon,
            user_id=input_dto.user_id
        )

        # 2. Mutasikan status draf awal ke antrean peninjauan dinas jika bukan draf
        action_name = "SAVE_DRAFT"
        status_after = SubmissionStatus.DRAFT.value
        audit_notes = f"Draf permohonan tipe '{permohonan.document_category.value}' berhasil disimpan secara mandiri."
        
        if not input_dto.is_draft:
            permohonan.transition_status(SubmissionStatus.MENUNGGU_VERIFIKASI)
            action_name = "SUBMIT_UNIFIED_FORM"
            status_after = SubmissionStatus.MENUNGGU_VERIFIKASI.value
            audit_notes = f"Berkas permohonan tipe '{permohonan.document_category.value}' berhasil didaftarkan secara mandiri."

        # 3. Simpan entitas domain ke database menggunakan Port Repositori [sipas-fe.txt]
        saved_permohonan = self.permohonan_repo.save(permohonan)

        # 4. Catat jejak audit transaksional untuk jaminan hukum (Audit Trail) [Bogor 7]
        self.audit_trail_repo.log_action(
            submission_id=saved_permohonan.id_permohonan,
            actor_name=input_dto.actor_name,
            role=input_dto.role,
            action=action_name,
            status_before=SubmissionStatus.DRAFT.value,
            status_after=status_after,
            notes=audit_notes
        )

        return saved_permohonan