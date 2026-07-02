"""
============================================================================
SIPAS SECURITY — Authentication Helper [auth.py]
============================================================================
Peran: Menyediakan enkripsi kata sandi (bcrypt murni) dan penanganan
       token JWT OAuth2 untuk otorisasi endpoint dinas Kabupaten Bogor.
       MEMBUANG ketergantungan Passlib karena abandonware dan tidak kompatibel
       dengan Python 3.12+/Bcrypt 5.0.
============================================================================
"""

import jwt
import bcrypt  # <-- Perbaikan: Menggunakan native bcrypt secara langsung
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import UserModel

SECRET_KEY = "geosipas-super-secret-key-bogor-gis-sipas"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def requires_roles(allowed_roles: List[str]):
    """
    FastAPI dependency to enforce strict Role-Based Access Control (RBAC) via JWT claims.

    KEBIJAKAN SOD (SEGREGATION OF DUTIES):
        Fungsi ini melakukan pemeriksaan peran secara MURNI berdasarkan daftar `allowed_roles`
        yang diberikan pada setiap endpoint. TIDAK ADA hardcoded global override yang
        mengizinkan SUPER_ADMIN untuk melewati pemeriksaan peran secara implisit.
        Setiap akses ke endpoint harus melewati validasi peran yang ketat sesuai dengan
        prinsip Segregation of Duties (SoD) dan Zero Trust Architecture.
    """
    def dependency(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token autentikasi tidak valid atau kedaluwarsa.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        role = payload.get("role")
        # Pemeriksaan peran murni — tidak ada special-case SUPER_ADMIN di sini.
        # Akses harus secara eksplisit didaftarkan pada setiap endpoint.
        if not role or role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hak akses ditolak. Peran Anda tidak memiliki wewenang untuk mengakses sumber daya ini."
            )
        return payload
    return dependency

def hash_password(password: str) -> str:
    """Mengenkripsi password mentah menjadi hash bcrypt murni (Native Bcrypt 5.0)."""
    # Bcrypt mengharuskan konversi data string ke format bytes
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Membuat Token JWT untuk autentikasi user."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Mendekode token JWT dan memvalidasi integritasnya."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    """Dependency Injection FastAPI untuk mengekstrak user aktif dari JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token autentikasi tidak valid atau kedaluwarsa.",
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
    """Memastikan user yang terautentikasi berstatus aktif."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun user tidak aktif."
        )
    return current_user