"""
============================================================================
SIPAS DOMAIN VALUE OBJECTS — PKKPR Status & Parameters [pkkpr_status.py]
============================================================================
Peran: Mendefinisikan tipe enumerasi statis dan objek nilai (Value Object)
       murni tanpa dependensi framework untuk siklus hidup permohonan PKKPR,
       kategori perizinan, dan batas amplop ruang (KDB, KLB, KDH, GSB).
============================================================================
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class PKKPRStatus(str, Enum):
    """Representasi status siklus hidup permohonan PKKPR di dinas."""
    DRAFT = "DRAFT"
    PENGAJUAN_BERKAS = "PENGAJUAN_BERKAS"
    VERIFIKASI_ADMINISTRASI = "VERIFIKASI_ADMINISTRASI"
    KAJIAN_TEKNIS_SPASIAL = "KAJIAN_TEKNIS_SPASIAL"
    SIDANG_FPR = "SIDANG_FPR"
    MENUNGGU_REKOMENDASI_KABID = "MENUNGGU_REKOMENDASI_KABID"
    MENUNGGU_TTE_KADIS = "MENUNGGU_TTE_KADIS"
    DISETUJUI = "DISETUJUI"
    DITOLAK = "DITOLAK"
    TIDAK_BERLAKU = "TIDAK_BERLAKU"


class PKKPRCategory(str, Enum):
    """Kategori permohonan pemanfaatan ruang sesuai regulasi PP 21/2021."""
    NON_BERUSAHA = "NON_BERUSAHA"                 # Rumah tinggal, sarana ibadah, fasilitas sosial
    BERUSAHA_PENILAIAN = "BERUSAHA_PENILAIAN"     # Berusaha via penilaian Tim Teknis & Forum Penataan Ruang
    BERUSAHA_OTOMATIS = "BERUSAHA_OTOMATIS"       # KKKPR konfirmasi otomatis jika ada RDTR digital OSS


class FPRRecommendation(str, Enum):
    """Kesimpulan rekomendasi hasil rapat pleno Forum Penataan Ruang (FPR)."""
    DISETUJUI_SELURUHNYA = "DISETUJUI_SELURUHNYA"
    DISETUJUI_SEBAGIAN = "DISETUJUI_SEBAGIAN"
    DITOLAK = "DITOLAK"


class PKKPRFileType(str, Enum):
    """Tipe berkas lampiran yang diunggah pemohon atau dinas."""
    KTP = "KTP"
    NIB = "NIB"
    BUKTI_TANAH = "BUKTI_TANAH"
    PROPOSAL = "PROPOSAL"
    REKOM_TEKNIS = "REKOM_TEKNIS"
    NOTULA_FPR = "NOTULA_FPR"
    PTP_BPN = "PTP_BPN"
    LAINNYA = "LAINNYA"


@dataclass(frozen=True)
class SpatialEnvelope:
    """
    Value Object batas parameter pemanfaatan ruang (Envelope of Limits).
    Ditetapkan dalam SK PKKPR dan menjadi batas atas/bawah bagi permohonan Site Plan.
    """
    kdb_max_percent: Optional[float] = None       # Koefisien Dasar Bangunan Maksimal (%)
    klb_max: Optional[float] = None               # Koefisien Lantai Bangunan Maksimal
    kdh_min_percent: Optional[float] = None       # Koefisien Daerah Hijau Minimal (%)
    gsb_min_meters: Optional[float] = None        # Garis Sempadan Bangunan Minimal (meter)
    max_floors: Optional[int] = None              # Batas Ketinggian Maksimal Jumlah Lantai
    zone_code: Optional[str] = None               # Kode Zona RDTR (contoh: "R-2", "K-1")
    zone_name: Optional[str] = None               # Nama Zona (contoh: "Perumahan Kepadatan Sedang")

    def validate_siteplan_compliance(
        self,
        siteplan_kdb: Optional[float],
        siteplan_klb: Optional[float],
        siteplan_kdh: Optional[float],
        siteplan_gsb: Optional[float]
    ) -> list[str]:
        """
        Memvalidasi apakah rencana site plan patuh terhadap batas SK PKKPR.
        Mengembalikan daftar pesan pelanggaran (jika ada).
        """
        violations: list[str] = []
        if self.kdb_max_percent is not None and siteplan_kdb is not None:
            if siteplan_kdb > self.kdb_max_percent:
                violations.append(
                    f"KDB Site Plan ({siteplan_kdb}%) melebihi batas maksimal SK PKKPR ({self.kdb_max_percent}%)."
                )

        if self.klb_max is not None and siteplan_klb is not None:
            if siteplan_klb > self.klb_max:
                violations.append(
                    f"KLB Site Plan ({siteplan_klb}) melebihi batas maksimal SK PKKPR ({self.klb_max})."
                )

        if self.kdh_min_percent is not None and siteplan_kdh is not None:
            if siteplan_kdh < self.kdh_min_percent:
                violations.append(
                    f"KDH Site Plan ({siteplan_kdh}%) kurang dari batas minimal SK PKKPR ({self.kdh_min_percent}%)."
                )

        if self.gsb_min_meters is not None and siteplan_gsb is not None:
            if siteplan_gsb < self.gsb_min_meters:
                violations.append(
                    f"GSB Site Plan ({siteplan_gsb}m) kurang dari jarak sempadan minimal SK PKKPR ({self.gsb_min_meters}m)."
                )

        return violations
