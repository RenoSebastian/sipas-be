from abc import ABC, abstractmethod
from typing import Optional, Any


class WhatsAppGatewayPort(ABC):
    """
    Interface asinkron untuk menghubungkan backend Python dengan 
    gateway pengiriman pesan WhatsApp (SaaS API atau Node.js lokal).
    """
    @abstractmethod
    async def send_otp(self, phone_number: str, otp_code: str) -> bool:
        """
        Mengirimkan pesan teks berisi OTP ke nomor WhatsApp tujuan.
        """
        pass


class OtpSessionRepositoryPort(ABC):
    """
    Interface untuk operasi CRUD pada penyimpanan sesi registrasi sementara
    (PendingRegistrationModel / Redis / DB Sementara).
    """
    @abstractmethod
    def save(self, pending_reg: Any, commit: bool = True) -> Any:
        """
        Menyimpan atau memperbarui sesi pendaftaran sementara.
        """
        pass

    @abstractmethod
    def find_by_session_id(self, session_id: str) -> Optional[Any]:
        """
        Mencari sesi pendaftaran berdasarkan ID Sesi (UUID).
        """
        pass

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[Any]:
        """
        Mencari sesi aktif berdasarkan username calon pengguna.
        """
        pass

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Any]:
        """
        Mencari sesi aktif berdasarkan email calon pengguna.
        """
        pass

    @abstractmethod
    def find_by_phone(self, phone: str) -> Optional[Any]:
        """
        Mencari sesi aktif berdasarkan nomor telepon/WhatsApp calon pengguna.
        """
        pass

    @abstractmethod
    def delete(self, session_id: str, commit: bool = True) -> None:
        """
        Menghapus sesi pendaftaran sementara (setelah sukses verifikasi atau kadaluwarsa).
        """
        pass


class UserRepositoryPort(ABC):
    """
    Interface untuk memeriksa ketersediaan data pengguna di database utama.
    Memisahkan Use Case dari ketergantungan langsung ke SQLAlchemy Model.
    """
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[Any]:
        pass

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Any]:
        pass

    @abstractmethod
    def find_by_phone(self, phone: str) -> Optional[Any]:
        pass

    @abstractmethod
    def save(self, user: Any) -> Any:  # <--- TAMBAHKAN BARIS INI SECARA TEPAT
        pass
    
    