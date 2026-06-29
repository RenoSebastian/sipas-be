"""
============================================================================
SIPAS HTTP CONTROLLER — Submissions Router [submissions.py]
============================================================================
Peran: Menyediakan REST endpoints bertingkat untuk mengelola pendaftaran
       10-tahap terpadu, kalibrasi, dan peninjauan berjenjang [sipas-fe.txt].
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Tuple, Optional, Any
from datetime import datetime, date
import logging
import random

# Adapter Koneksi & Repositori Database
from src.infrastructure.database.connection import get_db
from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
from src.infrastructure.database.repositories.audit_trail_repository import AuditTrailRepository
from src.infrastructure.database.models import PermohonanModel

# Adapter Eksternal Spasial, Geoserver, dan BSrE
from src.infrastructure.gis.cad_parser import CadParser
from src.infrastructure.security.bsre_client import BsreClient
from src.infrastructure.document.mock_generator import MockDocumentGenerator

# Import Use Cases (Clean Architecture Interactors)
from src.use_cases.submit_permohonan import SubmitPermohonanUseCase, SubmitPermohonanInputDto
from src.use_cases.calibrate_cad import CalibrateCadUseCase, CalibrateCadInputDto
from src.use_cases.verify_submission import VerifySubmissionUseCase, VerifySubmissionInputDto

# Penanganan Background Task Pengurai CAD
from src.infrastructure.queue.tasks import execute_cad_parsing_background

# Utilitas Keamanan / Autentikasi JWT
from fastapi.security import OAuth2PasswordRequestForm
from src.infrastructure.security.auth import get_current_user, hash_password, verify_password, create_access_token
from src.infrastructure.database.models import UserModel

logger = logging.getLogger("sipas-be")
router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions Core"])

# ─── SECTION 1: SUB-DTO SCHEMAS (Pydantic V2 Standards) ───────────────────

class ApplicantDto(BaseModel):
    type: str = Field(pattern="^(PERORANGAN|BADAN_USAHA)$", examples=["BADAN_USAHA"])
    name: str = Field(examples=["PT Geocitra Raya"])
    nik: Optional[str] = Field(default=None, examples=["3201020304050607"])
    nib: Optional[str] = Field(default=None, examples=["9120301938192"])
    npwp: str = Field(examples=["01.234.567.8-901.000"])
    directorName: Optional[str] = Field(default=None, examples=["Ahmad Fauzi"])
    phone: str = Field(examples=["081234567890"])
    email: str = Field(examples=["ahmad.fauzi@geocitra.co.id"])
    address: str = Field(examples=["Gedung Sentosa Lt. 4, Jl. Jend. Sudirman No. 10, Jakarta Pusat"])

class SubmissionDetailsDto(BaseModel):
    submissionType: str = Field(pattern="^(BARU|REVISI|PERPANJANGAN)$", examples=["BARU"])
    activityName: str = Field(examples=["Grand Bogor Residence"])
    category: str = Field(pattern="^(PERUMAHAN|NON_PERUMAHAN|FASUM|INDUSTRI)$", examples=["PERUMAHAN"])

class LocationDetailsDto(BaseModel):
    locationName: str = Field(examples=["Lahan Baranangsiang"])
    village: str = Field(examples=["Baranangsiang"])
    district: str = Field(examples=["Bogor Timur"])
    city: str = Field(default="Kabupaten Bogor", examples=["Kabupaten Bogor"])
    province: str = Field(default="Jawa Barat", examples=["Jawa Barat"])
    fullAddress: str = Field(examples=["Jl. Raya Pajajaran No.21, Baranangsiang, Kec. Bogor Timur"])
    landArea: float = Field(gt=0, examples=[25000.0])
    ownershipStatus: str = Field(pattern="^(SHM|HGB|HAK_PAKAI|LAINNYA)$", examples=["SHM"])
    certificateNumber: str = Field(examples=["SHM No. 10293/Baranangsiang"])
    certificateOwner: str = Field(examples=["PT Geocitra Raya"])

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
    kkprNumber: str = Field(examples=["503/KKPR/PUPR/2026/089"])
    landUse: str = Field(examples=["Zona Perumahan Kepadatan Sedang"])
    greenArea: float = Field(default=0.0, examples=[3850.0])

class TechnicalDetailsDto(BaseModel):
    # A. Kategori Perumahan
    lotCount: Optional[int] = Field(default=None, examples=[120])
    housingType: Optional[str] = Field(default=None, examples=["NON_SUBSIDI"])
    cemeteryArea: Optional[float] = Field(default=None, examples=[500.0])
    roadRowMain: Optional[str] = Field(default=None, examples=["12 Meter"])
    roadRowLocal: Optional[str] = Field(default=None, examples=["8 Meter"])
    waterSystem: Optional[str] = Field(default=None, examples=["PDAM"])

    # B. Kategori Non-Perumahan
    buildingBlocks: Optional[int] = Field(default=None, examples=[3])
    kdb: Optional[float] = Field(default=None, examples=[55.2])
    klb: Optional[float] = Field(default=None, examples=[2.1])
    kdh: Optional[float] = Field(default=None, examples=[15.4])
    parkingCapacity: Optional[int] = Field(default=None, examples=[150])
    maxFloors: Optional[int] = Field(default=None, examples=[5])
    totalFloorArea: Optional[float] = Field(default=None, examples=[24000.0])

    # C. Kategori Fasum
    facilityType: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    disabledAccess: Optional[str] = Field(default=None)
    specialParking: Optional[str] = Field(default=None)
    fireProtection: Optional[str] = Field(default=None)

    # D. Kategori Industri
    warehouseCount: Optional[int] = Field(default=None)
    roadLoadMst: Optional[str] = Field(default=None)
    electricityPower: Optional[str] = Field(default=None)
    ipalCapacity: Optional[str] = Field(default=None)
    greenBufferArea: Optional[float] = Field(default=None)
    tpsB3Provision: Optional[str] = Field(default=None)

class ConsultantDto(BaseModel):
    consultantName: str = Field(examples=["Ir. Hermawan Pratama"])
    companyName: str = Field(examples=["CV Rencana Semesta"])
    picName: str = Field(examples=["Hermawan Pratama"])

class StatementDto(BaseModel):
    agreed: bool = Field(default=True)

# ─── SECTION 2: NESTED ROOT REQUEST DTO ───────────────────────────────────

class SubmitRequest(BaseModel):
    """
    Struktur data request bertingkat (nested) yang identik 100% dengan
    Zod Schema di Frontend untuk mencegah galat parsing 422 di API Gateway.
    """
    id_permohonan: Optional[str] = Field(default=None, examples=["sub-123456"])
    applicant: ApplicantDto
    submission: SubmissionDetailsDto
    location: LocationDetailsDto
    coordinate: CoordinateDto
    spatial: SpatialDetailsDto
    technical: TechnicalDetailsDto
    consultant: ConsultantDto
    statement: StatementDto

class CalibrateRequest(BaseModel):
    cad_file_path: str = Field(examples=["C:/temp/blueprint.dxf"])
    anchor_cad_1: Tuple[float, float] = Field(examples=[(10.0, 15.0)])
    anchor_cad_2: Tuple[float, float] = Field(examples=[(120.0, 95.0)])
    anchor_map_1: Tuple[float, float] = Field(examples=[(106.8272, -6.5971)]) # Lng, Lat
    anchor_map_2: Tuple[float, float] = Field(examples=[(106.8295, -6.5990)])
    actor_name: Optional[str] = Field(default=None, examples=["Andi Setiawan"])
    role: Optional[str] = Field(default=None, examples=["TIM_TEKNIS"])

class VerifyRequest(BaseModel):
    actor_name: Optional[str] = Field(default=None, examples=["H. Rudy Susmanto, S.Si"])
    role: Optional[str] = Field(default=None, examples=["KABID_PUPR"])
    nip: Optional[str] = Field(default=None, examples=["198402122010011003"])
    action_type: str = Field(pattern="^(APPROVE|REJECT)$", examples=["APPROVE"])
    notes: str = Field(examples=["Berkas dan spasial sudah divalidasi, layak terbit."])
    is_spatially_compliant: bool = Field(default=True)

# ─── SECTION 2.1: AUTHENTICATION SCHEMAS ──────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(examples=["ahmad_fauzi"])
    email: str = Field(examples=["ahmad@geocitra.co.id"])
    password: str = Field(examples=["password123"])
    full_name: str = Field(examples=["Ahmad Fauzi"])
    role: str = Field(default="PEMOHON", pattern="^(PEMOHON|ADMIN|TIM_TEKNIS|KABID_PUPR)$", examples=["PEMOHON"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str
    full_name: str

# ─── SECTION 3: HTTP ROUTE HANDLERS ───────────────────────────────────────

@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(req: UserCreate, db: Session = Depends(get_db)):
    """Mendaftar user baru ke sistem secara aman."""
    existing_user = db.query(UserModel).filter(UserModel.username == req.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar.")
    existing_email = db.query(UserModel).filter(UserModel.email == req.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")

    new_user = UserModel(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "status": "SUCCESS",
        "message": "User berhasil terdaftar.",
        "username": new_user.username
    }

@router.post("/auth/token", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Memperoleh token JWT OAuth2 untuk otorisasi API."""
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    }


