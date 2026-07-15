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

        # 2. Cetak OTP ke Console Log agar Pemohon dapat menyalin kode tanpa WA Gateway
        print("\n" + "="*80)
        print(f" >>> [OTP BYPASS CONSOLE] NOMOR HP: {clean_phone} | KODE OTP ANDA: {otp_code} <<< ")
        print("="*80 + "\n")

        logger.info(f"[WA_GATEWAY_BYPASS] OTP sukses dicetak ke console: {otp_code} untuk nomor {clean_phone}.")
        return True