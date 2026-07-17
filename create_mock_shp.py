import os
import sys
import shutil
import zipfile
import math
import random
import json
import shapefile
from shapely.geometry import Polygon
from shapely.ops import transform

def get_kab_bogor_bounds():
    """Membaca koordinat Kabupaten Bogor secara dinamis dari aset GeoJSON untuk batas aman."""
    geojson_path = os.path.join(os.path.dirname(__file__), "sipas-fe", "src", "assets", "geojson", "kab bogor", "ADMINISTRASI_LN_25K.json")
    if not os.path.exists(geojson_path):
        geojson_path = os.path.join(os.path.dirname(__file__), "..", "sipas-fe", "src", "assets", "geojson", "kab bogor", "ADMINISTRASI_LN_25K.json")
    
    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            lons = []
            lats = []
            for feature in data.get("features", []):
                geom = feature.get("geometry", {})
                if geom.get("type") == "LineString":
                    coords = geom.get("coordinates", [])
                    for pt in coords:
                        lons.append(pt[0])
                        lats.append(pt[1])
            if lons and lats:
                return min(lons), max(lons), min(lats), max(lats)
        except Exception as e:
            print(f"[WARNING] Gagal memproses GeoJSON batasan wilayah: {str(e)}")
            
    return 106.33, 107.25, -6.85, -6.33


def generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, num_points=12, seed=42):
    """
    Menghasilkan batas luar lahan organik tidak beraturan (non-convex)
    menggunakan gabungan beberapa poligon acak yang saling tumpang tindih.
    """
    from shapely.ops import unary_union
    
    state = random.getstate()
    random.seed(seed)
    
    polys = []
    
    # 1. Poligon dasar tidak beraturan
    points = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        r = base_radius * (0.6 + 0.5 * random.random())
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        points.append((x, y))
    polys.append(Polygon(points))
    
    # 2. Tambahkan poligon tumpang tindih ekstra untuk membuat lekukan organik
    num_extra = random.randint(1, 2)
    for _ in range(num_extra):
        extra_angle = random.random() * 2 * math.pi
        extra_dist = base_radius * 0.7
        ex = center_x + extra_dist * math.cos(extra_angle)
        ey = center_y + extra_dist * math.sin(extra_angle)
        er = base_radius * (0.4 + 0.5 * random.random())
        
        extra_points = []
        extra_num = random.randint(6, 10)
        for i in range(extra_num):
            angle = (2 * math.pi * i) / extra_num
            r = er * (0.7 + 0.3 * random.random())
            x = ex + r * math.cos(angle)
            y = ey + r * math.sin(angle)
            extra_points.append((x, y))
        polys.append(Polygon(extra_points))
        
    unified = unary_union(polys)
    if unified.geom_type == 'MultiPolygon':
        unified = max(unified.geoms, key=lambda p: p.area)
    elif unified.geom_type != 'Polygon':
        unified = Polygon(points)
    
    random.setstate(state)
    return unified.simplify(1.0, preserve_topology=True)


def project_to_wgs84(geom, base_lon, base_lat, rotation_deg=0):
    """Mentransformasikan koordinat lokal meter ke proyeksi derajat bumi WGS84."""
    rad = math.radians(rotation_deg)
    lat_len = 111132.95
    lon_len = 111132.95 * math.cos(math.radians(base_lat))
    
    def transform_coords(x, y, z=None):
        # Rotasi
        x_rot = x * math.cos(rad) - y * math.sin(rad)
        y_rot = x * math.sin(rad) + y * math.cos(rad)
        
        # Translasi dan penskalaan derajat geografis
        lon = base_lon + (x_rot / lon_len)
        lat = base_lat + (y_rot / lat_len)
        return (lon, lat)
        
    return transform(transform_coords, geom)


def split_polygon_vertically(poly):
    """Membagi poligon Shapely menjadi 2 bagian secara vertikal di tengah-tengah bounding box."""
    from shapely.geometry import box
    minx, miny, maxx, maxy = poly.bounds
    center_x = (minx + maxx) / 2
    left_box = box(minx, miny, center_x, maxy)
    right_box = box(center_x, miny, maxx, maxy)
    
    left_poly = poly.intersection(left_box)
    right_poly = poly.intersection(right_box)
    
    if left_poly.geom_type == 'MultiPolygon':
        left_poly = max(left_poly.geoms, key=lambda p: p.area)
    if right_poly.geom_type == 'MultiPolygon':
        right_poly = max(right_poly.geoms, key=lambda p: p.area)
        
    return left_poly, right_poly


