import os
import sys
from datetime import date

# Tambahkan src ke python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.document.pdf_engine import HtmlToPdfEngine
from src.domain.entities.permohonan import Permohonan, DocumentCategory, SubmissionStatus

def test_receipt():
    print("Memulai pengujian pembuatan PDF Tanda Terima...")
    
    # 1. Inisialisasi PDF Engine
    pdf_engine = HtmlToPdfEngine()
    
    # 2. Mock Objek Permohonan
    permohonan = Permohonan(
        id_permohonan="sub-test-12345",
        submission_no="SIPAS-2026-0999",
        submission_date=date.today(),
        housing_name="Griya Harmoni Sukamakmur",
        developer_name="PT. Bangun Jaya Sentosa",
        land_area=15500.0,
        status=SubmissionStatus.MENUNGGU_VERIFIKASI,
        applicant_name="PT. Bangun Jaya Sentosa"
    )
    
    # 3. Jalankan generator
    output_path = pdf_engine.generate_receipt_pdf(permohonan)
    print(f"Hasil kompilasi tanda terima PDF disimpan di: {output_path}")
    
    # 4. Verifikasi keberadaan file
    if os.path.exists(output_path):
        print("VERIFIKASI SUKSES: Berkas PDF tanda terima berhasil terbentuk!")
        # Print file size
        size = os.path.getsize(output_path)
        print(f"Ukuran berkas: {size} bytes")
    else:
        print("VERIFIKASI GAGAL: Berkas PDF tidak ditemukan!")

if __name__ == "__main__":
    test_receipt()
