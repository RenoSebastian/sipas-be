"""
============================================================================
SIPAS MOCK — Generator Shapefile BPN [create_mock_shp.py]
============================================================================
Menghasilkan berkas SHP (.zip) + GeoJSON batas lahan pada koordinat uji yang
didefinisikan di mock_site_config.py. Geometri dibangun dari sumber UTM 48S
yang sama dengan create_mock_cad.py, sehingga CAD selalu menumpuk tepat di
atas SHP setelah kalibrasi Helmert.

Jalankan dari folder sipas-be:  poetry run python create_mock_shp.py
Output ditulis ke folder root SIPAS (../).
============================================================================
"""

import json
import os
import shutil
import sys
import zipfile

import shapefile
from shapely.geometry import mapping

from mock_site_config import (
    SITE_ID,
    SITE_NAME,
    get_site_polygon_utm,
    split_polygon_vertically,
    utm_to_wgs84_geom,
)

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def save_shp_zip(zip_path, utm_poly, sub_id, name):
    """Menyimpan satu poligon (sumber UTM) sebagai ESRI Shapefile WGS84 terkompresi ZIP."""
    temp_dir = f"temp_shp_{sub_id}"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        wgs84_poly = utm_to_wgs84_geom(utm_poly)
        shp_path = os.path.join(temp_dir, "siteplan")

        w = shapefile.Writer(shp_path, shapeType=shapefile.POLYGON)
        w.field("id", "C", 50)
        w.field("name", "C", 255)
        w.field("area_m2", "N", decimal=2)
        w.poly([[list(pt) for pt in wgs84_poly.exterior.coords]])
        w.record(sub_id, name, round(utm_poly.area, 2))
        w.close()

        with open(shp_path + ".prj", "w") as prjf:
            prjf.write(PRJ_WGS84)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                file_name = f"siteplan{ext}"
                zipf.write(os.path.join(temp_dir, file_name), arcname=file_name)
        print(f"[MOCK_SHP] Berhasil menulis shapefile zip ke: {zip_path} ({utm_poly.area:,.2f} m²)")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def save_geojson(geojson_path, utm_poly, sub_id, name):
    """Menyimpan GeoJSON batas lahan (form pengajuan mem-parsing .geojson secara nyata)."""
    wgs84_poly = utm_to_wgs84_geom(utm_poly)
    feature_collection = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"id": sub_id, "name": name, "area_m2": round(utm_poly.area, 2)},
            "geometry": mapping(wgs84_poly),
        }],
    }
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2)
    print(f"[MOCK_SHP] Berhasil menulis GeoJSON ke: {geojson_path}")


def main():
    print(f"[MOCK_SHP] Membuat berkas SHP batas lahan untuk: {SITE_NAME}")

    try:
        large_poly = get_site_polygon_utm()
        small_poly_1, small_poly_2 = split_polygon_vertically(large_poly)

        # ─── SEEDER ASLI (BACKWARD COMPATIBILITY) ───
        save_shp_zip("../sample_shapefile.zip", large_poly, SITE_ID, SITE_NAME)
        save_geojson("../sample_siteplan.geojson", large_poly, SITE_ID, SITE_NAME)

        # ─── FITUR SPLIT/MERGE SIMULATION ───
        print("\n[MOCK_SHP] Membuat berkas simulasi Split / Merge:")
        print(f" - Large   : {large_poly.area:,.2f} m²")
        print(f" - Small 1 : {small_poly_1.area:,.2f} m²")
        print(f" - Small 2 : {small_poly_2.area:,.2f} m² (Total anak = {small_poly_1.area + small_poly_2.area:,.2f} m²)")

        save_shp_zip("../mock_large_siteplan.zip", large_poly, "sub-large", "Large Parent Siteplan")
        save_shp_zip("../mock_small_siteplan_1.zip", small_poly_1, "sub-small-1", "Small Child Siteplan 1")
        save_shp_zip("../mock_small_siteplan_2.zip", small_poly_2, "sub-small-2", "Small Child Siteplan 2")
        save_geojson("../mock_large_siteplan.geojson", large_poly, "sub-large", "Large Parent Siteplan")
        save_geojson("../mock_small_siteplan_1.geojson", small_poly_1, "sub-small-1", "Small Child Siteplan 1")
        save_geojson("../mock_small_siteplan_2.geojson", small_poly_2, "sub-small-2", "Small Child Siteplan 2")

        print("[MOCK_SHP] Sukses memproduksi seluruh berkas Shapefile BPN.")
    except Exception as e:
        print(f"[MOCK_SHP_ERROR] Gagal memproduksi berkas SHP: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()