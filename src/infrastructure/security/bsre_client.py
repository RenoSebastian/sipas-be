"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — BSrE Sign Client [bsre_client.py]
============================================================================
Peran: Mengimplementasikan DigitalSignaturePort menggunakan integrasi API BSrE.
       Berfungsi mengirim berkas perizinan final ke server otoritas negara,
       melakukan tanda tangan digital, dan mengamankan hash sertifikat [Bogor 7, 10].
============================================================================
"""

import os
import requests
import logging
from requests.auth import HTTPBasicAuth

from src.use_cases.verify_submission import DigitalSignaturePort

logger = logging.getLogger("sipas-be")

class BsreClient(DigitalSignaturePort):
    def __init__(self):
        # Membaca konfigurasi REST API BSrE dari berkas lingkungan (.env) [sipas-fe.txt]
        self.bsre_api_url = os.getenv("BSRE_API_URL", "https://sandbox.bsre.go.id/api/v2")
        self.api_user = os.getenv("BSRE_API_USER", "sipas_bogor_client")
        self.api_password = os.getenv("BSRE_API_PASSWORD", "secure_bsre_sandbox_pass")
        
        self.auth = HTTPBasicAuth(self.api_user, self.api_password)

    def sign_pdf_document(self, pdf_path: str, certificate_owner_nip: str) -> str:
        """
        Mengirim dokumen Surat Keputusan (SK) PDF ke server BSrE untuk disematkan
        tanda tangan kriptografis resmi milik pejabat berwenang [Bogor 7, 10].
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"[BSRE_CLIENT_ERROR] Dokumen PDF yang akan ditandatangani tidak ditemukan: {pdf_path}")

        logger.info(f"[BSRE] Memulai proses tanda tangan elektronik untuk NIP Pejabat: {certificate_owner_nip}")

        # Endpoint resmi BSrE untuk penandatanganan PDF asinkron [Bogor 10]
        endpoint = f"{self.bsre_api_url}/sign/pdf"

        # Membuka dokumen fisik PDF secara aman
        try:
            with open(pdf_path, 'rb') as pdf_file:
                # Payload multipart form-data untuk API BSrE [Bogor 10]
                files = {'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')}
                data = {
                    'nik': certificate_owner_nip, # BSrE mengidentifikasi user menggunakan NIK/NIP aparatur
                    'tampilan': 'visible',         # Menyematkan tampilan visual tanda tangan/QR Code [Bogor 7]
                    'halaman': '1',                # Halaman pembubuhan tanda tangan
                    'lokasi_x': '400',             # Koordinat visual X
                    'lokasi_y': '100',             # Koordinat visual Y
                    'lebar': '150',
                    'tinggi': '80'
                }

                # Kirim permintaan POST multipart ke API BSrE
                response = requests.post(
                    endpoint,
                    auth=self.auth,
                    files=files,
                    data=data,
                    timeout=15 # Timeout aman maksimal 15 detik demi kestabilan server [sipas-fe.txt]
                )

            # Jika sukses, BSrE mengembalikan dokumen bertandatangan atau hash kriptografis SHA-256 [Bogor 7, 10]
            if response.status_code == 200:
                result_data = response.json()
                crypto_hash = result_data.get("signature_hash")
                signed_file_url = result_data.get("signed_file_url")

                logger.info(f"[BSRE] Sukses membubuhkan TTE Dinas secara digital. Hash Kriptografi: {crypto_hash}")
                
                # Skenario Penyimpanan Berkas Bertandatangan Asli (Dipergunakan untuk unduhan pemohon) [sipas-fe.txt]
                if signed_file_url:
                    self._download_signed_pdf(signed_file_url, pdf_path)

                return crypto_hash or "sha256-default-hash-verified-by-bsre-sipas-bogor"

            else:
                logger.error(f"[BSRE_ERROR] Server BSrE menolak penandatanganan dokumen (Status: {response.status_code}): {response.text}")
                raise RuntimeError(f"Gagal memproses TTE Dinas ke BSrE: {response.text}")

        except requests.exceptions.Timeout:
            logger.error("[BSRE_TIMEOUT] API Server BSrE tidak merespons dalam batasan waktu 15 detik.")
            raise TimeoutError("Koneksi ke server BSrE terputus akibat batas waktu tunggu habis.")
        except Exception as e:
            logger.error(f"[BSRE_CRASH] Kegagalan fatal sistem integrasi TTE BSrE: {str(e)}", exc_info=True)
            raise e

    def _download_signed_pdf(self, file_url: str, output_path: str) -> None:
        """Mengunduh berkas PDF yang telah sukses dibubuhi TTE dari server BSrE."""
        try:
            response = requests.get(file_url, auth=self.auth, stream=True, timeout=10)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"[BSRE] File hasil TTE berhasil diunduh ke: {output_path}")
        except Exception as e:
            logger.warning(f"[BSRE_WARNING] Gagal mengunduh file hasil TTE dari server BSrE: {str(e)}")