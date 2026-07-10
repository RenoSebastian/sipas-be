"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — CAD Parser [cad_parser.py] (REVISED v6)
============================================================================
Peran: Mengimplementasikan CadParserPort menggunakan pustaka ezdxf.
       Membaca berkas gambar kerja, mem-parsing entitas garis/poligon,
       mengelompokkannya berdasarkan standar layer daerah, serta melakukan
       simplifikasi koordinat (Ramer-Douglas-Peucker) secara otomatis.
============================================================================
"""

import os
import math
import logging
from typing import List, Tuple, Dict

import ezdxf
from ezdxf.filemanagement import readfile
from ezdxf.lldxf.const import DXFError

# Perbaikan Pylance: Impor langsung dari submodul internal entitas
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline

from src.use_cases.calibrate_cad import CadParserPort

logger = logging.getLogger("sipas-be")


# ─── MATH HELPERS: ALGORITMA RAMER-DOUGLAS-PEUCKER (RDP) ─────────────────────

def distance_point_to_line(
    point: Tuple[float, float], 
    line_start: Tuple[float, float], 
    line_end: Tuple[float, float]
) -> float:
    """
    Menghitung jarak tegak lurus antara sebuah titik dengan sebuah garis segment.
    Mencegah pembagian dengan nol jika titik start dan end bertumpukan.
    """
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
    denominator = math.sqrt((y2 - y1)**2 + (x2 - x1)**2)
    
    if denominator == 0:
        return math.sqrt((x0 - x1)**2 + (y0 - y1)**2)
        
    return numerator / denominator


def rdp_simplify(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    """
    Implementasi rekursif murni algoritma Ramer-Douglas-Peucker untuk
    menyederhanakan jalur koordinat linear dengan membuang vertex redundant.
    """
    if len(points) < 3:
        return points

    max_dist = 0.0
    index = 0
    end = len(points) - 1
    
    # Cari titik dengan jarak penyimpangan tegak lurus terjauh
    for i in range(1, end):
        dist = distance_point_to_line(points[i], points[0], points[end])
        if dist > max_dist:
            index = i
            max_dist = dist

    # Jika penyimpangan melebihi toleransi (epsilon), pecah rekursif di titik terjauh
    if max_dist > epsilon:
        results_1 = rdp_simplify(points[:index+1], epsilon)
        results_2 = rdp_simplify(points[index:], epsilon)
        return results_1[:-1] + results_2
    else:
        return [points[0], points[end]]


def simplify_polygon(vertices: List[Tuple[float, float]], epsilon: float = 0.1) -> List[Tuple[float, float]]:
    """
    Menjalankan simplifikasi spasial pada poligon tertutup secara aman.
    Menghindari degradasi geometri di bawah batas minimum kelaikan PostGIS (3 vertex unik).
    """
    if len(vertices) < 4:
        return vertices

    # Periksa apakah poligon tertutup (titik awal = titik akhir)
    is_closed = vertices[0] == vertices[-1]
    
    # Untuk poligon tertutup, simplifikasi dikerjakan sebagai garis terbuka sementara
    working_set = vertices[:-1] if is_closed else vertices
    simplified = rdp_simplify(working_set, epsilon)
    
    if is_closed:
        simplified.append(simplified[0])

    # Syarat mutlak poligon PostGIS: minimal memiliki 4 koordinat (3 titik unik + 1 penutup)
    # Jika hasil simplifikasi terlalu agresif, kembalikan data asli demi integritas database
    if len(simplified) < 4:
        return vertices
        
    return simplified


# ─── UTAMA: CAD PARSER IMPLEMENTATION ────────────────────────────────────────

class CadParser(CadParserPort):
    def __init__(self):
        # Daftar layer standar daerah Kabupaten Bogor yang diizinkan untuk diekstrak [sipas-be.txt]
        self.allowed_layers = {
            "PTSP_KDB",      # Koefisien Dasar Bangunan
            "PTSP_KDH",      # Koefisien Dasar Hijau
            "PTSP_KTB",      # Koefisien Tapak Basement
            "PTSP_PSU_JALAN",# Jaringan Jalan Internal
            "PTSP_PSU_MAKAM" # Lahan Pemakaman 2%
        }

    def parse_and_extract_layers(
        self, 
        file_path: str, 
        epsilon: float = 0.1
    ) -> Dict[str, List[List[Tuple[float, float]]]]:
        """
        Membaca file gambar kerja (DXF/DWG) dan mengekstrak koordinat lokal (x, y)
        per layer standar daerah yang teridentifikasi, dilengkapi kompresi RDP [sipas-be.txt].
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"[CAD_PARSER_ERROR] Berkas CAD tidak ditemukan di jalur: {file_path}")

        logger.info(f"[CAD_PARSER] Memulai ekstraksi berkas spasial dengan simplifikasi RDP (epsilon={epsilon}): {file_path}")
        extracted_data: Dict[str, List[List[Tuple[float, float]]]] = {layer: [] for layer in self.allowed_layers}

        try:
            # 1. Load dokumen CAD menggunakan ezdxf.readfile
            doc = readfile(file_path)
            model_space = doc.modelspace()

            # 2. Iterasi seluruh entitas Lightweight Polyline (LWPOLYLINE) di Model Space [sipas-be.txt]
            for entity in model_space.query('LWPOLYLINE'):
                layer_name = entity.dxf.layer.upper()

                # Saring hanya layer yang disepakati untuk diaudit tata ruang [sipas-be.txt]
                if layer_name in self.allowed_layers:
                    if isinstance(entity, LWPolyline):
                        vertices: List[Tuple[float, float]] = []
                        for vertex in entity.get_points(format='xy'):
                            vertices.append((float(vertex[0]), float(vertex[1])) if vertex else (0.0, 0.0))

                        if len(vertices) >= 3:
                            # Terapkan kompresi geometri RDP secara aman
                            simplified_vertices = simplify_polygon(vertices, epsilon)
                            extracted_data[layer_name].append(simplified_vertices)

            # 3. Iterasi entitas 2D/3D Polyline konvensional (POLYLINE) [sipas-be.txt]
            for entity in model_space.query('POLYLINE'):
                layer_name = entity.dxf.layer.upper()
                if layer_name in self.allowed_layers:
                    if isinstance(entity, Polyline):
                        vertices: List[Tuple[float, float]] = []
                        for vertex in entity.vertices:
                            pos = vertex.dxf.location
                            if pos:
                                vertices.append((float(pos.x), float(pos.y)))

                        if len(vertices) >= 3:
                            # Terapkan kompresi geometri RDP secara aman
                            simplified_vertices = simplify_polygon(vertices, epsilon)
                            extracted_data[layer_name].append(simplified_vertices)

            # 4. Rekam hasil kompresi dan statistik data ke log audit
            for layer, polygons in extracted_data.items():
                if len(polygons) > 0:
                    logger.info(f"[CAD_PARSER] Layer '{layer}': Berhasil memuat & menyederhanakan {len(polygons)} poligon spasial.")

            return extracted_data

        except DXFError as e:
            logger.error(f"[CAD_PARSER_ERROR] Struktur berkas DXF rusak atau tidak valid: {str(e)}")
            raise ValueError(f"Struktur berkas CAD tidak valid atau rusak secara spasial: {str(e)}")
        except Exception as e:
            logger.error(f"[CAD_PARSER_CRASH] Kegagalan fatal saat membaca berkas CAD: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses berkas CAD di server: {str(e)}")