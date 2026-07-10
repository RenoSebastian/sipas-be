import os
import sys
import shutil
import zipfile
import math
import random
import json
import geopandas as gpd
from shapely.geometry import Polygon
from shapely.ops import transform

def get_kab_bogor_bounds():
    """Dynamically parses coordinates of Kabupaten Bogor from GeoJSON to establish safe bounds."""
    # Attempt to locate frontend asset folder containing boundary GeoJSON
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
            print(f"[WARNING] Failed to parse GeoJSON for bounds: {str(e)}")
            
    # Hardcoded safe bounds inside Kabupaten Bogor if GeoJSON is not accessible
    return 106.33, 107.25, -6.85, -6.33

def get_random_center_in_kab_bogor():
    """Generates a random coordinate point specifically near the established Kabupaten Bogor seed locations."""
    # List of verified centers inside Kabupaten Bogor (Cibinong, Bojonggede, Sentul, Cileungsi, Gunung Putri)
    bases = [
        (106.8400, -6.4800), # Cibinong
        (106.8000, -6.4950), # Bojonggede
        (106.8700, -6.5600), # Babakan Madang (Sentul)
        (106.9600, -6.3800), # Cileungsi
        (106.9000, -6.4200), # Gunung Putri
    ]
    base_lon, base_lat = random.choice(bases)
    # Add tiny random offset to ensure each run is slightly unique but stays within the district
    lon = base_lon + random.uniform(-0.003, 0.003)
    lat = base_lat + random.uniform(-0.003, 0.003)
    return lon, lat


def generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, num_points=12, seed=42):
    """Generates a highly irregular, organic, non-convex siteplan boundary by unioning overlapping random polygons."""
    from shapely.ops import unary_union
    
    state = random.getstate()
    random.seed(seed)
    
    polys = []
    
    # 1. Base irregular shape
    points = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        r = base_radius * (0.6 + 0.5 * random.random())
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        points.append((x, y))
    polys.append(Polygon(points))
    
    # 2. Add 1-2 extra overlapping shapes to make it non-convex/organic
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
    """Transforms a Shapely geometry from local meters to WGS84 degrees around a base point."""
    rad = math.radians(rotation_deg)
    lat_len = 111132.95
    lon_len = 111132.95 * math.cos(math.radians(base_lat))
    
    def transform_coords(x, y, z=None):
        # Rotate
        x_rot = x * math.cos(rad) - y * math.sin(rad)
        y_rot = x * math.sin(rad) + y * math.cos(rad)
        
        # Scale to degrees and translate
        lon = base_lon + (x_rot / lon_len)
        lat = base_lat + (y_rot / lat_len)
        return (lon, lat)
        
    return transform(transform_coords, geom)

def main():
    print("[MOCK_SHP] Initializing organic WGS84 Shapefile generation for Kabupaten Bogor...")
    
    # Define temporary folder to build shapefile components
    temp_dir = "sample_shapefile_dir"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 1. Generate two deterministic irregular boundaries in local space
        poly_local_1 = generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, seed=101)
        poly_local_2 = generate_random_irregular_boundary(center_x=100, center_y=50, base_radius=120, seed=102)
        
        # 2. Set deterministic center locations inside Kabupaten Bogor matching seeds
        base_lon_1, base_lat_1 = 106.802744, -6.471861 # Cibinong (matches mock DXF)
        base_lon_2, base_lat_2 = 106.9000, -6.4200 # Gunung Putri
        
        rotation_deg_1 = 12.0
        rotation_deg_2 = 8.0
        
        print(f"[MOCK_SHP] Polygon 1: Center={base_lon_1:.6f},{base_lat_1:.6f}, Rot={rotation_deg_1:.1f}°, Area={poly_local_1.area:.1f}m2")
        print(f"[MOCK_SHP] Polygon 2: Center={base_lon_2:.6f},{base_lat_2:.6f}, Rot={rotation_deg_2:.1f}°, Area={poly_local_2.area:.1f}m2")

        # 3. Project them to WGS84
        wgs84_poly_1 = project_to_wgs84(poly_local_1, base_lon_1, base_lat_1, rotation_deg_1)
        wgs84_poly_2 = project_to_wgs84(poly_local_2, base_lon_2, base_lat_2, rotation_deg_2)
        
        polygons = [wgs84_poly_1, wgs84_poly_2]
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {
                "id": ["sub-1", "sub-5"],
                "name": ["Grand Bogor Residence", "Gunung Putri Commercial Hub"],
                "area_m2": [poly_local_1.area, poly_local_2.area]
            },
            geometry=polygons,
            crs="EPSG:4326"
        )
        
        # Write GeoDataFrame to Shapefile components
        shp_base_name = os.path.join(temp_dir, "sample_siteplan")
        gdf.to_file(shp_base_name + ".shp", driver="ESRI Shapefile")
        print("[MOCK_SHP] Successfully generated Shapefile component files (.shp, .shx, .dbf, .prj).")
        
        # Create zip archive in root workspace
        zip_path = "../sample_shapefile.zip"
        print(f"[MOCK_SHP] Compressing shapefiles into: {zip_path}...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_name in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                zipf.write(file_path, arcname=file_name)
                
        print(f"[MOCK_SHP] Success! Zipped Shapefile generated at: {zip_path}")
        
    except Exception as e:
        print(f"[MOCK_SHP_ERROR] Failed to generate mock Shapefile: {str(e)}")
        sys.exit(1)
        
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("[MOCK_SHP] Cleaned up temporary build files.")

if __name__ == "__main__":
    main()
