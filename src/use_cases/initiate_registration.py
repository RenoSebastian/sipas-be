"""
============================================================================
SIPAS USE CASE — Initiate Registration [initiate_registration.py] (REVISED v2)
============================================================================
Peran: Mengelola alur pendaftaran sementara tahap pertama.
       Menjamin pencegahan brute-force spamming OTP, penyelarasan zona waktu,
       serta perlindungan transaksional terhadap Unique Key Violation database.
       Mengunci peran pendaftaran mandiri publik wajib selalu menjadi "PEMOHON".
============================================================================
"""

import uuid
import secrets
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.use_cases.ports.otp_ports import (
    WhatsAppGatewayPort,
    OtpSessionRepositoryPort,
    UserRepositoryPort
)
from src.domain.entities.pending_registration import PendingRegistration
from src.infrastructure.security.auth import hash_password

logger = logging.getLogger("sipas-be")


@dataclass(frozen=True)
class InitiateRegistrationInputDto:
    username: str
    email: str
    password: str
    full_name: str
    role: str
    phone: str
    nip: Optional[str] = None
    company: Optional[str] = None


class InitiateRegistrationUseCase:
    def __init__(
        self,
        otp_repo: OtpSessionRepositoryPort,
        user_repo: UserRepositoryPort,
        whatsapp_gateway: WhatsAppGatewayPort
    ):
        self.otp_repo = otp_repo
        self.user_repo = user_repo
        self.whatsapp_gateway = whatsapp_gateway

    async def execute(self, dto: InitiateRegistrationInputDto) -> str:
        # 1. Validasi Keunikan Data di Database Utama (users)
        if self.user_repo.find_by_username(dto.username):
            raise ValueError("Username sudah terdaftar di sistem.")
        if self.user_repo.find_by_email(dto.email):
            raise ValueError("Alamat email sudah terdaftar di sistem.")
        if self.user_repo.find_by_phone(dto.phone):
            raise ValueError("Nomor WhatsApp sudah terdaftar di sistem.")

        # Ambil waktu UTC saat ini secara konsisten tanpa info zona waktu (PostgreSQL Naive)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # 2. Validasi & Pembersihan Sesi Lama di Database Sementara (pending_registrations)
        # Menghapus data sesi lama jika pengguna mengirim ulang pendaftaran dengan data sama
        old_sessions = []
        resend_count = 0

        # Periksa duplikasi data di tabel sementara secara berurutan
        checks = [
            (self.otp_repo.find_by_username, dto.username, "Username"),
            (self.otp_repo.find_by_email, dto.email, "Alamat email"),
            (self.otp_repo.find_by_phone, dto.phone, "Nomor WhatsApp")
        ]

        for check_func, value, label in checks:
            existing_session = check_func(value)
            if existing_session:
                # Cek jika sesi lama belum kedaluwarsa (masih aktif)
                if existing_session.expires_at > now_utc:
                    # A. Batasi waktu resend minimal berjeda 60 detik (Anti-Spam)
                    time_diff = now_utc - existing_session.last_sent_at
                    if time_diff.total_seconds() < 60:
                        remaining_seconds = int(60 - time_diff.total_seconds())
                        raise ValueError(f"Mohon tunggu {remaining_seconds} detik sebelum meminta OTP kembali.")
                    
                    # B. Batasi maksimal kirim ulang sebanyak 3 kali (Mencegah kehabisan kuota API)
                    if existing_session.resend_count >= 3:
                        raise ValueError("Batas maksimum kirim ulang OTP telah terlampaui. Silakan tunggu beberapa saat.")
                    
                    # Ambil nilai resend_count dari sesi aktif sebelumnya untuk akumulasi
                    resend_count = existing_session.resend_count + 1

                # Tambahkan sesi lama ke dalam antrean penghapusan
                old_sessions.append(existing_session)

        # Eksekusi penghapusan sesi sementara lama untuk mencegah Unique Key Constraint Violation di DB
        for old_sess in old_sessions:
            self.otp_repo.delete(old_sess.session_id, commit=False)

        # 3. Generate 6-Digit OTP secara Kriptografis Aman
        otp_code = "".join(secrets.choice("0123456789") for _ in range(6))
        
        # 4. Amankan OTP Menggunakan SHA-256 Hash Sebelum Disimpan ke Database
        otp_hash = hashlib.sha256(otp_code.encode("utf-8")).hexdigest()

        # 5. Enkripsi Kata Sandi (Menggunakan fungsi bawaan auth infrastruktur Anda)
        hashed_pw = hash_password(dto.password)

        # 6. Tentukan Parameter Sesi Sementara (Aktif selama 5 Menit)
        session_id = str(uuid.uuid4())
        expires_at = now_utc + timedelta(minutes=5)

        # 7. Buat Entity Domain PendingRegistration Baru
        # ─── KEBIJAKAN KEAMANAN (SECURITY INVARIANT) ───
        # Nilai peran ('role') dipaksa secara mutlak selalu menjadi "PEMOHON" pada pendaftaran OTP mandiri.
        # Hal ini menutup potensi eksploitasi bypass skema di mana peretas mencoba memanipulasi payload HTTP
        # untuk mendaftarkan akun internal (KADIS/KABID_PUPR) melalui jalur pendaftaran mandiri luar.
        pending_reg = PendingRegistration(
            session_id=session_id,
            username=dto.username,
            email=dto.email,
            hashed_password=hashed_pw,
            full_name=dto.full_name,
            role="PEMOHON",
            phone=dto.phone,
            nip=dto.nip,
            company=dto.company,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
            resend_count=resend_count, # Akumulasi jumlah resend
            last_sent_at=now_utc,
            created_at=now_utc
        )

        # 8. Simpan Sesi Registrasi Sementara Baru ke Repositori
        self.otp_repo.save(pending_reg)
        logger.info(f"[OTP_INITIATE] Sesi pendaftaran sementara berhasil dibuat dengan peran paksa 'PEMOHON'. ID Sesi: {session_id}")

        # 9. Kirim Kode OTP (Plain Text) Melalui WhatsApp Gateway Port secara Asinkron
        success = await self.whatsapp_gateway.send_otp(dto.phone, otp_code)
        if not success:
            # Jika pengiriman API gagal, hapus sesi sementara yang baru dibuat agar tidak mengunci data
            self.otp_repo.delete(session_id)
            logger.error(f"[OTP_INITIATE_FAILED] Gagal mengirim pesan ke gateway WhatsApp untuk nomor {dto.phone}")
            raise RuntimeError("Gagal mengirimkan pesan OTP melalui WhatsApp Gateway. Silakan coba lagi.")

        return session_id