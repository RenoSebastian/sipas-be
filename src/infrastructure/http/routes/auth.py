from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List, cast

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import UserModel
from src.infrastructure.security.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
    requires_roles
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & User Management"])

# ─── SCHEMAS ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., examples=["ahmad_fauzi"])
    email: str = Field(..., examples=["ahmad@geocitra.co.id"])
    password: str = Field(..., min_length=6, examples=["password123"])
    full_name: str = Field(..., examples=["Ahmad Fauzi"])
    role: str = Field(default="PEMOHON", pattern="^(PEMOHON|ADMIN|TIM_TEKNIS|KABID_PUPR)$", examples=["PEMOHON"])
    nip: Optional[str] = Field(default=None, examples=["9120301938192"])
    company: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])

class UserProfileResponse(BaseModel):
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

# ─── ENDPOINTS ────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(req: UserCreate, db: Session = Depends(get_db)):
    """Mendaftar user baru ke sistem secara aman."""
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
def list_users(db: Session = Depends(get_db), token_payload: dict = Depends(requires_roles(["ADMIN"]))):
    """Mendapatkan daftar semua pengguna terdaftar (Hanya Admin)."""
    users = db.query(UserModel).all()
    return [
        {
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
def update_user_status(username: str, req: UserStatusUpdate, db: Session = Depends(get_db), token_payload: dict = Depends(requires_roles(["ADMIN"]))):
    """Mengubah status keaktifan user (Hanya Admin)."""
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")
    user.is_active = (req.status == "Aktif")
    db.commit()
    return {
        "status": "SUCCESS", 
        "message": f"Status user {username} berhasil diubah menjadi {req.status}."
    }