def save_shp_zip(zip_path, local_poly, base_lon, base_lat, rotation_deg, sub_id, name):
    """Fungsi helper untuk menyimpan satu poligon ke bentuk ESRI Shapefile yang terkompresi ZIP."""
    temp_dir = f"temp_shp_{sub_id}"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        wgs84_poly = project_to_wgs84(local_poly, base_lon, base_lat, rotation_deg)
        shp_path = os.path.join(temp_dir, "siteplan")
        
        w = shapefile.Writer(shp_path)
        w.field("id", "C", 50)
        w.field("name", "C", 255)
        w.field("area_m2", "N", decimal=2)
        
        coords = [list(pt) for pt in wgs84_poly.exterior.coords]
        w.poly([coords])
        w.record(sub_id, name, local_poly.area)
        w.close()
        
        prj_content = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
        with open(shp_path + ".prj", "w") as prjf:
            prjf.write(prj_content)
            
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                file_name = f"siteplan{ext}"
                file_path = os.path.join(temp_dir, file_name)
                zipf.write(file_path, arcname=file_name)
        print(f"[MOCK_SHP] Berhasil menulis shapefile zip ke: {zip_path}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main():
    print("[MOCK_SHP] Memulai pembuatan berkas SHP terkompresi (.zip) batas luar organik untuk Kabupaten Bogor...")
    
    # ─── SEEDER ASLI (BACKWARD COMPATIBILITY) ───
    temp_dir = "sample_shapefile_dir"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        poly_local_1 = generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, seed=101)
        poly_local_2 = generate_random_irregular_boundary(center_x=100, center_y=50, base_radius=120, seed=102)
        
        base_lon_1, base_lat_1 = 106.802744, -6.471861  # Cibinong (sub-1)
        base_lon_2, base_lat_2 = 106.900000, -6.420000  # Gunung Putri (sub-5)
        
        rotation_deg_1 = 12.0
        rotation_deg_2 = 8.0
        
        wgs84_poly_1 = project_to_wgs84(poly_local_1, base_lon_1, base_lat_1, rotation_deg_1)
        wgs84_poly_2 = project_to_wgs84(poly_local_2, base_lon_2, base_lat_2, rotation_deg_2)
        
        shp_path = os.path.join(temp_dir, "sample_siteplan")
        w = shapefile.Writer(shp_path)
        w.field("id", "C", 50)
        w.field("name", "C", 255)
        w.field("area_m2", "N", decimal=2)
        
        w.poly([[list(pt) for pt in wgs84_poly_1.exterior.coords]])
        w.record("sub-1", "Grand Bogor Residence", poly_local_1.area)
        
        w.poly([[list(pt) for pt in wgs84_poly_2.exterior.coords]])
        w.record("sub-5", "Gunung Putri Commercial Hub", poly_local_2.area)
        
        w.close()
        
        prj_content = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
        with open(shp_path + ".prj", "w") as prjf:
            prjf.write(prj_content)
            
        zip_path = "../sample_shapefile.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                file_name = f"sample_siteplan{ext}"
                file_path = os.path.join(temp_dir, file_name)
                zipf.write(file_path, arcname=file_name)
        print(f"[MOCK_SHP] Sukses membuat berkas fallback: {zip_path}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    # ─── FITUR SPLIT/MERGE SIMULATION (3 OUTPUT DENGAN KOORDINAT SAMA) ───
    try:
        # Gunakan poly_local_1 (seed 101) sebagai poligon besar
        large_poly = poly_local_1
        
        # Potong menjadi dua bagian secara spasial (vertikal)
        small_poly_1, small_poly_2 = split_polygon_vertically(large_poly)
        
        print("\n[MOCK_SHP] Membuat 3 berkas Shapefile baru untuk simulasi Split / Merge (di koordinat Cibinong):")
        print(f" - Large Siteplan Area: {large_poly.area:.2f} m²")
        print(f" - Small Siteplan 1 Area: {small_poly_1.area:.2f} m²")
        print(f" - Small Siteplan 2 Area: {small_poly_2.area:.2f} m² (Total anak = {small_poly_1.area + small_poly_2.area:.2f} m²)")
        
        # Simpan ketiga file ke folder root
        save_shp_zip("../mock_large_siteplan.zip", large_poly, base_lon_1, base_lat_1, rotation_deg_1, "sub-large", "Large Parent Siteplan")
        save_shp_zip("../mock_small_siteplan_1.zip", small_poly_1, base_lon_1, base_lat_1, rotation_deg_1, "sub-small-1", "Small Child Siteplan 1")
        save_shp_zip("../mock_small_siteplan_2.zip", small_poly_2, base_lon_1, base_lat_1, rotation_deg_1, "sub-small-2", "Small Child Siteplan 2")
        
        print("[MOCK_SHP] Sukses memproduksi seluruh berkas simulasi Split/Merge Shapefile BPN.")
        
    except Exception as e:
        print(f"[MOCK_SHP_ERROR] Gagal memproduksi berkas simulasi Split/Merge: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()