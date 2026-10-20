"""
============================================================================
SIPAS MOCK — Generator Gambar Kerja CAD Site Plan [create_mock_cad.py]
============================================================================
Menghasilkan berkas DXF site plan (layer standar PTSP) di atas batas lahan
yang SAMA PERSIS dengan create_mock_shp.py (lihat mock_site_config.py).

Koordinat DXF = UTM 48S dikurangi origin lokal (meter, tanpa rotasi), jadi
setelah kalibrasi Helmert 2D di backend, CAD akan menumpuk tepat di atas SHP.
Titik ikat siap pakai ditulis ke ../mock_siteplan_control_points.json.

Jalankan dari folder sipas-be:  poetry run python create_mock_cad.py
Output ditulis ke folder root SIPAS (../).
============================================================================
"""

import json
import sys
from typing import Dict, List

import ezdxf
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from mock_site_config import (
    CAD_ORIGIN_UTM,
    SITE_NAME,
    get_control_points,
    get_site_polygon_utm,
    split_polygon_vertically,
    utm_to_local_geom,
)

# ─── PARAMETER DESAIN TAPAK (meter) ──────────────────────────────────────────
SETBACK_BOUNDARY = 3.0   # Sempadan dari batas terluar lahan
MAIN_ROAD_WIDTH = 8.0    # Jalan utama (E-W) & jalan spine (N-S)
LANE_WIDTH = 6.0         # Jalan lingkungan
FRONT_SETBACK = 1.0      # GSB kaveling terhadap jalan
LOT_WIDTH = 8.0          # Lebar muka kaveling
LOT_MAX_DEPTH = 12.0     # Kedalaman kaveling maksimum
LOT_GAP = 1.0            # Jarak antar kaveling
MIN_LOT_DEPTH = 6.0

LAYERS = [
    ("PTSP_KDB", 1),          # Merah   - kaveling bangunan
    ("PTSP_KDH", 3),          # Hijau   - RTH / taman
    ("PTSP_PSU_JALAN", 5),    # Biru    - jaringan jalan
    ("PTSP_PSU_MAKAM", 2),    # Kuning  - pemakaman
    ("PTSP_BATAS_LAHAN", 7),  # Putih   - batas terluar bidang tanah
]


def _largest_polygon(geom):
    if geom.is_empty:
        return None
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        polys = [g for g in geom.geoms if g.geom_type == "Polygon"]
        return max(polys, key=lambda p: p.area) if polys else None
    return None


def build_siteplan_layout(boundary: Polygon) -> Dict[str, List[Polygon]]:
    """
    Menyusun tata letak site plan rapi (grid jalan + kaveling persegi)
    yang menyesuaikan bentuk batas lahan secara otomatis.
    """
    minx, miny, maxx, maxy = boundary.bounds
    width, height = maxx - minx, maxy - miny
    cx = (minx + maxx) / 2
    inner = boundary.buffer(-SETBACK_BOUNDARY, join_style=2)

    # 1. Jaringan jalan: 1 jalan utama E-W, 1 spine N-S, 2 jalan lingkungan E-W
    y_main = miny + height * 0.50
    y_lane_s = miny + height * 0.25
    y_lane_n = miny + height * 0.75
    pad = 10.0

    def road(line_coords, w):
        return LineString(line_coords).buffer(w / 2, cap_style=2).intersection(boundary)

    roads = [
        road([(minx - pad, y_main), (maxx + pad, y_main)], MAIN_ROAD_WIDTH),
        road([(cx, miny - pad), (cx, maxy + pad)], MAIN_ROAD_WIDTH),
        road([(minx - pad, y_lane_s), (maxx + pad, y_lane_s)], LANE_WIDTH),
        road([(minx - pad, y_lane_n), (maxx + pad, y_lane_n)], LANE_WIDTH),
    ]
    road_union = unary_union(roads)

    # 2. RTH (KDH) di blok barat laut & makam di blok tenggara
    park_box = box(minx, y_lane_n + LANE_WIDTH / 2, minx + width * 0.28, maxy)
    park = _largest_polygon(park_box.intersection(boundary).difference(road_union))

    cemetery_box = box(maxx - width * 0.20, miny, maxx, y_lane_s - LANE_WIDTH / 2)
    cemetery = _largest_polygon(cemetery_box.intersection(boundary).difference(road_union))

    reserved = unary_union([g for g in (park, cemetery) if g is not None]).buffer(1.0)
    # Dikurangi sedikit (0.05 m) agar kaveling yang tepat menyentuh garis GSB tidak ikut ditolak
    road_clear = road_union.buffer(FRONT_SETBACK - 0.05)

    # 3. Kaveling: dua baris saling membelakangi di setiap strip antar jalan
    strip_edges = [
        (miny, y_lane_s - LANE_WIDTH / 2),
        (y_lane_s + LANE_WIDTH / 2, y_main - MAIN_ROAD_WIDTH / 2),
        (y_main + MAIN_ROAD_WIDTH / 2, y_lane_n - LANE_WIDTH / 2),
        (y_lane_n + LANE_WIDTH / 2, maxy),
    ]
    sides = [
        (cx - MAIN_ROAD_WIDTH / 2 - FRONT_SETBACK, -1),  # sisi barat, berjalan ke barat
        (cx + MAIN_ROAD_WIDTH / 2 + FRONT_SETBACK, +1),  # sisi timur, berjalan ke timur
    ]

    lots: List[Polygon] = []
    for y_lo, y_hi in strip_edges:
        usable = (y_hi - y_lo) - 2 * FRONT_SETBACK
        depth = min(LOT_MAX_DEPTH, (usable - LOT_GAP) / 2)
        if depth < MIN_LOT_DEPTH:
            rows = [(y_lo + FRONT_SETBACK, y_lo + FRONT_SETBACK + min(LOT_MAX_DEPTH, usable))]
        else:
            rows = [
                (y_lo + FRONT_SETBACK, y_lo + FRONT_SETBACK + depth),
                (y_hi - FRONT_SETBACK - depth, y_hi - FRONT_SETBACK),
            ]

        for r_lo, r_hi in rows:
            for x_start, direction in sides:
                x = x_start
                while minx - LOT_WIDTH <= x <= maxx + LOT_WIDTH:
                    x2 = x + direction * LOT_WIDTH
                    lot = box(min(x, x2), r_lo, max(x, x2), r_hi)
                    x = x2 + direction * LOT_GAP

                    if lot.intersects(road_clear) or lot.intersects(reserved):
                        continue
                    # Kaveling di tepi lahan dipotong mengikuti batas (trapesium alami)
                    clipped = _largest_polygon(lot.intersection(inner))
                    if clipped is None or clipped.area < lot.area * 0.6:
                        continue
                    lots.append(clipped.simplify(0.01))

    return {
        "PTSP_BATAS_LAHAN": [boundary],
        "PTSP_PSU_JALAN": [g for g in roads if not g.is_empty],
        "PTSP_KDH": [park] if park is not None else [],
        "PTSP_PSU_MAKAM": [cemetery] if cemetery is not None else [],
        "PTSP_KDB": lots,
    }


