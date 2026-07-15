import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.use_cases.ports.otp_ports import (
    OtpSessionRepositoryPort,
    UserRepositoryPort
)
from src.infrastructure.database.models import UserModel
from src.infrastructure.security.auth import create_access_token

logger = logging.getLogger("sipas-be")


@dataclass(frozen=True)
class VerifyRegistrationOtpInputDto:
    session_id: str
    plain_otp: str


class VerifyRegistrationOtpUseCase:
    def __init__(
        self,
        otp_repo: OtpSessionRepositoryPort,
        user_repo: UserRepositoryPort
    ):
        self.otp_repo = otp_repo
        self.user_repo = user_repo

    async def execute(self, dto: VerifyRegistrationOtpInputDto) -> Dict[str, Any]:
        # 1. Cari sesi pendaftaran sementara berdasarkan Session ID
        pending_reg = self.otp_repo.find_by_session_id(dto.session_id)
        if not pending_reg:
            raise ValueError("Sesi verifikasi tidak ditemukan atau pendaftaran telah kedaluwarsa.")

        # 2. Cek apakah status sesi sudah FAILED atau VERIFIED sebelumnya
        if pending_reg.status == "FAILED":
            raise ValueError("Sesi verifikasi ini telah diblokir karena terlalu banyak kesalahan.")
        if pending_reg.status == "VERIFIED":
            raise ValueError("Sesi verifikasi ini telah sukses diproses sebelumnya.")

        # 3. Validasi batas percobaan (Proteksi brute-force maksimal 3 kali salah)
        if pending_reg.attempts >= 3:
            pending_reg.status = "FAILED"
            self.otp_repo.save(pending_reg)
            raise ValueError("Batas maksimum kesalahan input OTP terlampaui. Sesi diblokir, silakan daftar ulang.")

        # 4. Validasi batas waktu kedaluwarsa (Maksimal 5 menit sejak pengiriman)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if now_utc > pending_reg.expires_at:
            pending_reg.status = "EXPIRED"
            self.otp_repo.save(pending_reg)
            raise ValueError("Kode OTP Anda telah kedaluwarsa. Silakan lakukan pendaftaran ulang.")

        # 5. Cocokkan Hash OTP (SHA-256)
        entered_otp_hash = hashlib.sha256(dto.plain_otp.encode("utf-8")).hexdigest()
        
        if entered_otp_hash != pending_reg.otp_hash:
            # Tambah counter kesalahan input
            pending_reg.attempts += 1
            self.otp_repo.save(pending_reg)
            
            remaining_attempts = 3 - pending_reg.attempts
            if remaining_attempts <= 0:
                pending_reg.status = "FAILED"
                self.otp_repo.save(pending_reg)
                raise ValueError("Kode OTP salah. Batas percobaan habis, silakan daftar ulang.")
            
            raise ValueError(f"Kode OTP salah. Sisa percobaan Anda: {remaining_attempts} kali.")

        # 6. OTP COCOK — Tandai sesi sebagai VERIFIED
        pending_reg.status = "VERIFIED"
        self.otp_repo.save(pending_reg, commit=False)

        # 7. Daftarkan Calon Pengguna Secara Permanen ke Database Utama (users)
        new_user = UserModel(
            username=pending_reg.username,
            email=pending_reg.email,
            hashed_password=pending_reg.hashed_password,
            full_name=pending_reg.full_name,
            role=pending_reg.role,
            is_active=True,
            nip=pending_reg.nip,
            company=pending_reg.company,
            phone=pending_reg.phone
        )
        
        # Simpan ke tabel utama
        self.user_repo.save(new_user)

        # 8. Bersihkan Sesi Sementara agar Tidak Mengotori Database
        self.otp_repo.delete(pending_reg.session_id)
        logger.info(f"[OTP_VERIFY_SUCCESS] Pengguna @{new_user.username} sukses memverifikasi OTP.")

        # 9. Buat JWT Access Token untuk Fitur Auto-Login Pasca-Registrasi
        access_token = create_access_token(data={"sub": new_user.username, "role": new_user.role})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role,
                "nip": new_user.nip,
                "company": new_user.company,
                "phone": new_user.phone,
                "status": "Aktif"
            }
        }