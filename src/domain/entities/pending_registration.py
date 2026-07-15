# --- FILE: src/domain/entities/pending_registration.py ---
"""
============================================================================
SIPAS DOMAIN ENTITY — Pending Registration [pending_registration.py]
============================================================================
Peran: Merepresentasikan data pendaftaran pengguna sementara yang sedang 
       menunggu verifikasi OTP WhatsApp di tingkat domain bisnis.
============================================================================
"""

from datetime import datetime
from typing import Optional


class PendingRegistration:
    def __init__(
        self,
        session_id: str,
        username: str,
        email: str,
        hashed_password: str,
        full_name: str,
        role: str,
        phone: str,
        otp_hash: str,
        expires_at: datetime,
        attempts: int = 0,
        resend_count: int = 0,
        last_sent_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        status: str = "PENDING",
        nip: Optional[str] = None,       # Penyelarasan: Menambahkan parameter NIP
        company: Optional[str] = None     # Penyelarasan: Menambahkan parameter Company
    ):
        self.session_id = session_id
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.role = role
        self.phone = phone
        self.nip = nip
        self.company = company
        self.otp_hash = otp_hash
        self.expires_at = expires_at
        self.attempts = attempts
        self.resend_count = resend_count
        self.last_sent_at = last_sent_at
        self.created_at = created_at
        self.status = status