"""
============================================================================
SIPAS DOMAIN EXCEPTIONS — [exceptions.py]
============================================================================
Peran: Mendefinisikan pengecualian (exceptions) tingkat domain murni untuk
       menegakkan aturan spasial dan bisnis secara arsitektural.
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