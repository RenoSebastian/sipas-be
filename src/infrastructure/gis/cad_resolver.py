"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — CAD Layer Metadata Resolver [cad_resolver.py]
============================================================================
Peran: Mengimplementasikan pola Indirection untuk memetakan nama-nama layer 
       CAD dinamis (Buku 3 / OGC standard) ke dalam kategori spasial sistem 
       internal menggunakan ekspresi reguler (Regex) yang di-compile [Buku 3 11].
============================================================================
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("sipas-be")

class CADLayerResolver:
    """
    Penyedia kamus pemetaan pola layer dinamis (Buku 3 Standard Aligner).
    Menggunakan pra-kompilasi Regex (compiled regex patterns) untuk menjamin 
    kecepatan pencocokan string saat memproses ribuan entitas spasial CAD 
    di latar belakang (high-performance runtime execution).
    """

    def __init__(self):
        # ─── DEKLARATIF PATTERN DICTIONARY (Buku 1 & Buku 3 Standards) ───────────
        # Mendefinisikan kamus pencocokan kata kunci fleksibel (Wildcards/Regex)
        self._raw_patterns: Dict[str, List[str]] = {
            "PTSP_KDB": [
                r"^PTSP[-_]KDB.*",               # Cocok dengan: PTSP-KDB_PL_1, PTSP_KDB_PL_2 [Buku 1 26]
                r".*KDB.*",                      # Cocok dengan: AF_G2572_KDB_B, KAV_KDB [Buku 3 11]
                r"^KDB[-_].*"                    # Cocok dengan: KDB-BANGUNAN-UTAMA
            ],
            "PTSP_KDH": [
                r"^PTSP[-_]KDH.*",               # Cocok dengan: PTSP-KDH_PL_1, PTSP_KDH
                r".*KDH.*",                      # Cocok dengan: AF_G2516_KDH_B
                r".*HIJAU.*",                    # Cocok dengan: PEKARANGAN_HIJAU, AREA_HIJAU
                r".*RTH.*"                       # Cocok dengan: RTH-KOTA, RTH-UTAMA
            ],
            "PTSP_KTB": [
                r"^PTSP[-_]KTB.*",               # Cocok dengan: PTSP-KTB_PL_1, PTSP_KTB
                r".*KTB.*",                      # Cocok dengan: BASEMENT_KTB, AF_G2192_KTB
                r".*BASEMENT.*"                  # Cocok dengan: BASEMENT_LEVEL_1
            ],
            "PTSP_PSU_JALAN": [
                r"^PTSP[-_]PSU[-_]JALAN.*",      # Cocok dengan: PTSP-PSU-JALAN_PL_1
                r".*JALAN.*",                    # Cocok dengan: JALAN_UTAMA, G721_JALAN
                r".*ROAD.*",                     # Cocok dengan: INTERNAL_ROAD, ACCESS_ROAD
                r"^ROW[-_].*"                    # Cocok dengan: ROW-8-METER, ROW_12_M_MAIN
            ],
            "PTSP_PSU_MAKAM": [
                r"^PTSP[-_]PSU[-_]MAKAM.*",      # Cocok dengan: PTSP-PSU-MAKAM_PL_1
                r".*MAKAM.*",                    # Cocok dengan: AREA_MAKAM, KAV_MAKAM [Purworejo 8]
                r".*TPU.*",                      # Cocok dengan: TPU_KABUPATEN, TPU_HIJAU
                r".*CEMETERY.*"                  # Cocok dengan: CEMETERY_ZONE
            ]
        }

        # Kompilasi seluruh string pattern menjadi Pattern Object re secara aman saat inisialisasi class
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Kompilasi Regex satu kali di memori untuk optimalisasi performa CPU."""
        for target_layer, pattern_list in self._raw_patterns.items():
            self._compiled_patterns[target_layer] = [
                re.compile(pattern, re.IGNORECASE) for pattern in pattern_list
            ]
        logger.info("[CAD_RESOLVER] Sukses mengompilasi pola pemetaan layer Buku 3.")

    def resolve_system_layer(self, raw_layer_name: str) -> Optional[str]:
        """
        Menerima nama layer kotor dari file DXF/DWG, lalu mencocokkannya 
        dengan pola reguler untuk menentukan layer target internal PostGIS yang tepat.
        
        Args:
            raw_layer_name: String nama layer asli dari CAD (misal: 'AF_G2572_KDB_B') [Buku 3 11]
            
        Returns:
            String kategori layer internal (misal: 'PTSP_KDB') atau None jika tidak cocok.
        """
        if not raw_layer_name:
            return None

        # Normalisasi string: hilangkan spasi gantung dan konversikan ke huruf kapital
        clean_name = raw_layer_name.strip().upper()

        # Iterasi pencocokan pola secara dinamis (Information Expert & Protected Variations)
        for target_layer, compiled_regex_list in self._compiled_patterns.items():
            for regex in compiled_regex_list:
                if regex.match(clean_name):
                    logger.debug(f"[CAD_RESOLVER] Layer asli '{raw_layer_name}' sukses dipetakan ke '{target_layer}'")
                    return target_layer

        # Catat layer yang diabaikan (unresolved layers) ke dalam logger untuk keperluan debugging
        logger.debug(f"[CAD_RESOLVER_UNRESOLVED] Layer '{raw_layer_name}' dilewati karena tidak cocok dengan pola perda.")
        return None

    @property
    def registered_system_layers(self) -> List[str]:
        """Mendapatkan daftar seluruh kategori layer spasial internal yang sah."""
        return list(self._raw_patterns.keys())