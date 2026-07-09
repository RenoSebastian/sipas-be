# --- FILE: src/use_cases/ports/document_generator_port.py ---
"""
============================================================================
SIPAS PORT ABSTRAKSI — Document Generator Port [document_generator_port.py]
============================================================================
Peran: Menyediakan kontrak antarmuka (Port) formal bagi Use Case agar bebas 
       dari ketergantungan langsung terhadap pustaka eksternal ekspor PDF.
       Menerapkan prinsip Dependency Inversion Principle (DIP) secara mutlak.
============================================================================
"""

from abc import ABC, abstractmethod
from typing import Optional

# Impor Entitas Domain sebagai Single Source of Truth parameter masukan
from src.domain.entities.telaah_staf import TelaahStaf
from src.domain.entities.permohonan import Permohonan


class DocumentGeneratorPort(ABC):
    """
    Abstraksi Kontrak Penghasil Dokumen Resmi Daerah (PDF).
    Wajib diimplementasikan oleh adapter di lapisan infrastruktur.
    """

    @abstractmethod
    def generate_telaah_staf_pdf(
        self, 
        telaah_staf: TelaahStaf, 
        project_name: str, 
        applicant_name: str
    ) -> str:
        """
        Mengompilasi data snapshoot verifikasi teknis & administrasi dari objek
        TelaahStaf menjadi berkas fisik PDF resmi untuk konsumsi Kabid & Kadis.

        Args:
            telaah_staf: Entitas domain berisi 13 matriks dan verifikasi formal.
            project_name: Nama perumahan/kawasan yang diajukan.
            applicant_name: Nama lengkap pemohon/direktur badan usaha.

        Returns:
            str: Jalur lokasi fisik absolut (Absolute File Path) dari berkas PDF di server.

        Raises:
            RuntimeError: Jika engine PDF mengalami kegagalan render atau I/O.
        """
        pass

    @abstractmethod
    def generate_draft_sk_siteplan(
        self, 
        permohonan: Permohonan, 
        notes_by_kabid: Optional[str] = None
    ) -> str:
        """
        Menghasilkan draf dokumen Surat Keputusan (SK) Pengesahan Site Plan
        untuk diperiksa dan diberikan catatan paraf oleh Kepala Bidang (Kabid).

        Args:
            permohonan: Entitas permohonan berisi detail parameter tata ruang.
            notes_by_kabid: Catatan khusus/paraf internal dari Kabid jika ada.

        Returns:
            str: Jalur lokasi fisik absolut berkas PDF draf SK di server.
        """
        pass

    @abstractmethod
    def generate_final_sk_siteplan(self, permohonan: Permohonan) -> str:
        """
        Menghasilkan dokumen Surat Keputusan (SK) Pengesahan Site Plan final
        yang bersih dari catatan draf, siap untuk dikirimkan secara asinkron
        ke BSrE untuk dibubuhi Tanda Tangan Elektronik (TTE) Kepala Dinas (Kadis).

        Args:
            permohonan: Entitas permohonan yang telah disetujui Kabid & Kadis.

        Returns:
            str: Jalur lokasi fisik absolut berkas PDF SK final siap TTE.
        """
        pass