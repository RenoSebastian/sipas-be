import os
import httpx
import logging
from datetime import datetime

from src.use_cases.ports.otp_ports import WhatsAppGatewayPort

logger = logging.getLogger("sipas-be")


class WhatsAppLocalAdapter(WhatsAppGatewayPort):
    def __init__(self) -> None:
        # Membaca URL endpoint API Node.js lokal dari konfigurasi .env
        # Jika tidak ada, fallback ke alamat server localhost port 3000
        self.gateway_url = os.getenv("WA_GATEWAY_URL", "http://localhost:3000/send-otp")
        self.api_token = os.getenv("WA_GATEWAY_TOKEN", "secure_local_dev_token_bogor_sipas")

    async def send_otp(self, phone_number: str, otp_code: str) -> bool:
        # 1. Bersihkan & Standardisasi Format Nomor HP ke Kode Negara (62)
        clean_phone = phone_number.strip()
        if clean_phone.startswith("0"):
            clean_phone = "62" + clean_phone[1:]
        elif clean_phone.startswith("+"):
            clean_phone = clean_phone[1:]

        # 2. Formulasi Teks Pesan OTP Dinamis dengan Timestamp (Anti-Ban Spam Meta Filter)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_text = (
            f"Halo! Kode OTP pendaftaran akun GEOSIPAS Anda adalah: *{otp_code}*.\n\n"
            f"Kode ini dibuat otomatis pada pukul {timestamp} WIB.\n"
            f"Demi keamanan akun Anda, mohon tidak membagikan kode ini kepada siapa pun."
        )

        payload = {
            "phone": clean_phone,
            "message": message_text
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }

        logger.info(f"[WA_GATEWAY] Mengirim pesan OTP ke nomor {clean_phone} via jembatan lokal...")

        try:
            # Menggunakan AsyncClient asinkron bawaan httpx demi performa tinggi tanpa memblokir FastAPI
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.gateway_url,
                    json=payload,
                    headers=headers
                )

            if response.status_code == 200:
                logger.info(f"[WA_GATEWAY_SUCCESS] Pesan OTP sukses dikirim ke {clean_phone}.")
                return True
            else:
                logger.error(
                    f"[WA_GATEWAY_ERROR] Jembatan lokal menolak request. "
                    f"HTTP Status: {response.status_code} | Response: {response.text}"
                )
                return False

        except httpx.RequestError as exc:
            logger.error(f"[WA_GATEWAY_CRASH] Kegagalan jaringan menghubungi jembatan Node.js lokal: {str(exc)}")
            return False
        except Exception as e:
            logger.error(f"[WA_GATEWAY_CRASH] Kesalahan tidak terduga pada pengiriman WA: {str(e)}", exc_info=True)
            return False