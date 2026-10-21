"""
============================================================================
SIPAS SECURITY — Authentication Helper [auth.py] (REVISED v6)
============================================================================
Peran: Menyediakan enkripsi kata sandi (bcrypt murni) dan penanganan
       token JWT OAuth2 untuk otorisasi endpoint dinas Kabupaten Bogor.
       Menghapus ketergantungan Passlib karena tidak kompatibel dengan
       Python 3.12+/Bcrypt 5.0, mendaftarkan peran KADIS, serta mengamankan
       requires_roles dari crash format string primitif rute lama.
============================================================================
"""

import jwt
import bcrypt
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import UserModel

# ─── SECTION 1: SYSTEM ROLES ENUM ─────────────────────────────────────────
# Menghilangkan smell code "Magic Strings" untuk proteksi otorisasi tipe-aman.

class UserRole(str, Enum):
    PEMOHON = "PEMOHON"          # User luar (Pengembang / Masyarakat)
    ADMIN = "ADMIN"              # Petugas Verifikator Awal (Administrasi) & Pengelola Akun
    KASI = "KASI"                # Kepala Seksi (Verifikasi Sektoral)
    TIM_TEKNIS = "TIM_TEKNIS"    # Ketua Tim Teknis (Verifikator Spasial & Telaah Staf)
    KABID_PUPR = "KABID_PUPR"    # Kepala Bidang (Reviewer Draf SK & Endorser Telaah Staf)
    SEKDIS = "SEKDIS"            # Sekretaris Dinas (Paraf Koordinasi Administrasi Dinas)
    KADIS = "KADIS"              # Kepala Dinas (Otoritas Final Penandatangan TTE SK Resmi)


SECRET_KEY = "geosipas-super-secret-key-bogor-gis-sipas"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # Durasi sesi 2 jam demi kenyamanan operasional dinas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")




# ─── SECTION 3: NATIVE BCRYPT CRYPTOGRAPHY (No Passlib Dependency) ────────

def hash_password(password: str) -> str:
    """Mengenkripsi password mentah menjadi hash bcrypt murni (Native Bcrypt 5.0)."""
    # Bcrypt membutuhkan konversi string ke format bytes
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)  # Tingkat keamanan standar korporasi
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi kecocokan password mentah dengan hash database menggunakan native Bcrypt."""
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


# ─── SECTION 4: JWT TOKEN OPERATIONS ──────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Membuat Token JWT bertanda tangan aman untuk autentikasi sesi user."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Mendekode token JWT dan memvalidasi keutuhan tanda tangan kriptografisnya."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# ─── SECTION 5: FASTAPI DEPENDENCY INJECTION GENERATORS ───────────────────

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    """Dependency Injection FastAPI untuk mengekstrak data user aktif dari token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesi Anda telah berakhir. Silakan lakukan masuk (login) ulang.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    username = payload.get("sub")
    if not isinstance(username, str):
        raise credentials_exception
        
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """Memastikan bahwa user yang terautentikasi berstatus aktif di sistem dinas."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun Anda dinonaktifkan oleh administrator sistem."
        )
    return current_user


def requires_roles(allowed_roles: List[Union[UserRole, str]]):
    """
    FastAPI dependency to enforce strict Role-Based Access Control (RBAC).
    Mengembalikan entitas UserModel dari user terautentikasi jika perannya diizinkan.
    """
    allowed_role_strings = [
        role.value if isinstance(role, UserRole) else str(role)
        for role in allowed_roles
    ]

    def dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        user_role = current_user.role
        if user_role == "SUPER_ADMIN" or user_role in allowed_role_strings:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Hak akses ditolak. Peran Anda ({user_role}) tidak memiliki wewenang untuk mengakses sumber daya ini."
        )
    return dependency