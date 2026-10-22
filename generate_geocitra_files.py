"""
============================================================================
SIPAS MOCK GENERATOR — Berkas SHP & CAD PKKPR PT Geocitra Pembangunan Mandiri
============================================================================
Menghasilkan berkas nyata untuk simulasi pengajuan Site Plan baru:
1. BPN_PKKPR_PT_Geocitra_Pembangunan_Mandiri.geojson (Full PKKPR 6.663 m²)
2. BPN_PKKPR_PT_Geocitra_Pembangunan_Mandiri.zip (Shapefile Full PKKPR)
3. BPN_Siteplan_Tahap1_Geocitra.geojson (Batas Site Plan Tahap 1 ~3.250 m²)
4. BPN_Siteplan_Tahap1_Geocitra.zip (Shapefile Site Plan Tahap 1)
5. CAD_Siteplan_Tahap1_Geocitra.dxf (Gambar Kerja CAD dengan layer PTSP)
6. CAD_Siteplan_Geocitra_Full.dxf (Gambar Kerja CAD Full Lahan)
============================================================================
"""

import os
import sys
import json
import math
import shutil
import zipfile
from typing import List, Tuple, Dict

import shapefile
from pyproj import Transformer
from shapely.geometry import Polygon, LineString, box, mapping
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union
import ezdxf

# Proyeksi WGS84 <-> UTM Zone 48S (Kabupaten Bogor)
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32748", always_xy=True)
_utm_to_wgs84 = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

# Koordinat Asli SK PKKPR-202610-0004 (PT Geocitra Pembangunan Mandiri)
GEOCITRA_PKKPR_COORDS_WGS84 = [
    [106.84015274, -6.59187357],
    [106.840254664, -6.590865792],
    [106.840834022, -6.591073746],
    [106.840769649, -6.591388344],
    [106.840726733, -6.591932224],
    [106.84015274, -6.59187357]
]

SK_NUMBER = "503/PKKPR/DPMPTSP/2026/001"
APPLICANT_NAME = "PT Geocitra Pembangunan Mandiri"
HOUSING_NAME = "Perumahan Geocitra Green Residence"


def get_pkkpr_polygon_utm() -> Polygon:
    poly_wgs = Polygon(GEOCITRA_PKKPR_COORDS_WGS84)
    utm_coords = [_wgs84_to_utm.transform(x, y) for x, y in poly_wgs.exterior.coords]
    return orient(Polygon(utm_coords), sign=-1.0)


def split_polygon_horizontal(poly: Polygon) -> Tuple[Polygon, Polygon]:
    """Membagi poligon secara horizontal (bagian utara dan bagian selatan)."""
    minx, miny, maxx, maxy = poly.bounds
    center_y = (miny + maxy) / 2
    south_poly = poly.intersection(box(minx, miny, maxx, center_y))
    north_poly = poly.intersection(box(minx, center_y, maxx, maxy))

    if south_poly.geom_type == "MultiPolygon":
        south_poly = max(south_poly.geoms, key=lambda p: p.area)
    if north_poly.geom_type == "MultiPolygon":
        north_poly = max(north_poly.geoms, key=lambda p: p.area)

    return orient(south_poly, sign=-1.0), orient(north_poly, sign=-1.0)


