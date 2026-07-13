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
from src.domain.entities.sk_draft import SkDraft  # <--- INJEKSI BARU (Tahap 1 & 4)


class DocumentGeneratorPort(ABC):
    """
    Abstraksi Kontrak Penghasil Dokumen Resmi Daerah (PDF).
    Wajib diimplementasikan oleh adapter di lapisan infrastruktur.
    """

    @abstractmethod
    def generate_telaah_staf_pdf(
        self, 
        telaah_staf: TelaahStaf, 
        permohonan: Permohonan,
        generated_by: Optional[str] = None
    ) -> str:
        """
        Mengompilasi data snapshot verifikasi teknis & administrasi dari objek
        TelaahStaf serta metrik sandingan 3-sisi dari objek Permohonan menjadi 
        berkas fisik PDF resmi untuk konsumsi peninjauan Kabid & Kadis.

        Args:
            telaah_staf: Entitas domain berisi 13 matriks dan verifikasi formal.
            permohonan: Entitas domain berisi parameter teknis dasar, 
                        usulan pemohon (proposed), regulasi (bylaw), 
                        dan hasil pengukuran dinas (verified).

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
        sk_draft: SkDraft,  # <--- PARAMETER BARU (Rich Domain Entity)
        notes_by_kabid: Optional[str] = None,
        generated_by: Optional[str] = None
    ) -> str:
        """
        Menghasilkan draf dokumen Surat Keputusan (SK) Pengesahan Site Plan
        lengkap dengan muatan diktum teknis (KEDUA) untuk diperiksa dan 
        diberikan catatan paraf oleh Kepala Bidang (Kabid).

        Args:
            permohonan: Entitas permohonan berisi detail parameter tata ruang.
            sk_draft: Entitas draf hukum SK yang berisi data diktum terstruktur.
            notes_by_kabid: Catatan khusus/paraf internal dari Kabid jika ada.

        Returns:
            str: Jalur lokasi fisik absolut berkas PDF draf SK di server.
        """
        pass

    @abstractmethod
    def generate_final_sk_siteplan(
        self, 
        permohonan: Permohonan,
        sk_draft: SkDraft,  # <--- PARAMETER BARU (Rich Domain Entity)
        generated_by: Optional[str] = None
    ) -> str:
        """
        Menghasilkan dokumen Surat Keputusan (SK) Pengesahan Site Plan final
        yang bersih dari catatan draf, siap untuk dibubuhi tanda tangan 
        visual TTE Coret Kepala Dinas (Kadis).

        Args:
            permohonan: Entitas permohonan yang telah disetujui Kabid & Kadis.
            sk_draft: Entitas hukum SK yang telah dibubuhi visual signature Kadis.

        Returns:
            str: Jalur lokasi fisik absolut berkas PDF SK final siap TTE.
        """
        pass