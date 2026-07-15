"""
============================================================================
SIPAS HTTP CONTROLLER — Submissions Router [submissions.py] (REVISED v8.2)
============================================================================
Peran: Menyediakan REST endpoints bertingkat untuk mengelola pendaftaran
       10-tahap terpadu (pendaftaran baru maupun revisi), kalibrasi,
       audit spasial, dan verifikasi berjenjang.
       Menegakkan otorisasi SoD API-Level untuk penandatanganan TTE Kadis,
       serta menyajikan visualisasi spasial instan dalam bentuk GeoJSON.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Request, Query
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
from src.infrastructure.database.repositories.sk_draft_repository import SkDraftRepository
from src.infrastructure.database.models import (
    PermohonanModel, 
    AuditTrailModel, 
    PermohonanFileModel, 
    MasterRDTRModel, 
    EvaluasiChecklistItemModel, 
    TelaahStafModel,
    SkDraftModel,
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
from src.infrastructure.http.schemas.submissions import (
    ApplicantDto,
    SubmissionDetailsDto,
    LocationDetailsDto,
    CoordinateDto,
    SpatialDetailsDto,
    TechnicalDetailsDto,
    ConsultantDto,
    StatementDto,
    DocumentDto,
    PhotoDto,
    TPUDetailsDto,
    SelfDeclaredCompensationDto,
    SubmitRequest,
    CalibrateRequest,
    EvaluasiChecklistItemDto,
    VerifyRequest
)

# ─── SECTION 2: HTTP ROUTE HANDLERS ───────────────────────────────────────

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
            bylaw_min_rth_area=bylaw_min_rth_area,

            # TPU & Kompensasi Mandiri
            tpu_method=req.tpu.method if req.tpu else None,
            tpu_area=req.tpu.area if req.tpu else None,
            tpu_nama=req.tpu.namaTpu if req.tpu else None,
            tpu_pengurus=req.tpu.pengurusTpu if req.tpu else None,
            tpu_no_pks=req.tpu.noPks if req.tpu else None,
            tpu_nominal=req.tpu.nominalKompensasi if req.tpu else None,
            tpu_address=req.tpu.alamat if req.tpu else None,
            tpu_koordinat=req.tpu.koordinat if req.tpu else None,
            tpu_bukti_dokumen=req.tpu.buktiDokumenUrl if req.tpu else None,
            self_declared_compensations=[comp.model_dump() for comp in req.compensations] if req.compensations else None,

            # ─── UPDATE FASE 5 (REVISI): SILSILAH PEMOHON INPUT DTO (MAPPER DARI HTTP SCHEMAS) ───
            baseline_source=req.baseline_source,
            parent_id_permohonan=req.parent_id_permohonan,
            replaced_sk_number=req.legacy_metadata.replaced_sk_number if req.legacy_metadata else None,
            replaced_sk_date=req.legacy_metadata.replaced_sk_date if req.legacy_metadata else None,
            replaced_sk_doc_url=req.legacy_metadata.replaced_sk_doc_url if req.legacy_metadata else None
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


@router.post("/{id_permohonan}/verify", status_code=status.HTTP_200_OK)
async def verify_submission(
    id_permohonan: str,
    req: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Otorisasi keputusan berjenjang dan penandatanganan elektronik BSrE [Bogor 7, 10]."""
    
    # ─── INTEGRITAS DATA & SOD KADIS ENDPOINT-LEVEL GATEKEEPER ───────────────
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
        sk_draft_repo = SkDraftRepository(db)
        
        # ─── PERBAIKAN PYLANCE nominal type check: Gunakan type annotation formal Port (DIP) ───
        doc_generator: DocumentGeneratorPort = HtmlToPdfEngine()
        bsre_client = BsreClient()

        use_case = VerifySubmissionUseCase(
            permohonan_repo=permohonan_repo,
            telaah_staf_repo=telaah_staf_repo,
            sk_draft_repo=sk_draft_repo,
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
        raise HTTPException(status_code=400, detail=str(e))


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
def get_all_submissions(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Kata kunci pencarian (nama perumahan, developer, atau no. berkas)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter berdasarkan status"),
    category: Optional[str] = Query(None, description="Filter berdasarkan kategori dokumen"),
    page: int = Query(1, ge=1, description="Nomor halaman (mulai dari 1)"),
    limit: int = Query(10, ge=1, le=1000, description="Jumlah data per halaman (maks. 1000)")
):
    """Mendapatkan seluruh daftar pengajuan site plan dengan pencarian, penapisan, dan paginasi."""
    repo = PermohonanRepository(db)
    # Filter hanya data milik sendiri jika login sebagai PEMOHON
    user_id = current_user.id if current_user.role == "PEMOHON" else None
    results, total_count = repo.find_all(
        search=search or None,
        status=status_filter or None,
        category=category or None,
        page=page,
        limit=limit,
        user_id=user_id
    )

    def serialize(r):
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
            "signatureHash": r.signature_hash,
            "signedPdfUrl": r.signed_pdf_url,
            "kabidSignature": r.kabid_signature,
            "disabledAccess": r.tech_disabled_access,
            "kadisSignature": r.kadis_signature,

            # Kesimpulan KKPR
            "kkprVerdict": r.kkpr_verdict.value if r.kkpr_verdict else None,
            "kkprVerifiedAt": r.kkpr_verified_at.isoformat() if r.kkpr_verified_at else None,
            "kkprVerifierName": r.kkpr_verifier_name,
            "verifiedKdb": r.verified_kdb,
            "verifiedKlb": r.verified_klb,
            "verifiedKdh": r.verified_kdh,
            "verifiedGsb": r.verified_gsb,
            "verifiedRthArea": r.verified_rth_area,

            # ─── UPDATE FASE 5 (REVISI): SILSILAH SERIALIZER KOLEKTIF ──────────
            "baseline_source": r.baseline_source,
            "parent_id_permohonan": r.parent_id_permohonan,
            "replaced_sk_number": r.replaced_sk_number,
            "replaced_sk_date": r.replaced_sk_date.isoformat() if r.replaced_sk_date else None,
            "replaced_sk_doc_url": r.replaced_sk_doc_url
        }

    import math
    total_pages = math.ceil(total_count / limit) if limit > 0 else 1
    return {
        "data": [serialize(r) for r in results],
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


@router.get("/{id_permohonan}", status_code=status.HTTP_200_OK)
def get_submission_by_id(id_permohonan: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Mendapatkan data rinci pengajuan berdasarkan ID, lengkap dengan metadata snapshot Telaah Staf."""
    repo = PermohonanRepository(db)
    r = repo.find_by_id(id_permohonan)
    if not r:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan.")

    db_files = db.query(PermohonanFileModel).filter(PermohonanFileModel.id_permohonan == id_permohonan).all()
    docs_list = []
    
    # Deklarasi tipe eksplisit untuk mencegah reportAttributeAccessIssue (Pylance compilation fix)
    photos_dict: Dict[str, Optional[str]] = {
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
                "id": str(f.id),
                "key": f.file_key,
                "name": f.file_name,
                "url": f.file_url,
                "type": f.file_name.split(".")[-1] if "." in f.file_name else "pdf",
                "uploadedAt": f.uploaded_at.isoformat() if f.uploaded_at else r.submission_date.isoformat()
            })
            if f.file_key in docs_dict:
                docs_dict[f.file_key] = f.file_url
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

    # Ambil Kompensasi awal/denda jika ada
    db_compensations = repo.find_kompensasi_by_permohonan_id(id_permohonan)
    compensations_list = [
        {
            "id": comp.id_kompensasi,
            "type": comp.tipe_kompensasi.value,
            "requiredAreaM2": comp.luas_kompensasi_m2,
            "fulfillmentMethod": "PENYEDIAAN_FISIK_OFFSITE" if comp.tipe_kompensasi.value in ['LAHAN_SAWAH', 'LAUK_MAKAM_FISIK', 'LAHAN_MAKAM_FISIK'] else "KOMPENSASI_UANG",
            "locationAddress": comp.alamat_lokasi or "-",
            "nominalAmount": comp.nilai_nominal,
            "documentUrl": comp.bukti_legalitas_url,
            "status": comp.status_pemenuhan.value
        }
        for comp in db_compensations
    ]

    # Snapshot dokumen Telaah Staf
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

    # SINKRONISASI TAFSIRAN PAYLOAD DRAFT SK UNTUK DETAIL KADIS (TAHAP 5)
    sk_draft_data = None
    sk_model = db.query(SkDraftModel).filter(SkDraftModel.id_permohonan == id_permohonan).first()
    if sk_model:
        sk_draft_data = {
            "idSk": sk_model.id_sk,
            "skNumber": sk_model.sk_number,
            "verdict": sk_model.verdict,
            "isOverridden": sk_model.is_overridden,
            "overrideReason": sk_model.override_reason,
            "createdAt": sk_model.created_at.isoformat(),
            "payload": sk_model.document_payload
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
        "disabledAccess": r.tech_disabled_access,
        "kadisSignature": r.kadis_signature,

        # TPU & Kompensasi Mandiri
        "tpu": {
            "method": r.tpu_detail.metode,
            "area": r.tpu_detail.luas,
            "namaTpu": r.tpu_detail.nama_tpu,
            "pengurusTpu": r.tpu_detail.pengurus_tpu,
            "noPks": r.tpu_detail.no_pks,
            "nominalKompensasi": r.tpu_detail.nominal_kompensasi,
            "alamat": r.tpu_detail.alamat,
            "buktiDokumenUrl": r.tpu_detail.bukti_dokumen_url,
            "statusVerifikasi": r.tpu_detail.status_verifikasi,
            "catatanVerifikasi": r.tpu_detail.catatan_verifikasi,
            "diverifikasiOleh": r.tpu_detail.diverifikasi_oleh,
            "diverifikasiPada": r.tpu_detail.diverifikasi_pada.isoformat() if r.tpu_detail.diverifikasi_pada else None
        } if r.tpu_detail else None,
        "compensations": compensations_list,

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
        "skDraft": sk_draft_data,        # Payload draf Surat Keputusan (SK) utuh

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
        ])(),

        # ─── UPDATE FASE 5 (REVISI): SILSILAH SERIALIZER SATUAN ──────────
        "baseline_source": r.baseline_source,
        "parent_id_permohonan": r.parent_id_permohonan,
        "replaced_sk_number": r.replaced_sk_number,
        "replaced_sk_date": r.replaced_sk_date.isoformat() if r.replaced_sk_date else None,
        "replaced_sk_doc_url": r.replaced_sk_doc_url
    }


# ─── INSTAN PRE-COMPILED GEOJSON ENDPOINT (PENGGANTI GEOSERVER) ───

@router.get("/{id_permohonan}/geojson", status_code=status.HTTP_200_OK)
async def get_submission_geojson(
    id_permohonan: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Mendapatkan data biner spasial GeoJSON utuh (FeatureCollection) langsung dari PostGIS."""
    repo = PermohonanRepository(db)
    # Validasi keberadaan permohonan terlebih dahulu
    permohonan = repo.find_by_id(id_permohonan)
    if not permohonan:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan.")
    
    try:
        # Memanggil kompilasi asinkron database yang telah di-optimize (ST_AsGeoJSON)
        geojson_data = await repo.get_siteplan_geojson_async(id_permohonan)
        return geojson_data
    except Exception as e:
        logger.error(f"[GET_GEOJSON_ERROR] Gagal memuat GeoJSON untuk permohonan {id_permohonan}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses visualisasi GeoJSON dari database: {str(e)}"
        )


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


from fastapi.responses import FileResponse
from pathlib import Path

@router.get("/{id_permohonan}/download", response_class=FileResponse)
async def download_signed_pdf(id_permohonan: str, db: Session = Depends(get_db)):
    """Mengunduh berkas Surat Keputusan (SK) resmi hasil TTE Kadis."""
    # 1. Pastikan permohonan ada di database
    permohonan_model = db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_permohonan).first()
    if not permohonan_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permohonan dengan ID '{id_permohonan}' tidak ditemukan."
        )

    # Pastikan direktori docs ada
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = docs_dir / f"SK_Pengesahan_Site_Plan_{id_permohonan}.pdf"
    draft_path = docs_dir / f"DRAFT_SK_Pengesahan_Site_Plan_{id_permohonan}.pdf"

    # 2. Jika file tidak ada fisik di server, coba generate secara dinamis
    if not pdf_path.exists() and not draft_path.exists():
        try:
            from src.infrastructure.database.repositories.sk_draft_repository import SkDraftRepository
            from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
            from src.infrastructure.document.pdf_engine import HtmlToPdfEngine

            # Inisialisasi adapter repo & engine dokumen
            permohonan_repo = PermohonanRepository(db)
            sk_draft_repo = SkDraftRepository(db)
            doc_generator = HtmlToPdfEngine()

            permohonan = permohonan_repo._to_domain(permohonan_model)
            sk_draft = sk_draft_repo.find_by_permohonan_id(id_permohonan)

            if sk_draft:
                if permohonan.status == "Disetujui":
                    doc_generator.generate_final_sk_siteplan(permohonan, sk_draft)
                else:
                    doc_generator.generate_draft_sk_siteplan(permohonan, sk_draft)
            else:
                # Generate PDF dummy yang rapi jika sk_draft belum dibentuk (untuk seeded/mock data)
                title = f"DRAF SK PENGESAHAN SITE PLAN - {permohonan_model.housing_name or 'PROYEK'}"
                status_text = permohonan_model.status
                html_dummy = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: sans-serif; padding: 50px; color: #334155; line-height: 1.6; }}
                        h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
                        .meta {{ margin: 20px 0; background: #f8fafc; padding: 15px; border-left: 4px solid #14b8a6; }}
                        .footer {{ margin-top: 50px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
                    </style>
                </head>
                <body>
                    <h1>{title}</h1>
                    <div class="meta">
                        <strong>Nomor Registrasi:</strong> {permohonan_model.submission_no}<br/>
                        <strong>Pengaju:</strong> {permohonan_model.developer_name or '-'}<br/>
                        <strong>Luas Lahan:</strong> {permohonan_model.land_area or 0} m²<br/>
                        <strong>Status Terakhir:</strong> {status_text}
                    </div>
                    <p>
                        Dokumen ini merupakan lampiran visual Surat Keputusan (SK) resmi yang digenerasi secara dinamis oleh GEOSIPAS 
                        untuk keperluan peninjauan dan pembuktian integrasi sistem TTE BSrE (tanda tangan elektronik).
                    </p>
                    <div class="footer">
                        GEOSIPAS Kabupaten Bogor &copy; 2026 - Sandbox TTE / BSSN Bypass
                    </div>
                </body>
                </html>
                """
                doc_generator.compile_to_pdf(html_dummy, str(draft_path))
        except Exception as e:
            logger.error(f"[DOWNLOAD_GENERATE_ERROR] Gagal memproduksi berkas secara dinamis: {str(e)}")

    # 3. Tentukan file mana yang akan diunduh
    target_path = pdf_path if pdf_path.exists() else (draft_path if draft_path.exists() else None)

    if not target_path or not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas Surat Keputusan (SK) belum diterbitkan atau tidak ditemukan."
        )

    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type="application/pdf"
    )


@router.get("/{id_permohonan}/receipt", response_class=FileResponse)
async def download_receipt_pdf(id_permohonan: str, db: Session = Depends(get_db)):
    """Mengunduh berkas tanda terima permohonan (receipt) untuk pemohon."""
    # 1. Pastikan permohonan ada di database
    permohonan_model = db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_permohonan).first()
    if not permohonan_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permohonan dengan ID '{id_permohonan}' tidak ditemukan."
        )

    # Pastikan direktori docs ada
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = docs_dir / f"Tanda_Terima_{id_permohonan}.pdf"

    # 2. Selalu generate secara dinamis tiap kali endpoint dipanggil agar mencerminkan perubahan visual terkini
    try:
        from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
        from src.infrastructure.document.pdf_engine import HtmlToPdfEngine

        # Inisialisasi adapter repo & engine dokumen
        permohonan_repo = PermohonanRepository(db)
        doc_generator = HtmlToPdfEngine()

        permohonan = permohonan_repo._to_domain(permohonan_model)
        doc_generator.generate_receipt_pdf(permohonan)
    except Exception as e:
        logger.error(f"[RECEIPT_GENERATE_ERROR] Gagal memproduksi tanda terima secara dinamis: {str(e)}")

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas Tanda Terima belum dibuat atau gagal dibuat secara dinamis."
        )

    return FileResponse(
        path=str(pdf_path),
        filename=pdf_path.name,
        media_type="application/pdf"
    )