@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_permohonan(
    req: SubmitRequest, 
    db: Session = Depends(get_db), 
    current_user: UserModel = Depends(get_current_user)
):
    """Menerima berkas pendaftaran terpadu satu pintu 10-tahap [Bogor 4]."""
    try:
        permohonan_repo = PermohonanRepository(db)
        audit_trail_repo = AuditTrailRepository(db)
        use_case = SubmitPermohonanUseCase(permohonan_repo, audit_trail_repo)

        # Gunakan ID yang dikirim oleh Frontend atau generasikan baru jika kosong
        id_permohonan = req.id_permohonan or f"sub-{int(datetime.utcnow().timestamp())}"
        submission_no = f"SIPAS-2026-0{random.randint(100, 999)}"

        # Panggil Use Case dengan DTO terstruktur 10-tahap lengkap
        dto = SubmitPermohonanInputDto(
            id_permohonan=id_permohonan,
            submission_no=submission_no,
            housing_name=req.submission.activityName,
            developer_name=req.applicant.name,
            land_area=req.location.landArea,
            actor_name=current_user.full_name,
            role=current_user.role,
            
            # Tahap 1
            applicant_type=req.applicant.type,
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
            
            # Tahap 10
            statement_agreed=req.statement.agreed,
            polygon=req.coordinate.polygon,
            user_id=current_user.id
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
            actor_name=current_user.full_name,
            role=current_user.role
        )

        # 1. Jalankan proses penyelarasan koordinat & validasi awal (Helmert)
        use_case.execute(dto)

        # 2. ARSITEKTUR INDIRECTION: Bungkus pemanggilan dalam closure helper tanpa parameter.
        # Ini mengeliminasi 100% bug pengetikan tipe data (Pylance Type-Check Bug).
        def run_cad_parsing_task() -> None:
            execute_cad_parsing_background(
                file_path=req.cad_file_path,
                id_permohonan=id_permohonan,
                anchor_cad_1=req.anchor_cad_1,
                anchor_cad_2=req.anchor_cad_2,
                anchor_map_1=req.anchor_map_1,
                anchor_map_2=req.anchor_map_2
            )

        # Daftarkan closure helper yang bersih ke dalam antrean latar belakang
        background_tasks.add_task(run_cad_parsing_task)

        return {
            "status": "SUCCESS",
            "message": "Penyelarasan spasial selesai. Poligon CAD sedang diekstrak di latar belakang."
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id_permohonan}/verify", status_code=status.HTTP_200_OK)
def verify_submission(
    id_permohonan: str,
    req: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Otorisasi keputusan berjenjang dan penandatanganan elektronik BSrE [Bogor 7, 10]."""
    try:
        permohonan_repo = PermohonanRepository(db)
        audit_trail_repo = AuditTrailRepository(db)
        doc_generator = MockDocumentGenerator()
        bsre_client = BsreClient()

        use_case = VerifySubmissionUseCase(
            permohonan_repo,
            doc_generator,
            bsre_client,
            audit_trail_repo
        )

        dto = VerifySubmissionInputDto(
            id_permohonan=id_permohonan,
            actor_name=current_user.full_name,
            role=current_user.role,
            nip=req.nip,
            action_type=req.action_type,
            notes=req.notes,
            is_spatially_compliant=req.is_spatially_compliant
        )

        result = use_case.execute(dto)
        return {
            "status": "SUCCESS",
            "message": f"Keputusan verifikasi berhasil direkam. Status berkas: {result.status.value}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", status_code=status.HTTP_200_OK)
def get_all_submissions(db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Mendapatkan seluruh daftar pengajuan site plan."""
    repo = PermohonanRepository(db)
    results = repo.find_all()
    # Map to JSON format matching frontend type
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
                "tpsB3Provision": r.tech_tps_b3_provision
            },
            "consultant": {
                "consultantName": r.consultant_name,
                "consultantCompanyName": r.consultant_company_name,
                "consultantPicName": r.consultant_pic_name
            },
            "location": {
                "lat": -6.595189,
                "lng": 106.816629,
                "address": r.location_full_address,
                "polygon": r.polygon or []
            }
        }
        for r in results
    ]

