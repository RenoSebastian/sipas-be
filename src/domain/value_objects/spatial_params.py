"""
============================================================================
SIPAS DOMAIN VALUE OBJECTS — Spatial Parameters [spatial_params.py]
============================================================================
Peran: Menyimpan objek nilai geospasial imutabel (Value Objects) seperti
       koordinat titik, matriks transformasi Helmert 2D [Jakarta 5], 
       serta rumus kalkulator kepatuhan teknis (KDB, GSB, Jarak Bebas)
       sesuai Buku 2 Pedoman Teknis [Buku 2, 15, 22].
============================================================================
"""

from dataclasses import dataclass
import math
from enum import Enum
from typing import Tuple
from pyproj import Transformer

# Proyeksi WGS84 (EPSG:4326) <-> UTM Zone 48S (EPSG:32748) Kabupaten Bogor [Planar UTM]
wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32748", always_xy=True)
utm_to_wgs84 = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)

class WallType(str, Enum):
    TRANSPARENT = 'TRANSPARENT' # Dinding terbuka/transparan (Buku 2 Hal 23)
    MASSIVE = 'MASSIVE'         # Dinding tertutup/masif (Buku 2 Hal 23)

# ─── VALUE OBJECT 1: KOORDINAT TITIK GEOGRAFIS ──────────────────────────────────
@dataclass(frozen=True)
class Coordinate:
    longitude: float # Sumbu X bumi
    latitude: float  # Sumbu Y bumi

    def __post_init__(self):
        """Memvalidasi batas rentang koordinat bumi nyata (WGS 84)."""
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"Ilegal: Nilai Longitude ({self.longitude}) harus berada di antara -180 s/d 180 derajat.")
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"Ilegal: Nilai Latitude ({self.latitude}) harus berada di antara -90 s/d 90 derajat.")


# ─── VALUE OBJECT 2: PARAMETER MATRIKS TRANSFORMASI HELMERT 2D [Jakarta 5] ──────
@dataclass(frozen=True)
class HelmertParameters:
    A: float            # s * cos(theta)
    B: float            # s * sin(theta)
    Tx: float           # Pergeseran sumbu X (Translasi X)
    Ty: float           # Pergeseran sumbu Y (Translasi Y)
    scale: float        # Skala seragam (s)
    rotation_rad: float # Sudut rotasi dalam satuan radian (theta)

    def transform(self, local_x: float, local_y: float) -> Coordinate:
        """
        Mentransformasikan titik koordinat lokal CAD (x, y) menjadi
        koordinat spasial bumi nyata (X, Y / Lng, Lat) secara planar-ke-geodetis [Jakarta 5].
        """
        X_planar = self.A * local_x - self.B * local_y + self.Tx
        Y_planar = self.B * local_x + self.A * local_y + self.Ty
        # Proyeksikan kembali dari UTM 48S (planar meter) ke WGS84 (geografis derajat)
        lng, lat = utm_to_wgs84.transform(X_planar, Y_planar)
        return Coordinate(longitude=lng, latitude=lat)


def solveHelmert2D(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    P1: Tuple[float, float],
    P2: Tuple[float, float]
) -> dict:
    """
    Menghitung parameter Helmert 2D Conformal berdasarkan dua pasang titik ikat
    yang terlebih dahulu diproyeksikan ke sistem UTM Zone 48S planar meter [Jakarta 5].
    """
    # Proyeksikan titik referensi geodetik (WGS84) ke planar meter (UTM Zone 48S)
    P1_planar = wgs84_to_utm.transform(P1[0], P1[1])
    P2_planar = wgs84_to_utm.transform(P2[0], P2[1])

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dX = P2_planar[0] - P1_planar[0]
    dY = P2_planar[1] - P1_planar[1]

    denom = dx * dx + dy * dy
    if denom == 0:
        raise ValueError("Jarak antar titik kontrol CAD tidak boleh nol.")

    # Menghitung parameter gabungan skala dan rotasi
    A = (dX * dx + dY * dy) / denom
    B = (dY * dx - dX * dy) / denom

    # Menghitung parameter translasi (pergeseran koordinat planar)
    Tx = P1_planar[0] - A * p1[0] + B * p1[1]
    Ty = P1_planar[1] - B * p1[0] - A * p1[1]

    # Ekstraksi nilai skala fisik & sudut rotasi (radian)
    scale = math.sqrt(A * A + B * B)
    rotation = math.atan2(B, A)

    return {
        "A": A,
        "B": B,
        "Tx": Tx,
        "Ty": Ty,
        "scale": scale,
        "rotation": rotation
    }



