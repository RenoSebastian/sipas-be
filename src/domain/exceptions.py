"""
============================================================================
SIPAS DOMAIN EXCEPTIONS — [exceptions.py] (REVISED v1.1)
============================================================================
Peran: Mendefinisikan pengecualian (exceptions) tingkat domain murni untuk
       menegakkan aturan spasial, otentikasi OTP, dan bisnis secara arsitektural.
============================================================================
"""

from typing import Optional


class SpatialValidationError(Exception):
    """
    Pengecualian yang dilemparkan ketika koordinat spasial atau denah CAD
    melanggar batas-batas teknis tata ruang daerah (Perda).
    """
    def __init__(self, message: str, detail: Optional[str] = None):
        """
        Inisialisasi Pengecualian Spasial dengan detail opsional [sipas-fe.txt].
        Menggunakan Optional[str] agar aman dari deteksi kesalahan Pylance.
        """
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class OtpExpiredError(Exception):
    """
    Pengecualian yang dilemparkan ketika kode OTP yang dimasukkan pengguna
    telah melewati batas waktu kedaluwarsa (Time-To-Live).
    """
    def __init__(self, message: str = "Kode OTP telah kedaluwarsa. Silakan lakukan registrasi ulang."):
        self.message = message
        super().__init__(self.message)


class OtpInvalidError(Exception):
    """
    Pengecualian yang dilemparkan ketika kode OTP yang dimasukkan pengguna
    salah atau tidak cocok dengan kode aslinya.
    """
    def __init__(self, message: str = "Kode OTP yang dimasukkan salah.", remaining_attempts: Optional[int] = None):
        self.message = message
        self.remaining_attempts = remaining_attempts
        super().__init__(self.message)


class OtpMaxAttemptsReachedError(Exception):
    """
    Pengecualian yang dilemparkan ketika batas maksimal pencocokan kode OTP
    telah terlampaui sebagai bagian dari perlindungan brute-force.
    """
    def __init__(self, message: str = "Batas maksimum percobaan memasukkan OTP telah terlampaui. Sesi diblokir."):
        self.message = message
        super().__init__(self.message)