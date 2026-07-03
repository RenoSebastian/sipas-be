import os
import sys
import shutil
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon

def main():
    print("[MOCK_SHP] Initializing Shapefile generation using geopandas...")
    
    # Define temporary folder to build shapefile components
    temp_dir = "sample_shapefile_dir"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Define mock polygon coordinates in WGS84 (Lng, Lat) for Kabupaten Bogor (irregular surveyed parcels)
        polygons = [
            # Lahan 1 (Bojong Gede area - sub-1)
            Polygon([
                (106.84000, -6.48000),
                (106.84300, -6.48020),
                (106.84280, -6.48150),
                (106.84320, -6.48280),
                (106.84150, -6.48310),
                (106.84010, -6.48250),
                (106.84020, -6.48120),
                (106.84000, -6.48000)
            ]),
            # Lahan 2 (Gunung Putri area - sub-5)
            Polygon([
                (106.90000, -6.42000),
                (106.90150, -6.42010),
                (106.90140, -6.42080),
                (106.90160, -6.42140),
                (106.90080, -6.42160),
                (106.90010, -6.42120),
                (106.90020, -6.42060),
                (106.90000, -6.42000)
            ])
        ]
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {
                "id": ["sub-1", "sub-5"],
                "name": ["Grand Bogor Residence", "Gunung Putri Commercial Hub"],
                "area_m2": [25000.0, 12000.0]
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
