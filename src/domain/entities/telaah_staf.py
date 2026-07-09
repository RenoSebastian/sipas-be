# --- FILE: src/domain/entities/telaah_staf.py ---
"""
============================================================================
SIPAS DOMAIN ENTITY — Telaah Staf [telaah_staf.py]
============================================================================
Peran: Entitas domain murni (Pure Python) yang merepresentasikan dokumen
       Telaah Staf teknis. Mengelola data 13 matriks verifikasi,
       penilaian administrasi, mutasi persetujuan Kabid, serta otomatisasi
       narasi rekomendasi berdasarkan aturan birokrasi daerah.
============================================================================
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field


class TelaahStafVerdict(str, Enum):
    """Representasi 4 keputusan kesimpulan akhir draf Telaah Staf."""
    SESUAI = "Sesuai / Dapat Disetujui"
    SESUAI_BERSYARAT = "Sesuai Bersyarat / Ketentuan Khusus"
    PERLU_PERBAIKAN = "Perlu Perbaikan / Revisi"
    TIDAK_SESUAI = "Tidak Sesuai / Ditolak"


@dataclass(frozen=True)
class VerifierInfo:
    """Value Object untuk mencatat identitas aparatur penilai secara imutabel."""
    name: str
    nip: str
    timestamp: datetime
    signature_base64: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Nama verifikator tidak boleh kosong.")
        if not self.nip.strip():
            raise ValueError("NIP verifikator wajib diisi secara legal.")


@dataclass(frozen=True)
class AdminChecklistItem:
    """Value Object penyimpan snapshot hasil verifikasi dokumen formal."""
    doc_key: str
    doc_label: str
    file_name: str
    status: str  # "SESUAI" | "TIDAK_SESUAI"
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.doc_key.strip():
            raise ValueError("Kunci identifikasi dokumen (doc_key) wajib diisi.")
        if self.status not in ["SESUAI", "TIDAK_SESUAI"]:
            raise ValueError(f"Status dokumen '{self.status}' tidak valid. Harus 'SESUAI' atau 'TIDAK_SESUAI'.")


@dataclass(frozen=True)
class TechnicalMatrixItem:
    """Value Object penyimpan snapshot hasil pengukuran 13 matriks teknis."""
    code: str                  # e.g., 'KDB', 'GSB'
    label: str                 # e.g., 'Koefisien Dasar Bangunan'
    unit: str                  # e.g., '%', 'm', 'm2'
    proposed_val: str          # Nilai masukan pemohon (Proposed)
    bylaw_val: str             # Ambang batas peraturan (Bylaw)
    verified_val: str          # Hasil hitung spasial dinas (Verified)
    status: str                # "SESUAI" | "SESUAI_BERSYARAT" | "TIDAK_SESUAI"
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Kode matriks teknis tidak boleh kosong.")
        if self.status not in ["SESUAI", "SESUAI_BERSYARAT", "TIDAK_SESUAI"]:
            raise ValueError(f"Status kelaikan teknis '{self.status}' melanggar ketentuan tata ruang.")


class TelaahStaf:
    """
    Entitas Domain Utama yang merangkum siklus hidup Telaah Staf.
    Mengunci snapshot penilaian teknis dan mengendalikan transisi veto Kabid.
    """
    def __init__(
        self,
        id_telaah: str,
        id_permohonan: str,
        verdict: TelaahStafVerdict,
        verifier: VerifierInfo,
        administrative_checklist: List[AdminChecklistItem],
        technical_matrix: List[TechnicalMatrixItem],
        created_at: Optional[datetime] = None,
        endorser: Optional[VerifierInfo] = None,
        is_overridden: bool = False,
        override_reason: Optional[str] = None,
        admin_verifier_name: Optional[str] = None,
        admin_verifier_nip: Optional[str] = None,
        admin_verified_at: Optional[str] = None
    ):
        self._id_telaah = id_telaah
        self._id_permohonan = id_permohonan
        self._verdict = verdict
        self._verifier = verifier
        self._administrative_checklist = administrative_checklist
        self._technical_matrix = technical_matrix
        self._created_at = created_at or datetime.now()
        
        # Atribut Pelacakan Hak Veto Kabid (Override & Endorsement)
        self._endorser = endorser
        self._is_overridden = is_overridden
        self._override_reason = override_reason

        # Metadata verifikasi administrasi
        self._admin_verifier_name = admin_verifier_name
        self._admin_verifier_nip = admin_verifier_nip
        self._admin_verified_at = admin_verified_at

        # Validasi konsistensi internal entitas saat inisialisasi awal
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Menegakkan kepatuhan aturan bisnis internal secara ketat (Anti-Smell Code)."""
        if not self._id_telaah.strip():
            raise ValueError("ID Telaah Staf tidak boleh kosong.")
        if not self._id_permohonan.strip():
            raise ValueError("ID Permohonan rujukan wajib diisi.")
        if not self._administrative_checklist:
            raise ValueError("Daftar verifikasi administrasi tidak boleh kosong.")
        if not self._technical_matrix:
            raise ValueError("Matriks verifikasi 13 aspek teknis wajib terisi lengkap.")
        
        # Validasi konsistensi logika veto Kabid (Kasus 3)
        if self._is_overridden:
            if not self._endorser:
                raise ValueError("Gagal: Kabid wajib tercantum sebagai endorser jika verdict di-override.")
            if not self._override_reason or not self._override_reason.strip():
                raise ValueError("Gagal: Alasan override / diskresi hukum wajib dicantumkan oleh Kabid.")

    # ─── GETTERS (PROPERTIES) ──────────────────────────────────────────────────
    @property
    def id_telaah(self) -> str:
        return self._id_telaah

    @property
    def id_permohonan(self) -> str:
        return self._id_permohonan

    @property
    def verdict(self) -> TelaahStafVerdict:
        return self._verdict

    @property
    def verifier(self) -> VerifierInfo:
        return self._verifier

    @property
    def administrative_checklist(self) -> List[AdminChecklistItem]:
        return self._administrative_checklist

    @property
    def technical_matrix(self) -> List[TechnicalMatrixItem]:
        return self._technical_matrix

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def endorser(self) -> Optional[VerifierInfo]:
        return self._endorser

    @property
    def is_overridden(self) -> bool:
        return self._is_overridden

    @property
    def admin_verifier_name(self) -> Optional[str]:
        return self._admin_verifier_name

    @property
    def admin_verifier_nip(self) -> Optional[str]:
        return self._admin_verifier_nip

    @property
    def admin_verified_at(self) -> Optional[str]:
        return self._admin_verified_at

    @property
    def override_reason(self) -> Optional[str]:
        return self._override_reason

    @property
    def dynamic_narrative(self) -> str:
        """
        Menghasilkan teks narasi hukum rekomendasi secara dinamis 
        berdasarkan status keputusan akhir (Strategy-like Pattern).
        """
        narratives = {
            TelaahStafVerdict.SESUAI: (
                "Berdasarkan ulasan verifikasi administrasi dan analisis geospasial terkalibrasi, "
                "permohonan izin e-Siteplan dinyatakan SESUAI terhadap seluruh batasan aturan RDTR. "
                "Dengan demikian, berkas direkomendasikan untuk DAPAT DISETUJUI dan diteruskan "
                "kepada Kepala Dinas untuk diterbitkan Surat Keputusan (SK) Pengesahan."
            ),
            TelaahStafVerdict.SESUAI_BERSYARAT: (
                "Berdasarkan hasil peninjauan teknis, dokumen rencana tapak dinyatakan SESUAI BERSYARAT. "
                "Pengembang diwajibkan untuk menyelesaikan catatan teknis khusus (sebagaimana tercantum "
                "dalam lampiran evaluasi) sebelum pengesahan gambar tata ruang final diserahterimakan."
            ),
            TelaahStafVerdict.PERLU_PERBAIKAN: (
                "Hasil ulasan menunjukkan adanya beberapa parameter teknis yang melanggar ketentuan daerah "
                "atau dokumen formal yang tidak lengkap. Berkas dikembalikan kepada Pemohon untuk dilakukan "
                "PERBAIKAN / REVISI sesuai dengan rincian rekomendasi koreksi Tim Teknis."
            ),
            TelaahStafVerdict.TIDAK_SESUAI: (
                "Berdasarkan ulasan komparasi spasial tiga sisi, proyek ini melanggar batasan intensitas "
                "pola ruang zonasi secara fatal dan tidak dapat ditoleransi. Berkas dinyatakan TIDAK SESUAI "
                "dan direkomendasikan untuk DITOLAK secara permanen."
            )
        }
        return narratives[self._verdict]

    # ─── DOMAIN BEHAVIOR (MUTATORS / STATE TRANSITIONS) ───────────────────────
    def endorse_by_kabid(self, kabid_name: str, kabid_nip: str) -> None:
        """Menyetujui (Endorse) dokumen Telaah Staf tanpa mengubah keputusan Tim Teknis."""
        self._endorser = VerifierInfo(
            name=kabid_name,
            nip=kabid_nip,
            timestamp=datetime.now()
        )
        self._validate_invariants()

    def override_by_kabid(
        self, 
        kabid_name: str, 
        kabid_nip: str, 
        new_verdict: TelaahStafVerdict, 
        reason: str
    ) -> None:
        """
        Mengeksekusi hak veto (Override) Kabid terhadap keputusan Tim Teknis (Kasus 3).
        Kabid mengambil alih tanggung jawab teknis secara hukum atas perubahan keputusan ini.
        """
        if not reason or not reason.strip():
            raise ValueError("Gagal: Justifikasi hukum wajib disertakan saat melakukan override.")
        if new_verdict == self._verdict:
            raise ValueError("Gagal: Verdict baru tidak boleh sama dengan verdict sebelumnya.")

        # Terapkan perubahan state
        self._endorser = VerifierInfo(
            name=kabid_name,
            nip=kabid_nip,
            timestamp=datetime.now()
        )
        self._verdict = new_verdict
        self._is_overridden = True
        self._override_reason = reason
        
        # Validasi ulang seluruh invarian pasca-mutasi untuk menjamin integritas objek
        self._validate_invariants()