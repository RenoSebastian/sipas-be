"""
============================================================================
SIPAS DOMAIN ENTITY — Surat Keputusan (SK) Draft [sk_draft.py]
============================================================================
Peran: Entitas domain murni (Pure Python) yang merepresentasikan draf Surat 
       Keputusan (SK) Persetujuan Rencana Tapak (Site Plan) Kabupaten Jombang / 
       Kabupaten Bogor.
       Menangani pembentukan Konsiderans (Menimbang, Mengingat, Memperhatikan),
       Diktum Keputusan, penomoran dinas otomatis sekuensial, serta visual
       tanda tangan (TTD Coret) Kepala Dinas.
============================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any


class SkVerdict(str, Enum):
    """Status kesimpulan akhir keselarasan hukum SK."""
    DAPAT_DISETUJUI = "DAPAT_DISETUJUI"
    BATAL_DEMI_HUKUM = "BATAL_DEMI_HUKUM"


@dataclass(frozen=True)
class SkSignerInfo:
    """
    Value Object untuk menampung identitas sah Kepala Dinas (Kadis)
    selaku penandatangan produk hukum secara kriptografis atau visual.
    """
    name: str
    nip: str
    office_title: str = "Kepala Dinas Perumahan dan Permukiman"
    signed_at: Optional[datetime] = None
    signature_base64: Optional[str] = None  # Visual coretan TTD Kadis

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Nama pejabat penandatangan (Kadis) tidak boleh kosong.")
        if not self.nip.strip():
            raise ValueError("NIP pejabat penandatangan wajib diisi secara legal.")


@dataclass(frozen=True)
class SkDiktumHunian:
    """
    Value Object rincian kaveling efektif hunian sesuai Diktum KEDUA butir 1.
    """
    tipe_rumah: str  # Contoh: "Tipe 50", "Tipe 44"
    jumlah_unit: int
    luas_m2: float

    def __post_init__(self) -> None:
        if self.jumlah_unit < 0:
            raise ValueError("Jumlah unit kaveling hunian tidak boleh bernilai negatif.")
        if self.luas_m2 < 0:
            raise ValueError("Luas kaveling hunian tidak boleh bernilai negatif.")


@dataclass(frozen=True)
class SkDiktumPsu:
    """
    Value Object spesifikasi fasilitas umum (PSU) sesuai Diktum KEDUA butir 2.
    """
    total_psu_area_m2: float
    allocation_details: str  # Deskripsi pembagian: "Jalan, RTH, Tempat Ibadah, TPST"
    cemetery_scheme: str  # Deskripsi makam: "Kerjasama TPU Desa Denanyar"
    road_row_min: float
    road_row_max: float
    drainage_type: str = "Saluran drainase terbuka dengan konstruksi Udich"

    def __post_init__(self) -> None:
        if self.total_psu_area_m2 < 0:
            raise ValueError("Luas area PSU tidak boleh bernilai negatif.")
        if self.road_row_min < 0 or self.road_row_max < 0:
            raise ValueError("Lebar ROW jalan harus bernilai positif.")


@dataclass(frozen=True)
class SkDiktumIntensity:
    """
    Value Object batas intensitas ruang yang disahkan sesuai Diktum KEDUA butir 6.
    """
    kdb_max: float
    klb_max: float
    kdh_min: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.kdb_max <= 100.0):
            raise ValueError("Batas maksimal KDB harus berada di rentang 0% - 100%.")
        if self.klb_max < 0:
            raise ValueError("Batas maksimal KLB tidak boleh bernilai negatif.")
        if not (0.0 <= self.kdh_min <= 100.0):
            raise ValueError("Batas minimal KDH harus berada di rentang 0% - 100%.")


@dataclass(frozen=True)
class SkConsiderations:
    """
    Value Object kompilasi Konsiderans (Konsideran Hukum & Data Teknis Lapangan).
    Menghilangkan hardcoded strings di luar domain layer.
    """
    menimbang: List[str]
    mengingat: List[str]
    memperhatikan: List[str]


class SkDraft:
    """
    Entitas Domain Utama yang merepresentasikan Surat Keputusan (SK) Persetujuan Rencana Tapak.
    Mengendalikan siklus pembentukan produk hukum dinas dan penguncian diktum teknis.
    """

    def __init__(
        self,
        id_sk: str,
        id_permohonan: str,
        sequence_no: int,  # Nomor urut SK dinas dari database counter
        created_at: Optional[datetime] = None,
        classification_code: str = "600",  # Default klasifikasi PU & Perkim
        office_code: str = "415.19",  # Kode dinas instansi penerbit
        considerations: Optional[SkConsiderations] = None,
        diktum_hunian: Optional[List[SkDiktumHunian]] = None,
        diktum_psu: Optional[SkDiktumPsu] = None,
        diktum_intensity: Optional[SkDiktumIntensity] = None,
        signer: Optional[SkSignerInfo] = None,
        verdict: SkVerdict = SkVerdict.DAPAT_DISETUJUI,
        custom_notes: Optional[str] = None
    ):
        self._id_sk = id_sk
        self._id_permohonan = id_permohonan
        self._sequence_no = sequence_no
        self._created_at = created_at or datetime.now()
        self._classification_code = classification_code
        self._office_code = office_code

        # Komposisi Value Objects
        self._considerations = considerations
        self._diktum_hunian = diktum_hunian or []
        self._diktum_psu = diktum_psu
        self._diktum_intensity = diktum_intensity
        self._signer = signer
        self._verdict = verdict
        self._custom_notes = custom_notes

        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Menegakkan kepatuhan aturan bisnis instansi (Anti-Smell Code & Invariant Guard)."""
        if not self._id_sk.strip():
            raise ValueError("ID SK tidak boleh kosong secara programmatic.")
        if not self._id_permohonan.strip():
            raise ValueError("ID Permohonan rujukan eksternal wajib ditambatkan.")
        if self._sequence_no <= 0:
            raise ValueError("Nomor urut sekuensial SK dinas harus bernilai positif.")

    # ─── SECTION: INFORMATION EXPERT (AUTOMATIC SK NUMBER GENERATOR) ───────────
    @property
    def sk_number(self) -> str:
        """
        Menghasilkan Nomor Surat Keputusan Dinas Resmi secara otomatis
        berdasarkan format Permendagri: [Klasifikasi]/[Urutan]/[Kode_Dinas]/[Tahun]
        Contoh: "600/249/415.19/2026"
        """
        tahun = self._created_at.year
        return f"{self._classification_code}/{self._sequence_no}/{self._office_code}/{tahun}"

    # ─── GETTERS (PROPERTIES) ──────────────────────────────────────────────────
    @property
    def id_sk(self) -> str:
        return self._id_sk

    @property
    def id_permohonan(self) -> str:
        return self._id_permohonan

    @property
    def sequence_no(self) -> int:
        return self._sequence_no

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def considerations(self) -> Optional[SkConsiderations]:
        return self._considerations

    @property
    def diktum_hunian(self) -> List[SkDiktumHunian]:
        return self._diktum_hunian

    @property
    def diktum_psu(self) -> Optional[SkDiktumPsu]:
        return self._diktum_psu

    @property
    def diktum_intensity(self) -> Optional[SkDiktumIntensity]:
        return self._diktum_intensity

    @property
    def signer(self) -> Optional[SkSignerInfo]:
        return self._signer

    @property
    def verdict(self) -> SkVerdict:
        return self._verdict

    @property
    def custom_notes(self) -> Optional[str]:
        return self._custom_notes

    # ─── DOMAIN BEHAVIOR: SIKLUS PENANDATANGANAN TTE KADIS ──────────────────────
    def apply_drawn_signature(self, kadis_name: str, kadis_nip: str, signature_base64: str) -> None:
        """
        Mengeksekusi penandatanganan visual (TTD Coret) oleh Kepala Dinas
        pada lembar SK keputusan final.
        """
        if not signature_base64 or not signature_base64.strip():
            raise ValueError("Gagal: Visual signature biner (base64) wajib dilampirkan.")

        self._signer = SkSignerInfo(
            name=kadis_name,
            nip=kadis_nip,
            signed_at=datetime.now(),
            signature_base64=signature_base64
        )
        self._validate_invariants()

    # ─── DOMAIN BEHAVIOR: EXPORT TO SERIALIZED DATA ────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """
        Mengonversi data domain model menjadi format terstruktur (Plain Dictionary).
        Sangat krusial untuk dipetakan ke dalam payload biner JSONB PostgreSQL.
        """
        return {
            "id_sk": self._id_sk,
            "id_permohonan": self._id_permohonan,
            "sk_number": self.sk_number,
            "sequence_no": self._sequence_no,
            "classification_code": self._classification_code,
            "office_code": self._office_code,
            "created_at": self._created_at.isoformat(),
            "verdict": self._verdict.value,
            "custom_notes": self._custom_notes,
            "signer": {
                "name": self._signer.name,
                "nip": self._signer.nip,
                "office_title": self._signer.office_title,
                "signed_at": self._signer.signed_at.isoformat() if self._signer.signed_at else None,
                "signature_base64": self._signer.signature_base64
            } if self._signer else None,
            "considerations": {
                "menimbang": self._considerations.menimbang,
                "mengingat": self._considerations.mengingat,
                "memperhatikan": self._considerations.memperhatikan
            } if self._considerations else None,
            "diktum_hunian": [
                {
                    "tipe_rumah": item.tipe_rumah,
                    "jumlah_unit": item.jumlah_unit,
                    "luas_m2": item.luas_m2
                } for item in self._diktum_hunian
            ],
            "diktum_psu": {
                "total_psu_area_m2": self._diktum_psu.total_psu_area_m2,
                "allocation_details": self._diktum_psu.allocation_details,
                "cemetery_scheme": self._diktum_psu.cemetery_scheme,
                "road_row_min": self._diktum_psu.road_row_min,
                "road_row_max": self._diktum_psu.road_row_max,
                "drainage_type": self._diktum_psu.drainage_type
            } if self._diktum_psu else None,
            "diktum_intensity": {
                "kdb_max": self._diktum_intensity.kdb_max,
                "klb_max": self._diktum_intensity.klb_max,
                "kdh_min": self._diktum_intensity.kdh_min
            } if self._diktum_intensity else None
        }