@router.get("/{id_permohonan}", status_code=status.HTTP_200_OK)
def get_submission_by_id(id_permohonan: str, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    """Mendapatkan data rinci pengajuan berdasarkan ID."""
    repo = PermohonanRepository(db)
    r = repo.find_by_id(id_permohonan)
    if not r:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan.")
    
    # Map to frontend structure
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
            "tpsB3Provision": r.tech_tps_b3_provision
        },
        "consultant": {
            "consultantName": r.consultant_name,
            "consultantCompanyName": r.consultant_company_name,
            "consultantPicName": r.consultant_pic_name
        },
        "location": {
            "lat": -6.595189,
            "lng": 106.816629,
            "address": r.location_full_address,
            "polygon": r.polygon or []
        },
        "documents": [
            { "id": f"doc-{r.id_permohonan}-1", "name": "Surat Permohonan.pdf", "type": "pdf", "url": "#", "uploadedAt": r.submission_date.isoformat() },
            { "id": f"doc-{r.id_permohonan}-2", "name": "Sertifikat Tanah Hak Milik.pdf", "type": "pdf", "url": "#", "uploadedAt": r.submission_date.isoformat() }
        ],
        "history": [
            { "date": r.submission_date.isoformat() + " 09:00", "status": "Draft", "notes": "Pengajuan dibuat", "actor": r.applicant_name },
            { "date": r.submission_date.isoformat() + " 10:00", "status": r.status.value, "notes": "Status terupdate ke: " + r.status.value, "actor": "Sistem" }
        ]
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
    
    for g in geoms:
        polygon_coords = []
        if g.geom:
            try:
                shapely_poly = to_shape(g.geom)
                exterior = getattr(shapely_poly, "exterior", None)
                if exterior is not None:
                    # Convert to list of [longitude, latitude]
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
        else:
            # Fallback as PSU / Kaveling / KDB
            psu_polygons.append(polygon_coords)
            
    return {
        "id_permohonan": id_permohonan,
        "roadPolygons": road_polygons,
        "rthPolygons": rth_polygons,
        "psuPolygons": psu_polygons
    }


@router.post("/ocr/ktp", status_code=status.HTTP_200_OK)
async def ocr_ktp(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Mengekstrak data NIK, Nama, dan Alamat dari dokumen KTP (OCR)."""
    try:
        from fastapi import HTTPException, UploadFile, File
        from src.infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
        
        content = await file.read()
        adapter = TesseractOcrAdapter()
        data = adapter.extract_ktp_data(content)
        return data
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Gagal memproses OCR KTP: {str(e)}")


@router.post("/ocr/nib", status_code=status.HTTP_200_OK)
async def ocr_nib(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """Mengekstrak data NIB, Nama Perusahaan, dan Alamat Perusahaan dari dokumen NIB (OCR)."""
    try:
        from fastapi import HTTPException, UploadFile, File
        from src.infrastructure.ocr.tesseract_adapter import TesseractOcrAdapter
        
        content = await file.read()
        adapter = TesseractOcrAdapter()
        data = adapter.extract_nib_data(content)
        return data
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Gagal memproses OCR NIB: {str(e)}")