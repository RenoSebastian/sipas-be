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

class MockDocumentGenerator(DocumentGeneratorPort):
    def __init__(self):
        # Buat folder 'docs' secara dinamis di root direktori kerja
        self.output_dir = Path("docs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_bapl_draft(self, id_permohonan: str, catatan_petugas: str) -> str:
        """Menghasilkan draf fisik file PDF BAPL tiruan secara dinamis."""
        dest_path = self.output_dir / f"bapl_{id_permohonan}.pdf"
        return str(dest_path.resolve())

    def generate_final_sk_siteplan(self, id_permohonan: str) -> str:
        """Menghasilkan draf fisik file PDF SK final tiruan secara dinamis."""
        dest_path = self.output_dir / f"sk_final_{id_permohonan}.pdf"
        return str(dest_path.resolve())