def save_shp_zip(zip_path: str, utm_poly: Polygon, sub_id: str, name: str, sk_no: str):
    """Menyimpan poligon ke file ESRI Shapefile WGS84 (.zip)."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    temp_dir = os.path.join(os.path.dirname(zip_path), f"temp_shp_{sub_id}")
    os.makedirs(temp_dir, exist_ok=True)
    try:
        wgs_coords = [_utm_to_wgs84.transform(x, y) for x, y in utm_poly.exterior.coords]
        wgs84_poly = Polygon(wgs_coords)
        shp_base = os.path.join(temp_dir, "batas_lahan_bpn")

        w = shapefile.Writer(shp_base, shapeType=shapefile.POLYGON)
        w.field("id", "C", 50)
        w.field("name", "C", 100)
        w.field("pemohon", "C", 100)
        w.field("no_sk", "C", 80)
        w.field("luas_m2", "N", decimal=2)

        w.poly([[list(pt) for pt in wgs84_poly.exterior.coords]])
        w.record(sub_id, name, APPLICANT_NAME, sk_no, round(utm_poly.area, 2))
        w.close()

        with open(shp_base + ".prj", "w") as prjf:
            prjf.write(PRJ_WGS84)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                fn = f"batas_lahan_bpn{ext}"
                zipf.write(os.path.join(temp_dir, fn), arcname=fn)
        print(f"[OK] SHP Zip tersimpan: {zip_path} ({utm_poly.area:,.1f} m²)")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def save_geojson(geojson_path: str, utm_poly: Polygon, sub_id: str, name: str, sk_no: str):
    """Menyimpan GeoJSON standar RFC 7946 (EPSG:4326)."""
    os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
    wgs_coords = [_utm_to_wgs84.transform(x, y) for x, y in utm_poly.exterior.coords]
    wgs84_poly = Polygon(wgs_coords)
    fc = {
        "type": "FeatureCollection",
        "name": name,
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": [{
            "type": "Feature",
            "properties": {
                "id": sub_id,
                "nama_bidang": name,
                "pemohon": APPLICANT_NAME,
                "sk_pkkpr": sk_no,
                "luas_m2": round(utm_poly.area, 2),
                "kabupaten": "Kabupaten Bogor",
                "kecamatan": "Sukaraja",
                "desa": "Cijujung"
            },
            "geometry": mapping(wgs84_poly)
        }]
    }
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2)
    print(f"[OK] GeoJSON tersimpan: {geojson_path}")


def build_cad_layout(boundary_utm: Polygon, origin_utm: Tuple[float, float]) -> Dict[str, List[Polygon]]:
    """
    Menyusun tata letak site plan kaveling dan jalan di koordinat lokal CAD (origin 0,0).
    """
    ox, oy = origin_utm
    boundary_local = transform(lambda x, y, z=None: (x - ox, y - oy), boundary_utm)
    minx, miny, maxx, maxy = boundary_local.bounds
    width, height = maxx - minx, maxy - miny
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2

    # Jalan Utama & Jalan Lingkungan
    road_width = 7.0
    roads = [
        LineString([(minx - 5, cy), (maxx + 5, cy)]).buffer(road_width / 2, cap_style=2).intersection(boundary_local),
        LineString([(cx, miny - 5), (cx, maxy + 5)]).buffer(road_width / 2, cap_style=2).intersection(boundary_local),
    ]
    road_union = unary_union([r for r in roads if not r.is_empty])

    # RTH / Taman
    park_box = box(minx + 2, maxy - 18, minx + 22, maxy - 2)
    park = park_box.intersection(boundary_local).difference(road_union)

    # Fasos / Fasum
    fasos_box = box(maxx - 20, miny + 2, maxx - 2, miny + 16)
    fasos = fasos_box.intersection(boundary_local).difference(road_union)

    # Kaveling Perumahan (KDB)
    lots: List[Polygon] = []
    lot_w, lot_h = 7.0, 12.0
    for y in [miny + 3, cy - lot_h - 2, cy + 5, maxy - lot_h - 2]:
        for x in [minx + 3, minx + 11, cx - lot_w - 2, cx + 4, maxx - lot_w - 11, maxx - lot_w - 3]:
            if x + lot_w <= maxx and y + lot_h <= maxy:
                lot = box(x, y, x + lot_w, y + lot_h)
                if not lot.intersects(road_union) and not lot.intersects(park) and not lot.intersects(fasos):
                    clipped = lot.intersection(boundary_local.buffer(-1.5))
                    if not clipped.is_empty and clipped.area > 30.0:
                        lots.append(clipped)

    return {
        "PTSP_BATAS_LAHAN": [boundary_local],
        "PTSP_PSU_JALAN": [road_union] if not road_union.is_empty else [],
        "PTSP_KDH": [park] if not park.is_empty else [],
        "PTSP_PSU_MAKAM": [fasos] if not fasos.is_empty else [],
        "PTSP_KDB": lots,
    }


def save_dxf(dxf_path: str, layout: Dict[str, List[Polygon]]):
    """Menyimpan layout gambar kerja CAD dalam format DXF AutoCAD."""
    os.makedirs(os.path.dirname(dxf_path), exist_ok=True)
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    layer_colors = {
        "PTSP_BATAS_LAHAN": 7,  # Putih
        "PTSP_PSU_JALAN": 5,    # Biru
        "PTSP_KDH": 3,          # Hijau
        "PTSP_PSU_MAKAM": 2,    # Kuning
        "PTSP_KDB": 1,          # Merah
    }

    for lyr_name, color in layer_colors.items():
        doc.layers.add(lyr_name, color=color)

    for lyr_name, geoms in layout.items():
        for geom in geoms:
            if geom.is_empty:
                continue
            if geom.geom_type == "Polygon":
                msp.add_lwpolyline(list(geom.exterior.coords)[:-1], close=True, dxfattribs={"layer": lyr_name})
            elif geom.geom_type == "MultiPolygon":
                for p in geom.geoms:
                    msp.add_lwpolyline(list(p.exterior.coords)[:-1], close=True, dxfattribs={"layer": lyr_name})

    doc.saveas(dxf_path)
    print(f"[OK] CAD DXF tersimpan: {dxf_path}")


def get_helmert_control_points(boundary_utm: Polygon, origin_utm: Tuple[float, float]) -> Dict:
    """Menghitung pasangan titik ikat Helmert 2D (Barat Laut & Tenggara)."""
    ox, oy = origin_utm
    coords = list(boundary_utm.exterior.coords)[:-1]

    # Titik NW (Barat Laut): x kecil, y besar
    nw_utm = min(coords, key=lambda c: (c[0] - ox) - (c[1] - oy))
    # Titik SE (Tenggara): x besar, y kecil
    se_utm = max(coords, key=lambda c: (c[0] - ox) - (c[1] - oy))

    nw_cad = [round(nw_utm[0] - ox, 4), round(nw_utm[1] - oy, 4)]
    se_cad = [round(se_utm[0] - ox, 4), round(se_utm[1] - oy, 4)]

    nw_wgs = _utm_to_wgs84.transform(nw_utm[0], nw_utm[1])
    se_wgs = _utm_to_wgs84.transform(se_utm[0], se_utm[1])

    wgs_polygon = [[round(_utm_to_wgs84.transform(x, y)[0], 8), round(_utm_to_wgs84.transform(x, y)[1], 8)] for x, y in boundary_utm.exterior.coords]

    return {
        "anchor_cad_1": nw_cad,
        "anchor_cad_2": se_cad,
        "anchor_map_1": [round(nw_wgs[0], 8), round(nw_wgs[1], 8)],
        "anchor_map_2": [round(se_wgs[0], 8), round(se_wgs[1], 8)],
        "scale": 1.0,
        "rotation": 0.0,
        "Tx": round(ox, 2),
        "Ty": round(oy, 2),
        "polygon": wgs_polygon
    }


def main():
    print("=" * 70)
    print("SIPAS MOCK BUILDER — Generator Berkas Simulasi PT Geocitra Pembangunan Mandiri")
    print("=" * 70)

    # 1. Geometri Induk PKKPR
    poly_full_utm = get_pkkpr_polygon_utm()
    # 2. Geometri Tahap 1 (Bagian Selatan seluas ~3.250 m²)
    poly_tahap1_utm, poly_tahap2_utm = split_polygon_horizontal(poly_full_utm)

    print(f"Luas Induk PKKPR : {poly_full_utm.area:,.2f} m²")
    print(f"Luas Tahap 1     : {poly_tahap1_utm.area:,.2f} m²")
    print(f"Luas Tahap 2     : {poly_tahap2_utm.area:,.2f} m²")

    # Direktori Target
    base_dirs = [
        os.path.abspath("../simulasi_berkas_geocitra"),
        os.path.abspath("../sipas-fe/public/downloads/simulasi_geocitra")
    ]

    origin_utm = (math.floor(poly_full_utm.bounds[0]), math.floor(poly_full_utm.bounds[1]))

    # Generate Layout CAD
    layout_full = build_cad_layout(poly_full_utm, origin_utm)
    layout_tahap1 = build_cad_layout(poly_tahap1_utm, origin_utm)

    # Hitung Titik Ikat Helmert
    ctrl_tahap1 = get_helmert_control_points(poly_tahap1_utm, origin_utm)
    ctrl_full = get_helmert_control_points(poly_full_utm, origin_utm)

    control_points_config = {
        "CAD_Siteplan_Tahap1_Geocitra.dxf": ctrl_tahap1,
        "CAD_Siteplan_Geocitra_Full.dxf": ctrl_full,
        "siteplan_geocitra.dxf": ctrl_tahap1
    }

    for target_dir in base_dirs:
        print(f"\nMenulis berkas ke folder: {target_dir}")
        os.makedirs(target_dir, exist_ok=True)

        # 1. Full PKKPR SHP & GeoJSON
        save_shp_zip(os.path.join(target_dir, "BPN_PKKPR_PT_Geocitra_Mandiri_Full.zip"), poly_full_utm, "pkkpr-full", "Batas Izin SK PKKPR PT Geocitra Pembangunan Mandiri", SK_NUMBER)
        save_geojson(os.path.join(target_dir, "BPN_PKKPR_PT_Geocitra_Mandiri_Full.geojson"), poly_full_utm, "pkkpr-full", "Batas Izin SK PKKPR PT Geocitra Pembangunan Mandiri", SK_NUMBER)

        # 2. Tahap 1 Site Plan SHP & GeoJSON
        save_shp_zip(os.path.join(target_dir, "BPN_Siteplan_Tahap1_Geocitra.zip"), poly_tahap1_utm, "sp-tahap-1", "Batas Site Plan Tahap 1 - Geocitra Green Residence", SK_NUMBER)
        save_geojson(os.path.join(target_dir, "BPN_Siteplan_Tahap1_Geocitra.geojson"), poly_tahap1_utm, "sp-tahap-1", "Batas Site Plan Tahap 1 - Geocitra Green Residence", SK_NUMBER)

        # 3. CAD Drawings
        save_dxf(os.path.join(target_dir, "CAD_Siteplan_Tahap1_Geocitra.dxf"), layout_tahap1)
        save_dxf(os.path.join(target_dir, "CAD_Siteplan_Geocitra_Full.dxf"), layout_full)

        # Buat juga salinan berekstensi .dwg (format teks/dxf wrapper agar diterima uploader .dwg/.dxf)
        shutil.copy(os.path.join(target_dir, "CAD_Siteplan_Tahap1_Geocitra.dxf"), os.path.join(target_dir, "CAD_Siteplan_Tahap1_Geocitra.dwg"))

        # Simpan ringkasan JSON titik ikat
        with open(os.path.join(target_dir, "titik_kontrol_helmert.json"), "w") as f:
            json.dump(control_points_config, f, indent=2)

    # Simpan juga ke file JSON frontend mock
    frontend_config_path = os.path.abspath("../sipas-fe/src/mock/siteplan/geocitra_control_points.json")
    with open(frontend_config_path, "w") as f:
        json.dump(control_points_config, f, indent=2)

    print("\n" + "=" * 70)
    print("SEMUA BERKAS SIMULASI BERHASIL DIBUAT DENGAN SEMPURNA!")
    print("=" * 70)


if __name__ == "__main__":
    main()