def clip_layout(layout: Dict[str, List[Polygon]], child: Polygon) -> Dict[str, List[Polygon]]:
    """Memotong layout induk ke batas lahan anak (simulasi pemecahan / split)."""
    clipped: Dict[str, List[Polygon]] = {"PTSP_BATAS_LAHAN": [child]}
    for layer, geoms in layout.items():
        if layer == "PTSP_BATAS_LAHAN":
            continue
        out = []
        for g in geoms:
            if layer == "PTSP_KDB":
                # Kaveling tidak boleh terbelah: ikut lahan anak bila titik tengahnya di dalam
                if child.contains(g.representative_point()):
                    out.append(g)
            else:
                part = _largest_polygon(g.intersection(child))
                if part is not None and part.area > 1.0:
                    out.append(part)
        clipped[layer] = out
    return clipped


def add_geometry_to_dxf(msp, geom, layer):
    """Menulis geometri Shapely sebagai LWPOLYLINE tertutup di DXF."""
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        msp.add_lwpolyline(list(geom.exterior.coords)[:-1], close=True, dxfattribs={"layer": layer})
        for interior in geom.interiors:
            msp.add_lwpolyline(list(interior.coords)[:-1], close=True, dxfattribs={"layer": layer})
    elif geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        for part in geom.geoms:
            add_geometry_to_dxf(msp, part, layer)


def save_dxf_siteplan(output_path: str, layout: Dict[str, List[Polygon]]):
    """Membuat dokumen DXF R2018 dengan layer standar PTSP."""
    doc = ezdxf.new("R2018")
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for name, color in LAYERS:
        doc.layers.add(name, color=color)

    for layer, geoms in layout.items():
        for g in geoms:
            add_geometry_to_dxf(msp, g, layer)

    doc.saveas(output_path)
    n_lots = len(layout.get("PTSP_KDB", []))
    area = layout["PTSP_BATAS_LAHAN"][0].area
    print(f"[MOCK_CAD] Sukses menulis DXF ke: {output_path} ({area:,.2f} m², {n_lots} kaveling)")


def main():
    print(f"[MOCK_CAD] Membuat gambar kerja CAD untuk: {SITE_NAME}")
    print(f"[MOCK_CAD] Origin lokal CAD (UTM 48S): E={CAD_ORIGIN_UTM[0]:.0f}, N={CAD_ORIGIN_UTM[1]:.0f}")

    try:
        large_poly = utm_to_local_geom(get_site_polygon_utm())
        small_poly_1, small_poly_2 = split_polygon_vertically(large_poly)

        layout = build_siteplan_layout(large_poly)

        # ─── SEEDER ASLI (BACKWARD COMPATIBILITY) ───
        save_dxf_siteplan("../sample_siteplan.dxf", layout)

        # ─── FITUR SPLIT/MERGE SIMULATION ───
        print("\n[MOCK_CAD] Membuat berkas DXF simulasi Split / Merge:")
        save_dxf_siteplan("../mock_large_siteplan.dxf", layout)
        save_dxf_siteplan("../mock_small_siteplan_1.dxf", clip_layout(layout, small_poly_1))
        save_dxf_siteplan("../mock_small_siteplan_2.dxf", clip_layout(layout, small_poly_2))

        # ─── TITIK IKAT HELMERT SIAP PAKAI ───
        control_points = {
            "sample_siteplan.dxf": get_control_points(large_poly),
            "mock_large_siteplan.dxf": get_control_points(large_poly),
            "mock_small_siteplan_1.dxf": get_control_points(small_poly_1),
            "mock_small_siteplan_2.dxf": get_control_points(small_poly_2),
        }
        with open("../mock_siteplan_control_points.json", "w", encoding="utf-8") as f:
            json.dump(control_points, f, indent=2)
        print("\n[MOCK_CAD] Titik ikat Helmert ditulis ke: ../mock_siteplan_control_points.json")
        print(json.dumps(control_points["mock_large_siteplan.dxf"], indent=2))

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Gagal memproduksi berkas CAD: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()