"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — CAD Parser [cad_parser.py]
============================================================================
Peran: Mengimplementasikan CadParserPort menggunakan pustaka ezdxf.
       Membaca berkas gambar kerja, mem-parsing entitas garis/poligon,
       dan mengelompokkannya berdasarkan standar layer OGC daerah.
============================================================================
"""

import os
import logging
from typing import List, Tuple, Dict

import ezdxf
from ezdxf.filemanagement import readfile
from ezdxf.lldxf.const import DXFError  # Diimpor dari namespace const agar aman dari linter

# Perbaikan Pylance: Impor langsung dari submodul internal entitas
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline

from src.use_cases.calibrate_cad import CadParserPort

logger = logging.getLogger("sipas-be")

class CadParser(CadParserPort):
    def __init__(self):
        # Daftar layer standar daerah Kabupaten Bogor yang diizinkan untuk diekstrak
        self.allowed_layers = {
            "PTSP_KDB",      # Koefisien Dasar Bangunan
            "PTSP_KDH",      # Koefisien Dasar Hijau
            "PTSP_KTB",      # Koefisien Tapak Basement
            "PTSP_PSU_JALAN",# Jaringan Jalan Internal
            "PTSP_PSU_MAKAM" # Lahan Pemakaman 2%
        }

    def parse_and_extract_layers(self, file_path: str) -> Dict[str, List[List[Tuple[float, float]]]]:
        """
        Membaca file gambar kerja (DXF/DWG) dan mengekstrak koordinat lokal (x, y)
        per layer standar yang teridentifikasi.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"[CAD_PARSER_ERROR] Berkas CAD tidak ditemukan di jalur: {file_path}")

        logger.info(f"[CAD_PARSER] Memulai ekstraksi berkas spasial: {file_path}")
        extracted_data: Dict[str, List[List[Tuple[float, float]]]] = {layer: [] for layer in self.allowed_layers}

        try:
            # 1. Load dokumen CAD menggunakan ezdxf.readfile
            doc = readfile(file_path)
            model_space = doc.modelspace()

            # 2. Iterasi seluruh entitas Lightweight Polyline (LWPOLYLINE) di Model Space
            # Tipe entitas ini adalah standar paling umum untuk poligon tertutup gambar kerja arsitek
            for entity in model_space.query('LWPOLYLINE'):
                layer_name = entity.dxf.layer.upper()

                # Saring hanya layer yang disepakati untuk diaudit tata ruang
                if layer_name in self.allowed_layers:
                    # Lakukan type narrowing secara eksplisit menggunakan isinstance agar Pylance mengenali objek LWPolyline
                    if isinstance(entity, LWPolyline):
                        vertices: List[Tuple[float, float]] = []
                        # Ambil koordinat vertex (x, y) lokal
                        for vertex in entity.get_points(format='xy'):
                            vertices.append((float(vertex[0]), float(vertex[1])) if vertex else (0.0, 0.0))

                        if len(vertices) >= 3:
                            extracted_data[layer_name].append(vertices)

            # 3. Iterasi entitas 2D/3D Polyline konvensional (POLYLINE)
            for entity in model_space.query('POLYLINE'):
                layer_name = entity.dxf.layer.upper()
                if layer_name in self.allowed_layers:
                    # Lakukan type narrowing secara eksplisit menggunakan isinstance agar Pylance mengenali objek Polyline
                    if isinstance(entity, Polyline):
                        vertices: List[Tuple[float, float]] = []
                        # Ambil vertex spasial dari Polyline konvensional
                        for vertex in entity.vertices:
                            pos = vertex.dxf.location
                            if pos:
                                vertices.append((float(pos.x), float(pos.y)))

                        if len(vertices) >= 3:
                            extracted_data[layer_name].append(vertices)

            # 4. Rekam hasil parsing ke log audit
            for layer, polygons in extracted_data.items():
                if len(polygons) > 0:
                    logger.info(f"[CAD_PARSER] Berhasil mengekstrak {len(polygons)} poligon dari layer '{layer}'.")

            return extracted_data

        except DXFError as e:  # Menangkap error dari ezdxf secara aman
            logger.error(f"[CAD_PARSER_ERROR] Struktur berkas DXF rusak atau tidak valid: {str(e)}")
            raise ValueError(f"Struktur berkas CAD tidak valid atau rusak secara spasial: {str(e)}")
        except Exception as e:
            logger.error(f"[CAD_PARSER_CRASH] Kegagalan fatal saat membaca berkas CAD: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses berkas CAD di server: {str(e)}")