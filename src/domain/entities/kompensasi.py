"""
============================================================================
SIPAS DOMAIN ENTITY — Lahan Kompensasi [kompensasi.py]
============================================================================
Peran: Entitas domain murni (Pure Python) yang merepresentasikan data
       mitigasi/kewajiban kompensasi pemohon, serta menghitung rasio pemenuhan
       lahan pengganti secara otomatis [Purworejo 8].
============================================================================
"""

from enum import Enum
from typing import List, Tuple, Optional

class CompensationType(str, Enum):
    LAHAN_SAWAH = 'LAHAN_SAWAH'
    LAHAN_MAKAM_FISIK = 'LAHAN_MAKAM_FISIK'
    LAHAN_MAKAM_UANG = 'LAHAN_MAKAM_UANG'
    PSU_FISIK_TAMBAHAN = 'PSU_FISIK_TAMBAHAN'

class FulfillmentStatus(str, Enum):
    BELUM_TERPENUHI = 'BELUM_TERPENUHI'
    PROSES_VERIFIKASI = 'PROSES_VERIFIKASI'
    TERPENUHI = 'TERPENUHI'

class LahanKompensasi:
    def __init__(
        self,
        id_kompensasi: str,
        id_permohonan: str,
        tipe_kompensasi: CompensationType,
        luas_kompensasi_m2: float,
        polygon_coords: Optional[List[Tuple[float, float]]] = None, # Format standard: [(lat, lng), ...] [sipas-fe.txt]
        status_pemenuhan: FulfillmentStatus = FulfillmentStatus.BELUM_TERPENUHI,
        nilai_nominal: float = 0.0,
        bukti_legalitas_url: Optional[str] = None,
        alamat_lokasi: Optional[str] = None
    ):
        self.id_kompensasi = id_kompensasi
        self.id_permohonan = id_permohonan
        self.tipe_kompensasi = tipe_kompensasi
        self.alamat_lokasi = alamat_lokasi
        
        if luas_kompensasi_m2 < 0:
            raise ValueError("Luas lahan kompensasi tidak boleh bernilai negatif.")
        self.luas_kompensasi_m2 = luas_kompensasi_m2
        
        self.polygon_coords = polygon_coords or []
        self.status_pemenuhan = status_pemenuhan
        
        if nilai_nominal < 0:
            raise ValueError("Nilai nominal uang pengganti tidak boleh negatif.")
        self.nilai_nominal = nilai_nominal
        self.bukti_legalitas_url = bukti_legalitas_url

    # ─── INVARIANT 1: RASIO MINIMUM MAKAM 2% [Purworejo 8, sipas-fe.txt] ──────────
    def validate_cemetery_ratio(self, total_housing_area: float) -> bool:
        """
        Memastikan bahwa jika kompensasi berupa penyediaan fisik tanah makam,
        maka luas lahan pengganti wajib minimal berkisar >= 2% dari total luas perumahan.
        """
        if self.tipe_kompensasi != CompensationType.LAHAN_MAKAM_FISIK:
            return True
            
        required_minimum = total_housing_area * 0.02 # Standar Perda Makam 2% [Purworejo 8]
        return self.luas_kompensasi_m2 >= required_minimum

    # ─── INVARIANT 2: RASIO PENGGANTIAN SAWAH 1:1 [Bogor 11, Purworejo 1] ────────
    def validate_ricefield_compensation(self, utilized_ricefield_area: float) -> bool:
        """
        Memastikan bahwa jika pengembang memanfaatkan lahan sawah produktif (KP2B),
        maka wajib mengganti dengan lahan sawah di tempat lain minimal seluas rasio 1:1.
        """
        if self.tipe_kompensasi != CompensationType.LAHAN_SAWAH:
            return True
            
        # Sawah pengganti wajib minimal sama luasnya dengan sawah yang dikonversi (1:1) [Bogor 11]
        return self.luas_kompensasi_m2 >= utilized_ricefield_area

    # ─── INVARIANT 3: KETENTUAN TRANSISI STATUS TERPENUHI [sipas-fe.txt] ─────────
    def verify_and_fulfill(self, is_valid_geospatial: bool) -> None:
        """
        Mengubah status kompensasi menjadi TERPENUHI secara aman.
        Wajib lolos uji spasial di peta dan memiliki dokumen legalitas [Purworejo 8, sipas-fe.txt].
        """
        if self.tipe_kompensasi == CompensationType.LAHAN_MAKAM_UANG:
            if self.nilai_nominal <= 0:
                raise ValueError("Gagal: Nilai nominal uang pengganti harus diisi.")
            if not self.bukti_legalitas_url:
                raise ValueError("Gagal: Bukti transfer pembayaran kas daerah wajib diunggah.")
            self.status_pemenuhan = FulfillmentStatus.TERPENUHI
            return

        # Untuk kompensasi fisik (Makam / Sawah) wajib lolos analisis spasial & sertifikat tanah [Purworejo 8]
        if not is_valid_geospatial:
            raise ValueError("Gagal: Poligon koordinat lahan pengganti melanggar batasan geospasial.")
        if not self.bukti_legalitas_url:
            raise ValueError("Gagal: Sertifikat bukti kepemilikan lahan pengganti wajib dilampirkan.")
            
        self.status_pemenuhan = FulfillmentStatus.TERPENUHI