"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Mock Document Generator [mock_generator.py]
============================================================================
Peran: Mengimplementasikan DocumentGeneratorPort untuk menyimulasikan
       pembuatan draf dokumen BAPL dan SK final format PDF secara asinkron.
============================================================================
"""

from pathlib import Path
from src.use_cases.verify_submission import DocumentGeneratorPort

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

    def _ensure_pdf_exists(self, dest_path: Path) -> str:
        """Membuat file PDF dummy minimal jika belum ada, agar BsreClient dapat membacanya."""
        if not dest_path.exists():
            dest_path.write_bytes(_DUMMY_PDF_HEADER)
        return str(dest_path.resolve())

    def generate_bapl_draft(self, id_permohonan: str, catatan_petugas: str) -> str:
        """Menghasilkan draf fisik file PDF BAPL tiruan secara dinamis."""
        dest_path = self.output_dir / f"bapl_{id_permohonan}.pdf"
        return self._ensure_pdf_exists(dest_path)

    def generate_final_sk_siteplan(self, id_permohonan: str) -> str:
        """Menghasilkan draf fisik file PDF SK final tiruan secara dinamis."""
        dest_path = self.output_dir / f"sk_final_{id_permohonan}.pdf"
        return self._ensure_pdf_exists(dest_path)