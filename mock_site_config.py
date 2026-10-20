"""
============================================================================
SIPAS MOCK — Konfigurasi Lokasi Tapak Bersama [mock_site_config.py]
============================================================================
Peran: Satu sumber kebenaran (single source of truth) koordinat lokasi uji
       untuk create_mock_cad.py dan create_mock_shp.py.

Strategi agar CAD selalu tepat berada di atas SHP:
  1. Titik sudut lahan (DMS, WGS84) dikonversi ke UTM Zone 48S (EPSG:32748),
     sistem planar yang SAMA dengan yang dipakai solveHelmert2D di backend.
  2. SHP  = poligon UTM -> diproyeksikan balik ke WGS84.
  3. CAD  = poligon UTM -> digeser ke origin lokal (tanpa rotasi, skala 1:1 meter).
  Karena CAD hanyalah translasi murni dari UTM, transformasi Helmert dengan
  dua titik ikat mana pun akan memetakan CAD kembali TEPAT ke poligon SHP.
============================================================================
"""

import math
import re
from typing import Dict, List, Tuple

from pyproj import Transformer
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import transform

# ─── KOORDINAT SUDUT LAHAN (Urutan searah jarum jam: BL -> TL -> TG -> BD) ──────
SITE_ID = "sub-1"
SITE_NAME = "Siteplan Uji Kabupaten Bogor"
SITE_CORNERS_DMS: List[Tuple[str, str]] = [
    ('6°34\'18.12"S', '106°42\'00.81"E'),  # Barat Laut
    ('6°34\'18.22"S', '106°42\'04.84"E'),  # Timur Laut
    ('6°34\'22.08"S', '106°42\'04.76"E'),  # Tenggara
    ('6°34\'22.08"S', '106°42\'00.62"E'),  # Barat Daya
]

# Proyeksi yang identik dengan src/domain/value_objects/spatial_params.py
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32748", always_xy=True)
_utm_to_wgs84 = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)

_DMS_PATTERN = re.compile(r"^\s*(\d+)\s*°\s*(\d+)\s*'\s*([\d.]+)\s*\"\s*([NSEW])\s*$", re.IGNORECASE)


def dms_to_decimal(dms: str) -> float:
    """Mengubah string DMS (mis. 6°34'18.12"S) menjadi derajat desimal bertanda."""
    match = _DMS_PATTERN.match(dms)
    if not match:
        raise ValueError(f"Format DMS tidak dikenali: {dms}")
    deg, minutes, seconds, hemi = match.groups()
    value = int(deg) + int(minutes) / 60.0 + float(seconds) / 3600.0
    return -value if hemi.upper() in ("S", "W") else value


def get_site_corners_wgs84() -> List[Tuple[float, float]]:
    """Daftar sudut lahan dalam (lon, lat) WGS84."""
    return [(dms_to_decimal(lon), dms_to_decimal(lat)) for lat, lon in SITE_CORNERS_DMS]


def wgs84_to_utm_geom(geom):
    return transform(lambda x, y, z=None: _wgs84_to_utm.transform(x, y), geom)


def utm_to_wgs84_geom(geom):
    return transform(lambda x, y, z=None: _utm_to_wgs84.transform(x, y), geom)


def get_site_polygon_utm() -> Polygon:
    """Poligon batas lahan dalam meter UTM 48S (searah jarum jam / standar ESRI)."""
    poly_wgs = Polygon(get_site_corners_wgs84())
    return orient(wgs84_to_utm_geom(poly_wgs), sign=-1.0)


# Origin lokal CAD = pojok kiri-bawah bounding box UTM (dibulatkan ke bawah per meter)
_site_utm = get_site_polygon_utm()
CAD_ORIGIN_UTM: Tuple[float, float] = (
    float(math.floor(_site_utm.bounds[0])),
    float(math.floor(_site_utm.bounds[1])),
)


def utm_to_local_geom(geom):
    """UTM 48S -> koordinat lokal CAD (meter, translasi murni)."""
    ox, oy = CAD_ORIGIN_UTM
    return transform(lambda x, y, z=None: (x - ox, y - oy), geom)


def local_to_utm_geom(geom):
    """Koordinat lokal CAD (meter) -> UTM 48S."""
    ox, oy = CAD_ORIGIN_UTM
    return transform(lambda x, y, z=None: (x + ox, y + oy), geom)


def local_to_wgs84_geom(geom):
    return utm_to_wgs84_geom(local_to_utm_geom(geom))


def split_polygon_vertically(poly: Polygon) -> Tuple[Polygon, Polygon]:
    """Membagi poligon menjadi 2 bagian (barat & timur) di tengah bounding box."""
    minx, miny, maxx, maxy = poly.bounds
    center_x = (minx + maxx) / 2
    left_poly = poly.intersection(box(minx, miny, center_x, maxy))
    right_poly = poly.intersection(box(center_x, miny, maxx, maxy))

    if left_poly.geom_type == "MultiPolygon":
        left_poly = max(left_poly.geoms, key=lambda p: p.area)
    if right_poly.geom_type == "MultiPolygon":
        right_poly = max(right_poly.geoms, key=lambda p: p.area)

    return orient(left_poly, sign=-1.0), orient(right_poly, sign=-1.0)


def get_control_points(boundary_local: Polygon) -> Dict[str, List[float]]:
    """
    Titik ikat Helmert (sudut Barat Laut & Tenggara) untuk wizard / endpoint kalibrasi.
    Formatnya identik dengan CalibrateCadInputDto: anchor_cad_* = [x, y], anchor_map_* = [lng, lat].
    """
    coords = list(boundary_local.exterior.coords)[:-1]
    nw = min(coords, key=lambda c: c[0] - c[1])   # x kecil, y besar
    se = max(coords, key=lambda c: c[0] - c[1])   # x besar, y kecil

    ox, oy = CAD_ORIGIN_UTM
    nw_lng, nw_lat = _utm_to_wgs84.transform(nw[0] + ox, nw[1] + oy)
    se_lng, se_lat = _utm_to_wgs84.transform(se[0] + ox, se[1] + oy)

    return {
        "anchor_cad_1": [round(nw[0], 4), round(nw[1], 4)],
        "anchor_cad_2": [round(se[0], 4), round(se[1], 4)],
        "anchor_map_1": [round(nw_lng, 9), round(nw_lat, 9)],
        "anchor_map_2": [round(se_lng, 9), round(se_lat, 9)],
    }
