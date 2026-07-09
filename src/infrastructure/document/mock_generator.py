# --- FILE: src/infrastructure/document/mock_generator.py ---
"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Mock Document Generator [mock_generator.py] (REVISED v6)
============================================================================
Peran: Mengimplementasikan DocumentGeneratorPort untuk menyimulasikan
       pembuatan draf dokumen BAPL, lembar Telaah Staf, draf SK, serta SK final 
       format PDF secara asinkron untuk kebutuhan testing.
       Nama file diselaraskan agar manusiawi dan mengikuti tata naskah dinas.
============================================================================
"""

import re
from pathlib import Path
from typing import Optional
from src.use_cases.ports.document_generator_port import DocumentGeneratorPort
from src.domain.entities.telaah_staf import TelaahStaf
from src.domain.entities.permohonan import Permohonan
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import PermohonanModel

# Header PDF minimal yang valid (agar os.path.exists dan file read berhasil)
_DUMMY_PDF_HEADER = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
    b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer<</Size 4 /Root 1 0 R>>\nstartxref\n%%EOF\n"
)

class MockDocumentGenerator(DocumentGeneratorPort):
    def __init__(self):
        # Buat folder 'docs' secara dinamis di root direktori kerja
        self.output_dir = Path("docs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_clean_project_identifier(self, id_permohonan: str) -> str:
        """
        Melakukan pencarian ke database secara transaksional untuk menghasilkan
        identitas file yang bersih, rapi, dan representatif bagi Pemohon.
        """
        db = SessionLocal()
        try:
            model = db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_permohonan).first()
            if model and model.submission_no:
                # Standarisasi nama rencana tapak agar aman digunakan sebagai nama file
                housing_clean = "Proyek"
                if model.housing_name:
                    # Ganti karakter non-alphanumeric dengan garis bawah (_)
                    housing_clean = re.sub(r'[^a-zA-Z0-9]', '_', model.housing_name)
                    # Satukan garis bawah yang berurutan ganda agar rapi
                    housing_clean = re.sub(r'_+', '_', housing_clean).strip('_')

                # Menghasilkan output format: "SIPAS-2026-004_Cileungsi_Green_Valley"
                return f"{model.submission_no}_{housing_clean}"
        except Exception:
            # Fallback jika terjadi kegagalan koneksi database
            pass
        finally:
            db.close()

        # Fallback ke programmatic ID jika data permohonan tidak ditemukan
        return id_permohonan

    def _ensure_pdf_exists(self, dest_path: Path) -> str:
        """Membuat file PDF dummy minimal jika belum ada, agar BsreClient dapat membacanya."""
        if not dest_path.exists():
            dest_path.write_bytes(_DUMMY_PDF_HEADER)
        return str(dest_path.resolve())

    # ─── REALISASI METODE KONTRAK PORT TERBARU ───────────────────────────────

    def generate_telaah_staf_pdf(
        self, 
        telaah_staf: TelaahStaf, 
        permohonan: Permohonan
    ) -> str:
        """Menghasilkan draf dokumen cetak Telaah Staf simulasi (Mock)."""
        clean_id = self._get_clean_project_identifier(permohonan.id_permohonan)
        dest_path = self.output_dir / f"Telaah_Staf_{clean_id}.pdf"
        return self._ensure_pdf_exists(dest_path)

    def generate_draft_sk_siteplan(
        self, 
        permohonan: Permohonan, 
        notes_by_kabid: Optional[str] = None
    ) -> str:
        """Menghasilkan draf SK Pengesahan simulasi (Mock) untuk ditinjau Kabid."""
        clean_id = self._get_clean_project_identifier(permohonan.id_permohonan)
        dest_path = self.output_dir / f"DRAFT_SK_Pengesahan_Site_Plan_{clean_id}.pdf"
        return self._ensure_pdf_exists(dest_path)

    def generate_final_sk_siteplan(self, permohonan: Permohonan) -> str:
        """Menghasilkan berkas fisik SK final simulasi (Mock) siap TTE Kadis."""
        clean_id = self._get_clean_project_identifier(permohonan.id_permohonan)
        dest_path = self.output_dir / f"SK_Pengesahan_Site_Plan_{clean_id}.pdf"
        return self._ensure_pdf_exists(dest_path)

    def generate_bapl_draft(self, id_permohonan: str, catatan_petugas: str) -> str:
        """Menghasilkan berkas fisik BAPL berformat nama dinas resmi secara dinamis."""
        clean_id = self._get_clean_project_identifier(id_permohonan)
        dest_path = self.output_dir / f"BAPL_Dinas_PUPR_{clean_id}.pdf"
        return self._ensure_pdf_exists(dest_path)