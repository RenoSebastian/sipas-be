# --- FILE: src/infrastructure/http/routes/auth.py ---
"""
============================================================================
SIPAS HTTP CONTROLLER — Auth Router [auth.py] (REVISED v6)
============================================================================
Peran: Menyediakan REST endpoints otentikasi, pendaftaran user baru, 
       pemutakhiran profil, otorisasi administrasi pengguna, serta
       layanan pendaftaran akun berbasis verifikasi OTP WhatsApp.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
import os
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, cast

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import UserModel, PendingRegistrationModel, AuditTrailModel
from src.infrastructure.security.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
    requires_roles,
    UserRole
)

# Integrasi Domain Ports, Use Cases, dan Adapters OTP WhatsApp
from src.use_cases.ports.otp_ports import OtpSessionRepositoryPort, UserRepositoryPort
from src.use_cases.initiate_registration import InitiateRegistrationUseCase, InitiateRegistrationInputDto
from src.use_cases.verify_registration_otp import VerifyRegistrationOtpUseCase, VerifyRegistrationOtpInputDto
from src.infrastructure.adapters.whatsapp_local_adapter import WhatsAppLocalAdapter

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & User Management"])

# ─── ADAPTOR REPOSITORI LOKAL SQL (CLEAN ARCHITECTURE INTERFACE) ──────────

class SqlOtpSessionRepository(OtpSessionRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def save(self, pending_reg, commit: bool = True):
        model = self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.session_id == pending_reg.session_id).first()
        if model:
            model.attempts = pending_reg.attempts
            model.resend_count = pending_reg.resend_count
            model.status = pending_reg.status
            model.last_sent_at = pending_reg.last_sent_at
        else:
            model = PendingRegistrationModel(
                session_id=pending_reg.session_id,
                username=pending_reg.username,
                email=pending_reg.email,
                hashed_password=pending_reg.hashed_password,
                full_name=pending_reg.full_name,
                role=pending_reg.role,
                phone=pending_reg.phone,
                nip=pending_reg.nip,
                company=pending_reg.company,
                otp_hash=pending_reg.otp_hash,
                expires_at=pending_reg.expires_at,
                attempts=pending_reg.attempts,
                resend_count=pending_reg.resend_count,
                last_sent_at=pending_reg.last_sent_at,
                status=pending_reg.status,
                created_at=pending_reg.created_at
            )
            self.db.add(model)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return pending_reg

    def find_by_session_id(self, session_id: str) -> Optional[PendingRegistrationModel]:
        return self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.session_id == session_id).first()

    def find_by_username(self, username: str) -> Optional[PendingRegistrationModel]:
        return self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.username == username).first()

    def find_by_email(self, email: str) -> Optional[PendingRegistrationModel]:
        return self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.email == email).first()

    def find_by_phone(self, phone: str) -> Optional[PendingRegistrationModel]:
        return self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.phone == phone).first()

    def delete(self, session_id: str, commit: bool = True) -> None:
        self.db.query(PendingRegistrationModel).filter(PendingRegistrationModel.session_id == session_id).delete()
        if commit:
            self.db.commit()
        else:
            self.db.flush()


class SqlUserRepository(UserRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def find_by_username(self, username: str) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.username == username).first()

    def find_by_email(self, email: str) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.email == email).first()

    def find_by_phone(self, phone: str) -> Optional[UserModel]:
        return self.db.query(UserModel).filter(UserModel.phone == phone).first()

    def save(self, user: UserModel) -> UserModel:
        self.db.add(user)
        self.db.commit()
        return user


# ─── SCHEMAS ──────────────────────────────────────────────────────────────

class InitiateRegisterRequest(BaseModel):
    username: str = Field(..., examples=["ahmad_fauzi"])
    email: str = Field(..., examples=["ahmad@geocitra.co.id"])
    password: str = Field(..., min_length=6, examples=["password123"])
    full_name: str = Field(..., examples=["Ahmad Fauzi"])
    role: str = Field(default="PEMOHON", pattern="^(PEMOHON|ADMIN|TIM_TEKNIS|KABID_PUPR|KADIS)$", examples=["PEMOHON"])
    phone: str = Field(..., examples=["081234567890"])
    nip: Optional[str] = Field(default=None, examples=["9120301938192"])
    company: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])


class VerifyOtpRequest(BaseModel):
    session_id: str = Field(..., examples=["session-uuid-string-here"])
    plain_otp: str = Field(..., min_length=6, max_length=6, examples=["123456"])


class UserCreate(BaseModel):
    username: str = Field(..., examples=["ahmad_fauzi"])
    email: str = Field(..., examples=["ahmad@geocitra.co.id"])
    password: str = Field(..., min_length=6, examples=["password123"])
    full_name: str = Field(..., examples=["Ahmad Fauzi"])
    role: str = Field(default="PEMOHON", pattern="^(PEMOHON|ADMIN|TIM_TEKNIS|KABID_PUPR|KADIS)$", examples=["PEMOHON"])
    nip: Optional[str] = Field(default=None, examples=["9120301938192"])
    company: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])

class UserProfileResponse(BaseModel):
    id: Optional[int] = None
    username: str
    email: str
    full_name: str
    role: str
    nip: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    status: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserProfileResponse
    # Flat properties for backward compatibility
    username: str
    role: str
    full_name: str

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)

class UserStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(Aktif|Nonaktif)$")

class UserUpdateAdmin(BaseModel):
    email: str = Field(..., examples=["ahmad@geocitra.co.id"])
    full_name: str = Field(..., examples=["Ahmad Fauzi"])
    role: str = Field(..., pattern="^(PEMOHON|ADMIN|TIM_TEKNIS|KABID_PUPR|KADIS)$", examples=["ADMIN"])
    nip: Optional[str] = Field(default=None, examples=["199208152018032001"])
    company: Optional[str] = Field(default=None, examples=["Dinas PUPR"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])
    password: Optional[str] = Field(default=None, min_length=6, examples=["password123"])

# ─── ENDPOINTS ────────────────────────────────────────────────────────────

@router.post("/register-otp", status_code=status.HTTP_202_ACCEPTED)
async def initiate_registration_otp(req: InitiateRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Menginisiasi registrasi user baru dengan mengirimkan kode OTP asinkron ke WhatsApp."""
    
    # ─── REVISI FASE 2: ROLE GUARD VALIDATION (OTP REGISTER) ───
    # Pendaftaran mandiri publik (via OTP) dipaksa hanya boleh untuk peran PEMOHON.
    # Peran dinas administratif hanya boleh diinisiasi jika peminta memiliki hak akses ADMIN yang sah.
    if req.role != UserRole.PEMOHON.value:
        auth_header = request.headers.get("Authorization")
        is_admin = False
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            from src.infrastructure.security.auth import decode_access_token
            payload = decode_access_token(token)
            if payload and payload.get("role") == UserRole.ADMIN.value:
                is_admin = True
        
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses Ditolak: Hanya Administrator (ADMIN) yang diizinkan mendaftarkan peran dinas internal."
            )

    # ─── REVISI FASE 3: BATASAN KEAKTIFAN TUNGGAL PEJABAT (KADIS / KABID_PUPR) ───
    if req.role in [UserRole.KADIS.value, UserRole.KABID_PUPR.value]:
        existing_active = db.query(UserModel).filter(
            UserModel.role == req.role,
            UserModel.is_active == True
        ).first()
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gagal: Pengguna aktif dengan peran {req.role} sudah terdaftar ({existing_active.full_name})."
            )

    otp_repo = SqlOtpSessionRepository(db)
    user_repo = SqlUserRepository(db)
    wa_gateway = WhatsAppLocalAdapter()

    use_case = InitiateRegistrationUseCase(
        otp_repo=otp_repo,
        user_repo=user_repo,
        whatsapp_gateway=wa_gateway
    )

    try:
        dto = InitiateRegistrationInputDto(
            username=req.username,
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            role=req.role,
            phone=req.phone,
            nip=req.nip,
            company=req.company
        )
        session_id = await use_case.execute(dto)
        return {
            "status": "SUCCESS",
            "message": "Kode OTP pendaftaran berhasil dikirim melalui WhatsApp.",
            "session_id": session_id
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_registration_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    """Memvalidasi kode OTP WhatsApp untuk mengaktifkan akun dan mengembalikan token JWT."""
    otp_repo = SqlOtpSessionRepository(db)
    user_repo = SqlUserRepository(db)

    use_case = VerifyRegistrationOtpUseCase(
        otp_repo=otp_repo,
        user_repo=user_repo
    )

    try:
        dto = VerifyRegistrationOtpInputDto(
            session_id=req.session_id,
            plain_otp=req.plain_otp
        )
        result = await use_case.execute(dto)
        return {
            "access_token": result["access_token"],
            "token_type": result["token_type"],
            "user": result["user"],
            "username": result["user"]["username"],
            "role": result["user"]["role"],
            "full_name": result["user"]["full_name"]
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(req: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Mendaftar user baru langsung tanpa OTP (Hanya Diizinkan untuk Admin atau Registrasi PEMOHON)."""
    
    # ─── REVISI FASE 2: ROLE GUARD VALIDATION (DIRECT REGISTER) ───
    # Membatasi pendaftaran peran dinas langsung agar tidak dapat ditembus oleh publik.
    if req.role != UserRole.PEMOHON.value:
        auth_header = request.headers.get("Authorization")
        is_admin = False
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            from src.infrastructure.security.auth import decode_access_token
            payload = decode_access_token(token)
            if payload and payload.get("role") == UserRole.ADMIN.value:
                is_admin = True
        
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses Ditolak: Hanya Administrator (ADMIN) yang diizinkan untuk mendaftarkan peran dinas internal."
            )

    # ─── REVISI FASE 3: BATASAN KEAKTIFAN TUNGGAL PEJABAT (KADIS / KABID_PUPR) ───
    if req.role in [UserRole.KADIS.value, UserRole.KABID_PUPR.value]:
        existing_active = db.query(UserModel).filter(
            UserModel.role == req.role,
            UserModel.is_active == True
        ).first()
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gagal: Pengguna aktif dengan peran {req.role} sudah terdaftar ({existing_active.full_name})."
            )

    existing_user = db.query(UserModel).filter(UserModel.username == req.username).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username sudah terdaftar.")
    existing_email = db.query(UserModel).filter(UserModel.email == req.email).first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email sudah terdaftar.")

    new_user = UserModel(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        is_active=True,
        nip=req.nip,
        company=req.company,
        phone=req.phone
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "status": "SUCCESS",
        "message": "User berhasil terdaftar.",
        "username": new_user.username
    }

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Memperoleh token JWT OAuth2 untuk otorisasi API dan data profil lengkap."""
    user = db.query(UserModel).filter(UserModel.username == form_data.username).first()
    if not user or not verify_password(form_data.password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun user tidak aktif."
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    profile_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "nip": user.nip,
        "company": user.company,
        "phone": user.phone,
        "status": "Aktif" if user.is_active else "Nonaktif"
    }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": profile_data,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    }

@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: UserModel = Depends(get_current_active_user)):
    """Mengambil data profil pengguna aktif berdasarkan token JWT."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "nip": current_user.nip,
        "company": current_user.company,
        "phone": current_user.phone,
        "status": "Aktif" if current_user.is_active else "Nonaktif"
    }

@router.put("/profile", response_model=UserProfileResponse)
def update_profile(req: ProfileUpdate, db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    """Memperbarui nama lengkap, email, nomor telepon, dan password secara aman."""
    if req.full_name is not None:
        current_user.full_name = req.full_name
    if req.email is not None and req.email != current_user.email:
        existing_email = db.query(UserModel).filter(UserModel.email == req.email, UserModel.id != current_user.id).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email sudah terdaftar.")
        current_user.email = req.email
    if req.phone is not None:
        current_user.phone = req.phone
    if req.password is not None and req.password != "":
        current_user.hashed_password = hash_password(req.password)
    
    db.commit()
    db.refresh(current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "nip": current_user.nip,
        "company": current_user.company,
        "phone": current_user.phone,
        "status": "Aktif" if current_user.is_active else "Nonaktif"
    }

@router.get("/users", response_model=List[UserProfileResponse])
def list_users(db: Session = Depends(get_db), token_payload: dict = Depends(requires_roles([UserRole.ADMIN]))):
    """Mendapatkan daftar semua pengguna terdaftar (Hanya Admin)."""
    users = db.query(UserModel).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "nip": u.nip,
            "company": u.company,
            "phone": u.phone,
            "status": "Aktif" if u.is_active else "Nonaktif"
        } for u in users
    ]

@router.put("/users/{username}/status")
def update_user_status(username: str, req: UserStatusUpdate, db: Session = Depends(get_db), token_payload: dict = Depends(requires_roles([UserRole.ADMIN]))):
    """Mengubah status keaktifan user (Hanya Admin)."""
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")
    
    # ─── REVISI FASE 3: VERIFIKASI KEAKTIFAN SEBELUM AKTIVASI STATUS ───
    target_active_state = (req.status == "Aktif")
    if target_active_state and user.role in [UserRole.KADIS.value, UserRole.KABID_PUPR.value]:
        existing_active = db.query(UserModel).filter(
            UserModel.role == user.role,
            UserModel.is_active == True,
            UserModel.username != username
        ).first()
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Gagal mengaktifkan akun. Peran {user.role} yang aktif saat ini "
                    f"sudah dipegang oleh '{existing_active.full_name}'."
                )
            )

    user.is_active = target_active_state
    db.commit()
    return {
        "status": "SUCCESS", 
        "message": f"Status user {username} berhasil diubah menjadi {req.status}."
    }

@router.put("/users/{username}")
def update_user_details(username: str, req: UserUpdateAdmin, db: Session = Depends(get_db), token_payload: dict = Depends(requires_roles([UserRole.ADMIN]))):
    """Mengubah data profil/role user secara administratif (Hanya Admin)."""
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")
    
    # Validasi email jika berubah
    if req.email != user.email:
        existing_email = db.query(UserModel).filter(UserModel.email == req.email, UserModel.username != username).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email sudah terdaftar.")
            
    # ─── REVISI FASE 3: VERIFIKASI BATASAN KEAKTIFAN TUNGGAL SAAT UPDATE PERAN ───
    # Jika peran dimutasi ke peran sensitif (KADIS / KABID_PUPR) dan pengguna tersebut aktif,
    # pastikan tidak menabrak pejabat aktif lainnya di dalam sistem.
    if req.role in [UserRole.KADIS.value, UserRole.KABID_PUPR.value] and user.is_active:
        existing_active = db.query(UserModel).filter(
            UserModel.role == req.role,
            UserModel.is_active == True,
            UserModel.username != username
        ).first()
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Gagal memperbarui peran. Jabatan {req.role} yang aktif saat ini "
                    f"sedang dipegang oleh '{existing_active.full_name}'."
                )
            )

    user.email = req.email
    user.full_name = req.full_name
    user.role = req.role
    user.nip = req.nip
    user.company = req.company
    user.phone = req.phone
    if req.password:
        user.hashed_password = hash_password(req.password)
        
    db.commit()
    return {
        "status": "SUCCESS",
        "message": f"Data user {username} berhasil diperbarui."
    }

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "system_config.json")

DEFAULT_CONFIG = {
    "sessionDuration": 120,
    "idleTimeout": 15,
    "isMaintenance": False,
    "maintenanceMessage": "Sistem sedang dalam pemeliharaan berkala untuk peningkatan performa. Silakan coba beberapa saat lagi.",
    "slideBanners": [
        {
            "id": "slide-1",
            "imageUrl": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?auto=format&fit=crop&w=1200&q=80",
            "title": "Selamat Datang di GEOSIPAS",
            "subtitle": "Sistem Informasi Pelayanan Pengesahan Site Plan Digital Kabupaten Bogor Terintegrasi GIS."
        },
        {
            "id": "slide-2",
            "imageUrl": "https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=1200&q=80",
            "title": "Akurasi Peta & Spasial Terpadu",
            "subtitle": "Validasi otomatis tumpang tindih tata ruang (KDB, KLB, KDH, GSB) secara presisi."
        },
        {
            "id": "slide-3",
            "imageUrl": "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?auto=format&fit=crop&w=1200&q=80",
            "title": "Efisiensi Administrasi Berjenjang",
            "subtitle": "Proses peninjauan dokumen resmi hingga penandatanganan elektronik TTE BSrE secara legal."
        }
    ],
    "rotationInterval": 5,
    "appName": "GEOSIPAS",
    "appLogo": None,
    "mapCenterLat": -6.4816,
    "mapCenterLng": 106.8560,
    "mapZoom": 11
}

def load_system_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_system_config(config_data):
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

@router.get("/config")
def get_system_config():
    """Mengambil konfigurasi sistem global."""
    return load_system_config()

@router.put("/config")
def update_system_config(req: dict, token_payload: dict = Depends(requires_roles([UserRole.ADMIN]))):
    """Memperbarui konfigurasi sistem global (Hanya Admin)."""
    save_system_config(req)
    return {"status": "SUCCESS", "message": "Konfigurasi sistem global berhasil diperbarui."}

@router.get("/audit-logs")
def get_all_audit_logs(
    limit: int = 50,
    page: int = 1,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(requires_roles([UserRole.ADMIN]))
):
    """Mendapatkan seluruh daftar log aktivitas sistem dengan pagination dan filter pencarian (Hanya Admin/Super Admin)."""
    query = db.query(AuditTrailModel)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                AuditTrailModel.submission_id.ilike(search_filter),
                AuditTrailModel.actor_name.ilike(search_filter),
                AuditTrailModel.action.ilike(search_filter),
                AuditTrailModel.notes.ilike(search_filter)
            )
        )
    
    total = query.count()
    logs = query.order_by(AuditTrailModel.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": log.id,
                "submission_id": log.submission_id,
                "actor_name": log.actor_name,
                "role": log.role,
                "action": log.action,
                "status_before": log.status_before,
                "status_after": log.status_after,
                "notes": log.notes,
                "digital_signature_hash": log.digital_signature_hash,
                "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for log in logs
        ]
    }

