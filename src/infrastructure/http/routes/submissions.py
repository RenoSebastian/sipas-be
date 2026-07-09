# --- FILE: src/infrastructure/http/routes/submissions.py ---
"""
============================================================================
SIPAS HTTP CONTROLLER — Submissions Router [submissions.py] (REVISED v5)
============================================================================
Peran: Menyediakan REST endpoints bertingkat untuk mengelola pendaftaran
       10-tahap terpadu, kalibrasi, audit spasial, dan verifikasi berjenjang.
       Menegakkan otorisasi SoD API-Level untuk penandatanganan TTE Kadis,
       serta memetakan 13 matriks aspek secara type-safe dan Pylance-compliant.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Request
from pydantic import BaseModel, Field, model_validator, SecretStr
from sqlalchemy.orm import Session
from typing import Tuple, Optional, Any, List, Dict, cast
from datetime import datetime, date, timezone
import logging
import random
import shutil
import uuid
import os
import urllib.parse

# Adapter Koneksi & Repositori Database
from src.infrastructure.database.connection import get_db, get_bpn_port, get_oss_port, get_simtaru_port
from src.use_cases.ports.integration_ports import BpnValidationPort, OssSyncPort, SimtaruSyncPort
from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
from src.infrastructure.database.repositories.audit_trail_repository import AuditTrailRepository
from src.infrastructure.database.repositories.telaah_staf_repository import TelaahStafRepository
from src.infrastructure.database.models import (
    PermohonanModel, 
    AuditTrailModel, 
    PermohonanFileModel, 
    MasterRDTRModel, 
    EvaluasiChecklistItemModel, 
    TelaahStafModel,
    ChecklistStatus
)

# Adapter Eksternal Spasial, Geoserver, dan BSrE
from src.infrastructure.gis.cad_parser import CadParser
from src.infrastructure.security.bsre_client import BsreClient
from src.infrastructure.document.pdf_engine import HtmlToPdfEngine

# Import Kontrak Port Abstraksi untuk Nominal Typing (Anti-ReportArgumentType)
from src.use_cases.ports.document_generator_port import DocumentGeneratorPort

# Import Use Cases (Clean Architecture Interactors)
from src.use_cases.submit_permohonan import SubmitPermohonanUseCase, SubmitPermohonanInputDto
from src.use_cases.calibrate_cad import CalibrateCadUseCase, CalibrateCadInputDto
from src.use_cases.verify_submission import VerifySubmissionUseCase, VerifySubmissionInputDto, EvaluasiChecklistItemDto as UsecaseEvaluasiChecklistItemDto

# Penanganan Background Task Pengurai CAD
from src.infrastructure.queue.tasks import execute_cad_parsing_background

# Utilitas Keamanan / Autentikasi JWT (Aligning KADIS)
from src.infrastructure.security.auth import get_current_user, UserRole
from src.infrastructure.database.models import UserModel

logger = logging.getLogger("sipas-be")
router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions Core"])

# ─── SECTION 1: REQUEST & RESPONSE SCHEMAS (Pydantic V2) ──────────────────

class ApplicantDto(BaseModel):
    type: Optional[str] = Field(default="PERORANGAN", pattern="^(PERORANGAN|BADAN_USAHA)$", examples=["BADAN_USAHA"])
    name: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])
    nik: Optional[str] = Field(default=None, examples=["3201020304050607"])
    nib: Optional[str] = Field(default=None, examples=["9120301938192"])
    npwp: Optional[str] = Field(default=None, examples=["01.234.567.8-901.000"])
    directorName: Optional[str] = Field(default=None, examples=["Ahmad Fauzi"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])
    email: Optional[str] = Field(default=None, examples=["ahmad.fauzi@geocitra.co.id"])
    address: Optional[str] = Field(default=None, examples=["Gedung Sentosa Lt. 4, Jakarta Pusat"])

class SubmissionDetailsDto(BaseModel):
    submissionType: Optional[str] = Field(default="BARU", pattern="^(BARU|REVISI|PERPANJANGAN)$", examples=["BARU"])
    activityName: Optional[str] = Field(default=None, examples=["Grand Bogor Residence"])
    category: Optional[str] = Field(default="PERUMAHAN", pattern="^(PERUMAHAN|NON_PERUMAHAN|FASUM|INDUSTRI)$", examples=["PERUMAHAN"])

class LocationDetailsDto(BaseModel):
    locationName: Optional[str] = Field(default=None, examples=["Lahan Baranangsiang"])
    village: Optional[str] = Field(default=None, examples=["Baranangsiang"])
    district: Optional[str] = Field(default=None, examples=["Bogor Timur"])
    city: Optional[str] = Field(default="Kabupaten Bogor", examples=["Kabupaten Bogor"])
    province: Optional[str] = Field(default="Jawa Barat", examples=["Jawa Barat"])
    fullAddress: Optional[str] = Field(default=None, examples=["Jl. Raya Pajajaran No.21, Kec. Bogor Timur"])
    landArea: Optional[float] = Field(default=None, examples=[25000.0])
    ownershipStatus: Optional[str] = Field(default="SHM", pattern="^(SHM|HGB|HAK_PAKAI|LAINNYA)$", examples=["SHM"])
    certificateNumber: Optional[str] = Field(default=None, examples=["SHM No. 10293/Baranangsiang"])
    certificateOwner: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])

class CoordinateDto(BaseModel):
    polygon: Optional[list] = Field(default=None)
    coordinatesText: Optional[str] = Field(default=None)
    cadFileName: Optional[str] = Field(default=None, examples=["blueprint.dxf"])
    cadParamA: Optional[float] = Field(default=None)
    cadParamB: Optional[float] = Field(default=None)
    cadParamTx: Optional[float] = Field(default=None)
    cadParamTy: Optional[float] = Field(default=None)
    cadScale: Optional[float] = Field(default=None)
    cadRotation: Optional[float] = Field(default=None)

class SpatialDetailsDto(BaseModel):
    kkprNumber: Optional[str] = Field(default=None, examples=["503/KKPR/PUPR/2026/089"])
    landUse: Optional[str] = Field(default=None, examples=["Zona Perumahan Kepadatan Sedang"])
    greenArea: Optional[float] = Field(default=0.0, examples=[3850.0])

class TechnicalDetailsDto(BaseModel):
    lotCount: Optional[int] = Field(default=None, examples=[120])
    housingType: Optional[str] = Field(default=None, examples=["NON_SUBSIDI"])
    cemeteryArea: Optional[float] = Field(default=None, examples=[500.0])
    roadRowMain: Optional[str] = Field(default=None, examples=["12 Meter"])
    roadRowLocal: Optional[str] = Field(default=None, examples=["8 Meter"])
    waterSystem: Optional[str] = Field(default=None, examples=["PDAM"])
    waterSource: Optional[str] = Field(default=None, examples=["PDAM Tirta Kahuripan"])
    buildingBlocks: Optional[int] = Field(default=None, examples=[3])
    kdb: Optional[float] = Field(default=None, examples=[55.2])
    klb: Optional[float] = Field(default=None, examples=[2.1])
    kdh: Optional[float] = Field(default=None, examples=[15.4])
    parkingCapacity: Optional[int] = Field(default=None, examples=[150])
    maxFloors: Optional[int] = Field(default=None, examples=[5])
    totalFloorArea: Optional[float] = Field(default=None, examples=[24000.0])
    facilityType: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    disabledAccess: Optional[str] = Field(default=None)
    specialParking: Optional[str] = Field(default=None)
    fireProtection: Optional[str] = Field(default=None)
    warehouseCount: Optional[int] = Field(default=None)
    roadLoadMst: Optional[str] = Field(default=None)
    electricityPower: Optional[str] = Field(default=None)
    ipalCapacity: Optional[str] = Field(default=None)
    greenBufferArea: Optional[float] = Field(default=None)
    tpsB3Provision: Optional[str] = Field(default=None)

    # Metrik Proposed Pengembang
    applicantBuildingArea: Optional[float] = Field(default=None, examples=[13750.0])
    applicantGsb: Optional[float] = Field(default=None, examples=[5.0])
    applicantRthArea: Optional[float] = Field(default=None, examples=[2500.0])

class ConsultantDto(BaseModel):
    consultantName: Optional[str] = Field(default=None, examples=["Ir. Hermawan Pratama"])
    companyName: Optional[str] = Field(default=None, examples=["CV Rencana Semesta"])
    picName: Optional[str] = Field(default=None, examples=["Hermawan Pratama"])

class StatementDto(BaseModel):
    agreed: bool = Field(default=True)

class DocumentDto(BaseModel):
    legalDoc: Optional[str] = Field(default=None)
    technicalDoc: Optional[str] = Field(default=None)
    supportDoc: Optional[str] = Field(default=None)
    supportDoc2: Optional[str] = Field(default=None)
    skaDoc: Optional[str] = Field(default=None)
    cadDoc: Optional[str] = Field(default=None)
    ktpDoc: Optional[str] = Field(default=None)
    nibDoc: Optional[str] = Field(default=None)

class PhotoDto(BaseModel):
    photoNorth: Optional[str] = Field(default=None)
    photoSouth: Optional[str] = Field(default=None)
    photoEast: Optional[str] = Field(default=None)
    photoWest: Optional[str] = Field(default=None)
    photoAccess: Optional[str] = Field(default=None)

class SubmitRequest(BaseModel):
    id_permohonan: Optional[str] = Field(default=None, examples=["sub-123456"])
    is_draft: bool = Field(default=False)
    applicant: ApplicantDto
    submission: SubmissionDetailsDto
    location: LocationDetailsDto
    coordinate: CoordinateDto
    spatial: SpatialDetailsDto
    technical: TechnicalDetailsDto
    consultant: ConsultantDto
    statement: StatementDto
    document: Optional[DocumentDto] = Field(default=None)
    photo: Optional[PhotoDto] = Field(default=None)

    @model_validator(mode='before')
    @classmethod
    def allow_empty_fields_for_draft(cls, data: Any) -> Any:
        if isinstance(data, dict):
            is_draft = data.get("is_draft", False)
            if is_draft:
                for field in ["applicant", "submission", "location", "coordinate", "spatial", "technical", "consultant", "statement", "document", "photo"]:
                    if field not in data or data[field] is None:
                        data[field] = {}
        return data

class CalibrateRequest(BaseModel):
    cad_file_path: str = Field(examples=["C:/temp/blueprint.dxf"])
    anchor_cad_1: Tuple[float, float] = Field(examples=[(10.0, 15.0)])
    anchor_cad_2: Tuple[float, float] = Field(examples=[(120.0, 95.0)])
    anchor_map_1: Tuple[float, float] = Field(examples=[(106.8272, -6.5971)])
    anchor_map_2: Tuple[float, float] = Field(examples=[(106.8295, -6.5990)])

# ─── SECTION 2: SKEMA CHECKLIST & VERIFY DTO (13 Matriks Aspek) ────────────

class EvaluasiChecklistItemDto(BaseModel):
    aspek_code: str = Field(..., examples=["M3_KDB", "legalDoc"])
    aspek_label: str = Field(..., examples=["Koefisien Dasar Bangunan (KDB)", "Sertifikat Tanah BPN"])
    status_kelayakan: str = Field(..., pattern="^(Sesuai|Sesuai Bersyarat|Tidak Sesuai|Pending)$", examples=["Sesuai"])
    catatan_verifikator: Optional[str] = Field(default=None, examples=["Memenuhi batas aman"])
    attachment_url: Optional[str] = Field(default=None, examples=["/uploads/evaluasi/revisi_kdb.pdf"])

class VerifyRequest(BaseModel):
    # actor_name & role ditiadakan dari body request demi mencegah Spoofing Peran.
    # Data penandatangan wajib ditarik langsung dari session token JWT Kepala Dinas / Kabid.
    nip: Optional[str] = Field(default=None, examples=["197503112000031001"])
    passphrase: Optional[SecretStr] = Field(default=None, min_length=6, json_schema_extra={"writeOnly": True}, examples=["P@ssw0rdPejabat!"])
    action_type: str = Field(pattern="^(APPROVE|REJECT|REVERT_TO_TECHNICAL|REVERT_TO_ADMINISTRATIVE|OVERRIDE_VERDICT|SAVE_TECHNICAL_MATRIX)$")
    notes: str = Field(...)
    is_spatially_compliant: bool = Field(default=True)
    signature_base64: Optional[str] = Field(default=None, description="Visual signature coretan tangan")

    # Parameter Penilaian Spasial & Komparasi Tiga Sisi
    kkpr_verdict: Optional[str] = Field(default=None, pattern="^(Sesuai|Sesuai Bersyarat|Perlu Perbaikan / Revisi|Tidak Sesuai / Ditolak)$")
    verified_kdb: Optional[float] = None
    verified_klb: Optional[float] = None
    verified_kdh: Optional[float] = None
    verified_gsb: Optional[float] = None
    verified_rth_area: Optional[float] = None
    
    # Array checklist formal kelengkapan berkas & 13 matriks teknis daerah (Fase 2)
    checklist_items: Optional[List[EvaluasiChecklistItemDto]] = None


# ─── SECTION 3: HTTP ROUTE HANDLERS ───────────────────────────────────────

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Mengunggah berkas lampiran secara lokal ke storage backend [uploads/permohonan]"""
    try:
        MAX_FILE_SIZE = 20 * 1024 * 1024
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ukuran berkas melebihi batas maksimal 20MB."
            )

        upload_dir = "uploads/permohonan"
        os.makedirs(upload_dir, exist_ok=True)
        
        raw_filename = file.filename if file.filename else ""
        file_ext = os.path.splitext(raw_filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        base_url = str(request.base_url).rstrip("/")
        file_url = f"{base_url}/uploads/permohonan/{unique_filename}"
        
        return {
            "file_name": file.filename,
            "file_path": file_path,
            "file_url": file_url
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengunggah berkas: {str(e)}"
        )

@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_permohonan(
    req: SubmitRequest, 
    db: Session = Depends(get_db), 
    bpn_port: BpnValidationPort = Depends(get_bpn_port),
    oss_port: OssSyncPort = Depends(get_oss_port),
    simtaru_port: SimtaruSyncPort = Depends(get_simtaru_port),
    current_user: UserModel = Depends(get_current_user)
):
    """Menerima berkas pendaftaran terpadu satu pintu 10-tahap [Bogor 4]."""
    try:
        permohonan_repo = PermohonanRepository(db)
        audit_trail_repo = AuditTrailRepository(db)
        
        use_case = SubmitPermohonanUseCase(
            permohonan_repo, 
            audit_trail_repo,
            bpn_port=bpn_port,
            oss_port=oss_port,
            simtaru_port=simtaru_port
        )
 
        id_permohonan = req.id_permohonan or f"sub-{int(datetime.now(timezone.utc).timestamp())}"
        submission_no = f"SIPAS-2026-0{random.randint(100, 999)}"

        rdtr = db.query(MasterRDTRModel).filter(
            MasterRDTRModel.district == req.location.district,
            MasterRDTRModel.village == req.location.village,
            MasterRDTRModel.category == req.submission.category
        ).first()

        bylaw_max_kdb = rdtr.max_kdb if rdtr else 60.0
        bylaw_max_klb = rdtr.max_klb if rdtr else 3.5
        bylaw_min_kdh = rdtr.min_kdh if rdtr else 10.0
        bylaw_min_gsb = rdtr.min_gsb if rdtr else 5.0
        bylaw_min_rth_area = rdtr.min_rth_area if rdtr else 1400.0
 
        dto = SubmitPermohonanInputDto(
            id_permohonan=id_permohonan,
            submission_no=submission_no,
            housing_name=req.submission.activityName,
            developer_name=req.applicant.name,
            land_area=req.location.landArea,
            actor_name=cast(str, current_user.full_name),
            role=cast(str, current_user.role),
            
            # Tahap 1
            applicant_type=req.applicant.type,
            applicant_name=req.applicant.name or req.applicant.directorName,
            applicant_nik=req.applicant.nik,
            applicant_nib=req.applicant.nib,
            applicant_npwp=req.applicant.npwp,
            applicant_director_name=req.applicant.directorName,
            applicant_phone=req.applicant.phone,
            applicant_email=req.applicant.email,
            applicant_address=req.applicant.address,
            
            # Tahap 2
            submission_type=req.submission.submissionType,
            submission_category=req.submission.category,
            
            # Tahap 3
            location_name=req.location.locationName,
            location_village=req.location.village,
            location_district=req.location.district,
            location_city=req.location.city,
            location_province=req.location.province,
            location_full_address=req.location.fullAddress,
            location_ownership_status=req.location.ownershipStatus,
            location_certificate_number=req.location.certificateNumber,
            location_certificate_owner=req.location.certificateOwner,
            
            # Tahap 4
            cad_file_name=req.coordinate.cadFileName,
            cad_param_a=req.coordinate.cadParamA,
            cad_param_b=req.coordinate.cadParamB,
            cad_param_tx=req.coordinate.cadParamTx,
            cad_param_ty=req.coordinate.cadParamTy,
            cad_scale=req.coordinate.cadScale,
            cad_rotation=req.coordinate.cadRotation,
            
            # Tahap 5
            spatial_kkpr_number=req.spatial.kkprNumber,
            spatial_land_use=req.spatial.landUse,
            spatial_green_area=req.spatial.greenArea,
            
            # Tahap 6
            tech_lot_count=req.technical.lotCount,
            tech_housing_type=req.technical.housingType,
            tech_cemetery_area=req.technical.cemeteryArea,
            tech_road_row_main=req.technical.roadRowMain,
            tech_road_row_local=req.technical.roadRowLocal,
            tech_water_system=req.technical.waterSystem,
            tech_water_source=req.technical.waterSource,
            
            tech_building_blocks=req.technical.buildingBlocks,
            tech_kdb=req.technical.kdb,
            tech_klb=req.technical.klb,
            tech_kdh=req.technical.kdh,
            tech_parking_capacity=req.technical.parkingCapacity,
            tech_max_floors=req.technical.maxFloors,
            tech_total_floor_area=req.technical.totalFloorArea,
            
            tech_facility_type=req.technical.facilityType,
            tech_capacity=req.technical.capacity,
            tech_disabled_access=req.technical.disabledAccess,
            tech_special_parking=req.technical.specialParking,
            tech_fire_protection=req.technical.fireProtection,
            
            tech_warehouse_count=req.technical.warehouseCount,
            tech_road_load_mst=req.technical.roadLoadMst,
            tech_electricity_power=req.technical.electricityPower,
            tech_ipal_capacity=req.technical.ipalCapacity,
            tech_green_buffer_area=req.technical.greenBufferArea,
            tech_tps_b3_provision=req.technical.tpsB3Provision,
            
            # Tahap 7
            consultant_name=req.consultant.consultantName,
            consultant_company_name=req.consultant.companyName,
            consultant_pic_name=req.consultant.picName,
            
            # Tahap 8
            document_legal_doc=req.document.legalDoc if req.document else None,
            document_technical_doc=req.document.technicalDoc if req.document else None,
            document_support_doc=req.document.supportDoc if req.document else None,
            document_support_doc2=req.document.supportDoc2 if req.document else None,
            document_ska_doc=req.document.skaDoc if req.document else None,
            document_cad_doc=req.document.cadDoc if req.document else None,
            document_ktp_doc=req.document.ktpDoc if req.document else None,
            document_nib_doc=req.document.nibDoc if req.document else None,
            
            # Tahap 9
            photo_north=req.photo.photoNorth if req.photo else None,
            photo_south=req.photo.photoSouth if req.photo else None,
            photo_east=req.photo.photoEast if req.photo else None,
            photo_west=req.photo.photoWest if req.photo else None,
            photo_access=req.photo.photoAccess if req.photo else None,
            
            # Tahap 10
            statement_agreed=req.statement.agreed,
            polygon=req.coordinate.polygon,
            user_id=cast(int, current_user.id),
            is_draft=req.is_draft,

            # Proposed & Bylaw
            applicant_land_area=req.location.landArea,
            applicant_building_area=req.technical.applicantBuildingArea if req.technical else None,
            applicant_kdb=req.technical.kdb if req.technical else None,
            applicant_klb=req.technical.klb if req.technical else None,
            applicant_kdh=req.technical.kdh if req.technical else None,
            applicant_gsb=req.technical.applicantGsb if req.technical else None,
            applicant_rth_area=req.technical.applicantRthArea if req.technical else None,

            bylaw_max_kdb=bylaw_max_kdb,
            bylaw_max_klb=bylaw_max_klb,
            bylaw_min_kdh=bylaw_min_kdh,
            bylaw_min_gsb=bylaw_min_gsb,
            bylaw_min_rth_area=bylaw_min_rth_area
        )
        result = use_case.execute(dto)

        return {
            "status": "SUCCESS",
            "message": "Permohonan terpadu berhasil didaftarkan.",
            "data": {
                "id_permohonan": result.id_permohonan,
                "category": result.document_category.value,
                "base_sla_days": result.base_sla,
                "status": result.status.value
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id_permohonan}/calibrate", status_code=status.HTTP_200_OK)
def calibrate_cad_spasial(
    id_permohonan: str,
    req: CalibrateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Mengalkulasi transformasi koordinat Helmert 2D gambar CAD [Jakarta 5]."""
    try:
        permohonan_repo = PermohonanRepository(db)
        audit_trail_repo = AuditTrailRepository(db)
        cad_parser = CadParser()

        use_case = CalibrateCadUseCase(
            permohonan_repo,
            cad_parser,
            audit_trail_repo
        )

        dto = CalibrateCadInputDto(
            id_permohonan=id_permohonan,
            cad_file_path=req.cad_file_path,
            anchor_cad_1=req.anchor_cad_1,
            anchor_cad_2=req.anchor_cad_2,
            anchor_map_1=req.anchor_map_1,
            anchor_map_2=req.anchor_map_2,
            actor_name=cast(str, current_user.full_name),
            role=cast(str, current_user.role)
        )

        use_case.execute(dto)

        def run_cad_parsing_task() -> None:
            execute_cad_parsing_background(
                file_path=req.cad_file_path,
                id_permohonan=id_permohonan,
                anchor_cad_1=req.anchor_cad_1,
                anchor_cad_2=req.anchor_cad_2,
                anchor_map_1=req.anchor_map_1,
                anchor_map_2=req.anchor_map_2
            )

        background_tasks.add_task(run_cad_parsing_task)

        return {
            "status": "SUCCESS",
            "message": "Penyelarasan spasial selesai. Poligon CAD sedang diekstrak di latar belakang."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── UPDATE ENDPOINT VERIFIKASI (SoD Enforcer & 13 Matriks Aspek) ───────────

@router.post("/{id_permohonan}/verify", status_code=status.HTTP_200_OK)
async def verify_submission(
    id_permohonan: str,
    req: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Otorisasi keputusan berjenjang dan penandatanganan elektronik BSrE [Bogor 7, 10]."""
    
    # ─── INTEGRITAS DATA & SOD KADIS ENDPOINT-LEVEL GATEKEEPER ───────────────
    # Memeriksa data terkini permohonan dari database untuk mengunci wewenang TTE Kadis.
    permohonan_model = db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_permohonan).first()
    if not permohonan_model:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan.")

    # Proteksi keamanan API (Segregation of Duties): Hanya Kadis yang boleh menyetujui di meja Kadis
    if permohonan_model.status == "Menunggu Persetujuan":
        if current_user.role != "KADIS":
            logger.warning(
                f"[SECURITY_ALERT] Non-KADIS user '{current_user.username}' (Role: {current_user.role}) "
                f"attempted to trigger final TTE signature on submission: {id_permohonan}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses Ditolak: Hanya Kepala Dinas (KADIS) yang diizinkan memproses penandatanganan SK final."
            )

    try:
        permohonan_repo = PermohonanRepository(db)
        telaah_staf_repo = TelaahStafRepository(db)
        audit_trail_repo = AuditTrailRepository(db)
        
        # ─── PERBAIKAN PYLANCE nominal type check: Gunakan type annotation formal Port (DIP) ───
        doc_generator: DocumentGeneratorPort = HtmlToPdfEngine()
        bsre_client = BsreClient()

        use_case = VerifySubmissionUseCase(
            permohonan_repo=permohonan_repo,
            telaah_staf_repo=telaah_staf_repo,
            document_generator=doc_generator,
            digital_signature_client=bsre_client,
            audit_trail_repo=audit_trail_repo
        )

        # ─── REVISI: TRANSFORMASI CHECKLIST DTO KE USECASE MODEL ───
        usecase_items = []
        if req.checklist_items:
            for item in req.checklist_items:
                usecase_items.append(
                    UsecaseEvaluasiChecklistItemDto(
                        aspek_code=item.aspek_code,
                        aspek_label=item.aspek_label,
                        status_kelayakan=item.status_kelayakan,
                        catatan_verifikator=item.catatan_verifikator,
                        attachment_url=item.attachment_url,
                        # Pasang data penambat audit verifikator secara dinamis (Fase 1)
                        verified_by_id=current_user.id,
                        verified_at=datetime.now()
                    )
                )

        # Kontrak Verifikasi - Identitas aktor DIPAKSA ditarik murni dari JWT (Anti-Spoofing)
        dto = VerifySubmissionInputDto(
            id_permohonan=id_permohonan,
            actor_name=cast(str, current_user.full_name),
            role=cast(str, current_user.role),
            nip=req.nip,
            passphrase=req.passphrase.get_secret_value() if req.passphrase else None,
            action_type=req.action_type,
            notes=req.notes,
            is_spatially_compliant=req.is_spatially_compliant,
            signature_base64=req.signature_base64,

            # Parameter komparasi teknis revisi
            kkpr_verdict=req.kkpr_verdict,
            verified_kdb=req.verified_kdb,
            verified_klb=req.verified_klb,
            verified_kdh=req.verified_kdh,
            verified_gsb=req.verified_gsb,
            verified_rth_area=req.verified_rth_area,
            checklist_items=usecase_items
        )

        result = await use_case.execute(dto)
        return {
            "status": "SUCCESS",
            "message": f"Keputusan verifikasi berhasil direkam. Status berkas: {result.status.value}"
        }
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/rdtr-limits", status_code=status.HTTP_200_OK)
def get_rdtr_limits(
    district: str,
    village: str,
    category: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Mendapatkan batasan regulasi (bylaw) RDTR Kabupaten Bogor secara dinamis."""
    rdtr = db.query(MasterRDTRModel).filter(
        MasterRDTRModel.district == district,
        MasterRDTRModel.village == village,
        MasterRDTRModel.category == category
    ).first()

    if not rdtr:
        return {
            "max_kdb": 60.0,
            "max_klb": 3.5,
            "min_kdh": 10.0,
            "min_gsb": 5.0,
            "min_rth_area": 1400.0,
            "is_fallback": True
        }

    return {
        "max_kdb": rdtr.max_kdb,
        "max_klb": rdtr.max_klb,
        "min_kdh": rdtr.min_kdh,
        "min_gsb": rdtr.min_gsb,
        "min_rth_area": rdtr.min_rth_area,
        "is_fallback": False
    }

@router.get("", status_code=status.HTTP_200_OK)
def get_all_submissions(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Mendapatkan seluruh daftar pengajuan site plan."""
    repo = PermohonanRepository(db)
    results = repo.find_all()
    return [
        {
            "id": r.id_permohonan,
            "submissionNo": r.submission_no,
            "housingName": r.housing_name,
            "developerName": r.developer_name,
            "landArea": r.land_area,
            "submissionDate": r.submission_date.isoformat(),
            "status": r.status.value,
            "category": r.document_category.value,
            "base_sla_days": r.base_sla,
            "remaining_sla_days": r.remaining_sla_days,
            
            # Form data (Tahap 1-10)
            "applicant": {
                "type": r.applicant_type,
                "name": r.applicant_name,
                "nik": r.applicant_nik,
                "nib": r.applicant_nib,
                "npwp": r.applicant_npwp,
                "directorName": r.applicant_director_name,
                "phone": r.applicant_phone,
                "email": r.applicant_email,
                "address": r.applicant_address
            },
            "submissionDetails": {
                "submissionType": r.submission_type,
                "activityName": r.housing_name,
                "category": r.submission_category
            },
            "locationDetails": {
                "locationName": r.location_name,
                "village": r.location_village,
                "district": r.location_district,
                "city": r.location_city,
                "province": r.location_province,
                "fullAddress": r.location_full_address,
                "landArea": r.land_area,
                "ownershipStatus": r.location_ownership_status,
                "certificateNumber": r.location_certificate_number,
                "certificateOwner": r.location_certificate_owner
            },
            "spatial": {
                "kkprNumber": r.spatial_kkpr_number,
                "landUse": r.spatial_land_use,
                "greenArea": r.spatial_green_area
            },
            "technical": {
                "lotCount": r.tech_lot_count,
                "housingType": r.tech_housing_type,
                "cemeteryArea": r.tech_cemetery_area,
                "roadRowMain": r.tech_road_row_main,
                "roadRowLocal": r.tech_road_row_local,
                "waterSystem": r.tech_water_system,
                "waterSource": r.tech_water_source,
                "buildingBlocks": r.tech_building_blocks,
                "kdb": r.tech_kdb,
                "klb": r.tech_klb,
                "kdh": r.tech_kdh,
                "parkingCapacity": r.tech_parking_capacity,
                "maxFloors": r.tech_max_floors,
                "totalFloorArea": r.tech_total_floor_area,
                "facilityType": r.tech_facility_type,
                "capacity": r.tech_capacity,
                "disabledAccess": r.tech_disabled_access,
                "specialParking": r.tech_special_parking,
                "fireProtection": r.tech_fire_protection,
                "warehouseCount": r.tech_warehouse_count,
                "roadLoadMst": r.tech_road_load_mst,
                "electricityPower": r.tech_electricity_power,
                "ipalCapacity": r.tech_ipal_capacity,
                "greenBufferArea": r.tech_green_buffer_area,
                "tpsB3Provision": r.tech_tps_b3_provision,

                "applicantBuildingArea": r.applicant_building_area,
                "applicantGsb": r.applicant_gsb,
                "applicantRthArea": r.applicant_rth_area
            },
            "consultant": {
                "consultantName": r.consultant_name,
                "consultantCompanyName": r.consultant_company_name,
                "companyName": r.consultant_company_name,
                "consultantPicName": r.consultant_pic_name,
                "picName": r.consultant_pic_name
            },
            "statement": {
                "agreed": r.statement_agreed
            },
            "location": {
                "lat": sum(float(pt[1]) for pt in r.polygon) / len(r.polygon) if r.polygon and len(r.polygon) >= 3 else -6.595189,
                "lng": sum(float(pt[0]) for pt in r.polygon) / len(r.polygon) if r.polygon and len(r.polygon) >= 3 else 106.816629,
                "address": r.location_full_address,
                "polygon": r.polygon or []
            },
            "signatureHash": r.signature_hash,
            "signedPdfUrl": r.signed_pdf_url,
            "kabidSignature": r.kabid_signature,
            "kadisSignature": r.kadis_signature,

            # Kesimpulan KKPR
            "kkprVerdict": r.kkpr_verdict.value if r.kkpr_verdict else None,
            "kkprVerifiedAt": r.kkpr_verified_at.isoformat() if r.kkpr_verified_at else None,
            "kkprVerifierName": r.kkpr_verifier_name,
            "verifiedKdb": r.verified_kdb,
            "verifiedKlb": r.verified_klb,
            "verifiedKdh": r.verified_kdh,
            "verifiedGsb": r.verified_gsb,
            "verifiedRthArea": r.verified_rth_area
        }
        for r in results
    ]

@router.get("/{id_permohonan}", status_code=status.HTTP_200_OK)
def get_submission_by_id(id_permohonan: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Mendapatkan data rinci pengajuan berdasarkan ID, lengkap dengan metadata snapshot Telaah Staf."""
    repo = PermohonanRepository(db)
    r = repo.find_by_id(id_permohonan)
    if not r:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan.")

    db_files = db.query(PermohonanFileModel).filter(PermohonanFileModel.id_permohonan == id_permohonan).all()
    docs_list = []
    photos_dict = {
        "photoNorth": None,
        "photoSouth": None,
        "photoEast": None,
        "photoWest": None,
        "photoAccess": None
    }
    docs_dict: Dict[str, Optional[str]] = {
        "legalDoc": None,
        "technicalDoc": None,
        "supportDoc": None,
        "supportDoc2": None,
        "skaDoc": None,
        "cadDoc": None,
        "ktpDoc": None,
        "nibDoc": None
    }
    for f in db_files:
        if f.file_type == "document":
            docs_list.append({
                "id": f"doc-{r.id_permohonan}-{f.id}",
                "name": f.file_name,
                "type": f.file_name.split('.')[-1] if '.' in f.file_name else 'pdf',
                "url": f.file_url,
                "uploadedAt": f.uploaded_at.isoformat(),
                "key": f.file_key
            })
            if f.file_url:
                docs_dict[f.file_key] = f"{f.file_url}?name={urllib.parse.quote(f.file_name)}"
        elif f.file_type == "photo":
            if f.file_url:
                photos_dict[f.file_key] = f"{f.file_url}?name={urllib.parse.quote(f.file_name)}"

    # Ambil Checklist Evaluasi manual jika ada
    db_evaluations = db.query(EvaluasiChecklistItemModel).filter(
        EvaluasiChecklistItemModel.id_permohonan == id_permohonan
    ).all()

    evaluation_list = [
        {
            "aspekCode": item.aspek_code,
            "aspekLabel": item.aspek_label,
            "statusKelayakan": item.status_kelayakan.value,
            "catatanVerifikator": item.catatan_verifikator,
            "attachmentUrl": item.attachment_url,
            "verifiedById": item.verified_by_id,
            "verifiedAt": item.verified_at.isoformat() if item.verified_at else None
        }
        for item in db_evaluations
    ]

    # ─── BARU: SNAPSHOT DOKUMEN TELAAH STAF DI API DETAIL (Fase 4 REST) ──────
    telaah_staf_data = None
    telaah_model = db.query(TelaahStafModel).filter(TelaahStafModel.id_permohonan == id_permohonan).first()
    if telaah_model:
        telaah_staf_data = {
            "idTelaah": telaah_model.id_telaah,
            "verdict": telaah_model.verdict,
            "isOverridden": telaah_model.is_overridden,
            "overrideReason": telaah_model.override_reason,
            "createdAt": telaah_model.created_at.isoformat(),
            "payload": telaah_model.document_payload
        }

    return {
        "id": r.id_permohonan,
        "submissionNo": r.submission_no,
        "housingName": r.housing_name,
        "developerName": r.developer_name,
        "landArea": r.land_area,
        "submissionDate": r.submission_date.isoformat(),
        "status": r.status.value,
        "category": r.document_category.value,
        "base_sla_days": r.base_sla,
        "remaining_sla_days": r.remaining_sla_days,

        # Form data (Tahap 1-10)
        "applicant": {
            "type": r.applicant_type,
            "name": r.applicant_name,
            "nik": r.applicant_nik,
            "nib": r.applicant_nib,
            "npwp": r.applicant_npwp,
            "directorName": r.applicant_director_name,
            "phone": r.applicant_phone,
            "email": r.applicant_email,
            "address": r.applicant_address
        },
        "submissionDetails": {
            "submissionType": r.submission_type,
            "activityName": r.housing_name,
            "category": r.submission_category
        },
        "locationDetails": {
            "locationName": r.location_name,
            "village": r.location_village,
            "district": r.location_district,
            "city": r.location_city,
            "province": r.location_province,
            "fullAddress": r.location_full_address,
            "landArea": r.land_area,
            "ownershipStatus": r.location_ownership_status,
            "certificateNumber": r.location_certificate_number,
            "certificateOwner": r.location_certificate_owner
        },
        "spatial": {
            "kkprNumber": r.spatial_kkpr_number,
            "landUse": r.spatial_land_use,
            "greenArea": r.spatial_green_area
        },
        "technical": {
            "lotCount": r.tech_lot_count,
            "housingType": r.tech_housing_type,
            "cemeteryArea": r.tech_cemetery_area,
            "roadRowMain": r.tech_road_row_main,
            "roadRowLocal": r.tech_road_row_local,
            "waterSystem": r.tech_water_system,
            "waterSource": r.tech_water_source,
            "buildingBlocks": r.tech_building_blocks,
            "kdb": r.tech_kdb,
            "klb": r.tech_klb,
            "kdh": r.tech_kdh,
            "parkingCapacity": r.tech_parking_capacity,
            "maxFloors": r.tech_max_floors,
            "totalFloorArea": r.tech_total_floor_area,
            "facilityType": r.tech_facility_type,
            "capacity": r.tech_capacity,
            "disabledAccess": r.tech_disabled_access,
            "specialParking": r.tech_special_parking,
            "fireProtection": r.tech_fire_protection,
            "warehouseCount": r.tech_warehouse_count,
            "roadLoadMst": r.tech_road_load_mst,
            "electricityPower": r.tech_electricity_power,
            "ipalCapacity": r.tech_ipal_capacity,
            "greenBufferArea": r.tech_green_buffer_area,
            "tpsB3Provision": r.tech_tps_b3_provision,

            "applicantBuildingArea": r.applicant_building_area,
            "applicantGsb": r.applicant_gsb,
            "applicantRthArea": r.applicant_rth_area
        },
        "consultant": {
            "consultantName": r.consultant_name,
            "consultantCompanyName": r.consultant_company_name,
            "companyName": r.consultant_company_name,
            "consultantPicName": r.consultant_pic_name,
            "picName": r.consultant_pic_name
        },
        "statement": {
            "agreed": r.statement_agreed
        },
        "location": {
            "lat": sum(float(pt[1]) for pt in r.polygon) / len(r.polygon) if r.polygon and len(r.polygon) >= 3 else -6.595189,
            "lng": sum(float(pt[0]) for pt in r.polygon) / len(r.polygon) if r.polygon and len(r.polygon) >= 3 else 106.816629,
            "address": r.location_full_address,
            "polygon": r.polygon or []
        },
        "documents": docs_list or [
            { "id": f"doc-{r.id_permohonan}-1", "name": "Surat Permohonan.pdf", "type": "pdf", "url": "#", "uploadedAt": r.submission_date.isoformat() },
            { "id": f"doc-{r.id_permohonan}-2", "name": "Sertifikat Tanah Hak Milik.pdf", "type": "pdf", "url": "#", "uploadedAt": r.submission_date.isoformat() }
        ],
        "document": docs_dict,
        "photo": photos_dict,
        "photos": photos_dict,
        "signatureHash": r.signature_hash,
        "signedPdfUrl": r.signed_pdf_url,
        
        # Paraf Kabid & TTE Kadis
        "kabidSignature": r.kabid_signature,
        "kadisSignature": r.kadis_signature,

        # Parameter Evaluasi
        "kkprVerdict": r.kkpr_verdict.value if r.kkpr_verdict else None,
        "kkprVerifiedAt": r.kkpr_verified_at.isoformat() if r.kkpr_verified_at else None,
        "kkprVerifierName": r.kkpr_verifier_name,
        "verifiedKdb": r.verified_kdb,
        "verifiedKlb": r.verified_klb,
        "verifiedKdh": r.verified_kdh,
        "verifiedGsb": r.verified_gsb,
        "verifiedRthArea": r.verified_rth_area,
        "evaluationChecklist": evaluation_list,
        "telaahStaf": telaah_staf_data,  # Payload snapshot Telaah Staf utuh

        "history": (lambda: [
            {
                "date": log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "status": log.status_after,
                "action": log.action,
                "notes": log.notes,
                "actor": f"{log.actor_name} ({log.role})",
                "digitalSignatureHash": log.digital_signature_hash
            }
            for log in db.query(AuditTrailModel).filter(AuditTrailModel.submission_id == r.id_permohonan).order_by(AuditTrailModel.created_at.asc()).all()
        ] or [
            { "date": r.submission_date.isoformat() + " 09:00", "status": "Draft", "action": "Draft", "notes": "Pengajuan dibuat", "actor": r.applicant_name or "Pemohon", "digitalSignatureHash": None }
        ])()
    }

@router.get("/{id_permohonan}/geometries", status_code=status.HTTP_200_OK)
def get_submission_geometries(
    id_permohonan: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Mendapatkan data poligon CAD detail (jalan, RTH, PSU, kaveling) dari PostGIS."""
    from src.infrastructure.database.models import SitePlanGeometryModel
    from geoalchemy2.shape import to_shape
    
    geoms = db.query(SitePlanGeometryModel).filter(
        SitePlanGeometryModel.id_permohonan == id_permohonan
    ).all()
    
    road_polygons = []
    rth_polygons = []
    psu_polygons = []
    kavling_polygons = []
    
    for g in geoms:
        polygon_coords = []
        if g.geom:
            try:
                shapely_poly = to_shape(cast(Any, g.geom))
                exterior = getattr(shapely_poly, "exterior", None)
                if exterior is not None:
                    polygon_coords = [(float(pt[0]), float(pt[1])) for pt in exterior.coords]
            except Exception:
                continue
        
        if not polygon_coords:
            continue
            
        layer = g.layer_name.upper()
        if "JALAN" in layer:
            road_polygons.append(polygon_coords)
        elif "RTH" in layer or "HIJAU" in layer or "TAMAN" in layer:
            rth_polygons.append(polygon_coords)
        elif "KDB" in layer or "KAVELING" in layer or "KAVLING" in layer:
            kavling_polygons.append(polygon_coords)
        else:
            psu_polygons.append(polygon_coords)
            
    return {
        "id_permohonan": id_permohonan,
        "roadPolygons": road_polygons,
        "rthPolygons": rth_polygons,
        "psuPolygons": psu_polygons,
        "kavlingPolygons": kavling_polygons
    }

@router.post("/ocr/ktp", status_code=status.HTTP_200_OK)
async def ocr_ktp(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Mengekstrak data NIK, Nama, dan Alamat dari dokumen KTP (OCR)."""
    try:
        from src.infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
        
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran berkas melebihi batas maksimal 20MB.")
        adapter = TesseractOcrAdapter()
        data = adapter.extract_ktp_data(content)
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses OCR KTP: {str(e)}")

@router.post("/ocr/nib", status_code=status.HTTP_200_OK)
async def ocr_nib(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Mengekstrak data NIB, Nama Perusahaan, dan Alamat Perusahaan dari dokumen NIB (OCR)."""
    try:
        from src.infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
        
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Ukuran berkas melebihi batas maksimal 20MB.")
        adapter = TesseractOcrAdapter()
        data = adapter.extract_nib_data(content)
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses OCR NIB: {str(e)}")
