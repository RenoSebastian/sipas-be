import os
import sys
import shutil
import zipfile
import math
import geopandas as gpd
from shapely.geometry import Polygon

# Real-world surveyed irregular parcel boundary vertices matching create_mock_cad.py
BOUNDARY_VERTICES_1 = [
    (0, 0),
    (140, 15),
    (155, -45),
    (240, -30),
    (220, 70),
    (280, 110),
    (190, 160),
    (110, 115),
    (80, 140),
    (-40, 100),
    (-20, 50),
    (-60, 30),
    (0, 0)
]

BOUNDARY_VERTICES_2 = [
    (0, 0),
    (90, -10),
    (110, -50),
    (180, -30),
    (160, 40),
    (200, 70),
    (130, 120),
    (80, 85),
    (50, 100),
    (-30, 70),
    (-10, 35),
    (-40, 20),
    (0, 0)
]

def cad_to_wgs84(vertices, base_lon, base_lat, rotation_deg=12):
    """Projects local CAD polygon to WGS84 coordinates in Kabupaten Bogor."""
    rad = math.radians(rotation_deg)
    
    # Scale: meters per degree at latitude base_lat
    lat_len = 111132.95
    lon_len = 111132.95 * math.cos(math.radians(base_lat))
    
    wgs84_coords = []
    for x, y in vertices:
        # Rotate
        x_rot = x * math.cos(rad) - y * math.sin(rad)
        y_rot = x * math.sin(rad) + y * math.cos(rad)
        
        # Scale to degrees and translate
        lon = base_lon + (x_rot / lon_len)
        lat = base_lat + (y_rot / lat_len)
        wgs84_coords.append((lon, lat))
        
    return Polygon(wgs84_coords)

def main():
    print("[MOCK_SHP] Initializing organic WGS84 Shapefile generation for Kabupaten Bogor...")
    
    # Define temporary folder to build shapefile components
    temp_dir = "sample_shapefile_dir"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 1. Project CAD boundary to Bojong Gede (for sub-1)
        wgs84_poly_1 = cad_to_wgs84(BOUNDARY_VERTICES_1, base_lon=106.8400, base_lat=-6.4800, rotation_deg=12)
        
        # 2. Project second CAD boundary to Gunung Putri (for sub-5 / sub-2)
        wgs84_poly_2 = cad_to_wgs84(BOUNDARY_VERTICES_2, base_lon=106.9000, base_lat=-6.4200, rotation_deg=8)
        
        polygons = [wgs84_poly_1, wgs84_poly_2]
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {
                "id": ["sub-1", "sub-5"],
                "name": ["Grand Bogor Residence", "Gunung Putri Commercial Hub"],
                "area_m2": [wgs84_poly_1.area * (111132.95**2 * math.cos(math.radians(-6.48))), 
                            wgs84_poly_2.area * (111132.95**2 * math.cos(math.radians(-6.42)))]
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
