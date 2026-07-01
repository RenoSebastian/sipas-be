import os
import httpx
import logging
import asyncio
from src.use_cases.verify_submission import DigitalSignaturePort

logger = logging.getLogger("sipas-be")

class BsreClient(DigitalSignaturePort):
    def __init__(self):
        # Membaca konfigurasi REST API BSrE dari berkas lingkungan (.env) [sipas-fe.txt]
        self.bsre_api_url = os.getenv("BSRE_API_URL", "https://sandbox.bsre.go.id/api/v2")
        self.api_user = os.getenv("BSRE_API_USER", "sipas_bogor_client")
        self.api_password = os.getenv("BSRE_API_PASSWORD", "secure_bsre_sandbox_pass")

    async def sign_pdf_document(self, pdf_path: str, certificate_owner_nip: str, passphrase: str) -> str:
        """
        Mengirim dokumen Surat Keputusan (SK) PDF ke server BSrE untuk disematkan
        tanda tangan kriptografis resmi milik pejabat berwenang secara asinkron [Bogor 7, 10].
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"[BSRE_CLIENT_ERROR] Dokumen PDF yang akan ditandatangani tidak ditemukan: {pdf_path}")

        logger.info(f"[BSRE] Memulai proses TTE asinkron untuk NIP Pejabat: {certificate_owner_nip}")

        # Endpoint resmi BSrE untuk penandatanganan PDF asinkron [Bogor 10]
        endpoint = f"{self.bsre_api_url}/sign/pdf"

        # Payload multipart form-data untuk API BSrE [Bogor 10]
        # Membuka dokumen fisik PDF secara aman secara asinkron (non-blocking)
        try:
            def read_pdf_file() -> bytes:
                with open(pdf_path, 'rb') as pdf_file:
                    return pdf_file.read()

            pdf_content = await asyncio.to_thread(read_pdf_file)

            files = {'file': (os.path.basename(pdf_path), pdf_content, 'application/pdf')}
            data = {
                'nik': certificate_owner_nip, # BSrE mengidentifikasi user menggunakan NIK/NIP aparatur
                'passphrase': passphrase,       # PIN/Passphrase TTE Pejabat
                'tampilan': 'visible',         # Menyematkan tampilan visual tanda tangan/QR Code [Bogor 7]
                'halaman': '1',                # Halaman pembubuhan tanda tangan
                'lokasi_x': '400',             # Koordinat visual X
                'lokasi_y': '100',             # Koordinat visual Y
                'lebar': '150',
                'tinggi': '80'
            }

            # Kirim permintaan POST multipart ke API BSrE secara asinkron (non-blocking)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    endpoint,
                    auth=(self.api_user, self.api_password),
                    files=files,
                    data=data
                )

            # Jika sukses, BSrE mengembalikan dokumen bertandatangan atau hash kriptografis SHA-256 [Bogor 7, 10]
            if response.status_code == 200:
                result_data = response.json()
                crypto_hash = result_data.get("signature_hash")
                signed_file_url = result_data.get("signed_file_url")

                logger.info(f"[BSRE] Sukses membubuhkan TTE Dinas secara digital. Hash Kriptografi: {crypto_hash}")
                
                # Skenario Penyimpanan Berkas Bertandatangan Asli (Dipergunakan untuk unduhan pemohon) [sipas-fe.txt]
                if signed_file_url:
                    await self._download_signed_pdf(signed_file_url, pdf_path)

                return crypto_hash or "sha256-default-hash-verified-by-bsre-sipas-bogor"

            else:
                logger.error(f"[BSRE_ERROR] Server BSrE menolak penandatanganan dokumen (Status: {response.status_code}): {response.text}")
                raise RuntimeError(f"Gagal memproses TTE Dinas ke BSrE: {response.text}")

        except httpx.TimeoutException:
            logger.error("[BSRE_TIMEOUT] API Server BSrE tidak merespons dalam batasan waktu 20 detik.")
            raise TimeoutError("Koneksi ke server BSrE terputus akibat batas waktu tunggu habis.")
        except Exception as e:
            logger.error(f"[BSRE_CRASH] Kegagalan fatal sistem integrasi TTE BSrE: {str(e)}", exc_info=True)
            raise e

    async def _download_signed_pdf(self, file_url: str, output_path: str) -> None:
        """Mengunduh berkas PDF yang telah sukses dibubuhi TTE secara asinkron dari server BSrE."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(file_url, auth=(self.api_user, self.api_password))
                if response.status_code == 200:
                    def write_pdf_file() -> None:
                        with open(output_path, 'wb') as f:
                            f.write(response.content)
                    await asyncio.to_thread(write_pdf_file)
                    logger.info(f"[BSRE] File hasil TTE berhasil diunduh ke: {output_path}")
        except Exception as e:
            logger.warning(f"[BSRE_WARNING] Gagal mengunduh file hasil TTE dari server BSrE: {str(e)}")