# ─── VALUE OBJECT 3: ATURAN BAKU AMBANG BATAS INTENSITAS BANGUNAN [Buku 2, 15] ──
@dataclass(frozen=True)
class SitePlanBylaws:
    max_kdb_percent: float = 60.0 # Koefisien Dasar Bangunan Maksimal [Buku 2, 15]
    max_klb: float = 3.5          # Koefisien Lantai Bangunan Maksimal [Buku 2, 15]
    min_kdh_percent: float = 10.0 # Koefisien Dasar Hijau Minimal [Buku 2, 15]
    max_ktb_percent: float = 75.0 # Koefisien Tapak Basement Maksimal [Buku 2, 15]

    def validate_kdb(self, calculated_kdb_percent: float) -> bool:
        """Memverifikasi kepatuhan persentase KDB hasil kalkulasi CAD [Buku 2, 15]."""
        return calculated_kdb_percent <= self.max_kdb_percent

    def validate_klb(self, calculated_klb: float) -> bool:
        """Memverifikasi kepatuhan nilai KLB hasil kalkulasi CAD [Buku 2, 15]."""
        return calculated_klb <= self.max_klb

    def validate_kdh(self, calculated_kdh_percent: float) -> bool:
        """Memverifikasi kepatuhan persentase KDH hasil kalkulasi CAD [Buku 2, 15]."""
        return calculated_kdh_percent >= self.min_kdh_percent

    def validate_ktb(self, calculated_ktb_percent: float) -> bool:
        """Memverifikasi kepatuhan persentase KTB hasil kalkulasi CAD [Buku 2, 15]."""
        return calculated_ktb_percent <= self.max_ktb_percent


# ─── VALUE OBJECT 4: KALKULATOR GARIS SEMPADAN BANGUNAN (GSB) [Buku 2, 22] ─────
@dataclass(frozen=True)
class GsbCalculator:
    @staticmethod
    def get_minimum_gsb(road_width_m: float) -> float:
        """
        Menghitung batas minimum GSB berdasarkan lebar rencana jalan utama
        menggunakan regulasi DKI Jakarta Buku 2 Hal 22 [Buku 2, 22].
        """
        if road_width_m <= 0:
            raise ValueError("Lebar rencana jalan harus bernilai positif.")

        if road_width_m <= 12.0:
            # Jalan <= 12m, GSB sebesar setengah kali lebar rencana jalan [Buku 2, 22]
            return road_width_m * 0.5
        elif road_width_m <= 26.0:
            # Jalan > 12m s/d <= 26m, GSB sebesar 8 meter [Buku 2, 22]
            return 8.0
        else:
            # Jalan > 26m, GSB sebesar 10 meter [Buku 2, 22]
            return 10.0


# ─── VALUE OBJECT 5: KALKULATOR JARAK BEBAS ANTAR-BANGUNAN [Buku 2, 23-25] ─────
@dataclass(frozen=True)
class JarakBebasCalculator:
    @staticmethod
    def get_minimum_distance(
        wall_type_a: WallType, 
        wall_type_b: WallType, 
        height_a_m: float, 
        height_b_m: float
    ) -> float:
        """
        Menghitung jarak bebas minimum antar-bangunan berdasarkan tipe dinding
        dan ketinggian masing-masing bangunan sesuai Buku 2 Hal 23 s/d 25 [Buku 2, 23, 24, 25].
        """
        if height_a_m <= 0 or height_b_m <= 0:
            raise ValueError("Ketinggian bangunan wajib bernilai positif.")

        # Ya = Tinggi Bangunan A, Yb = Tinggi Bangunan B
        # Kasus 1: Kedua dinding terbuka/transparan -> Jarak = Ya + Yb [Buku 2, 24]
        if wall_type_a == WallType.TRANSPARENT and wall_type_b == WallType.TRANSPARENT:
            return height_a_m + height_b_m

        # Kasus 2: Salah satu dinding masif dan satu transparan -> Jarak = 0.5 Ya + Yb [Buku 2, 25]
        elif wall_type_a == WallType.TRANSPARENT and wall_type_b == WallType.MASSIVE:
            return (0.5 * height_a_m) + height_b_m
        elif wall_type_a == WallType.MASSIVE and wall_type_b == WallType.TRANSPARENT:
            return (0.5 * height_b_m) + height_a_m

        # Kasus 3: Kedua dinding masif -> Jarak = 0.5 Ya + 0.5 Yb [Buku 2, 25]
        else:
            return (0.5 * height_a_m) + (0.5 * height_b_m)