from abc import ABC, abstractmethod
from typing import Dict

class OcrPort(ABC):
    @abstractmethod
    def extract_ktp_data(self, image_bytes: bytes) -> Dict[str, str]:
        """Mengekstraksi data KTP (NIK, Nama, Alamat) dari bytes gambar."""
        pass

    @abstractmethod
    def extract_nib_data(self, image_bytes: bytes) -> Dict[str, str]:
        """Mengekstraksi data NIB (NIB, Nama Perusahaan, Alamat Perusahaan) dari bytes gambar."""
        pass
