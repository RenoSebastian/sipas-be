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
        # Define mock polygon coordinates in WGS84 (Lng, Lat) for Kabupaten Bogor
        polygons = [
            # Lahan 1 (Grand Bogor Residence area)
            Polygon([
                (106.8160, -6.5945),
                (106.8175, -6.5945),
                (106.8175, -6.5960),
                (106.8160, -6.5960),
                (106.8160, -6.5945)
            ]),
            # Lahan 2 (Batu Tulis area)
            Polygon([
                (106.8105, -6.6205),
                (106.8120, -6.6205),
                (106.8120, -6.6220),
                (106.8105, -6.6220),
                (106.8105, -6.6205)
            ])
        ]
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {
                "id": ["sub-1", "sub-5"],
                "name": ["Grand Bogor Residence", "Batu Tulis Residence"],
                "area_m2": [25000.0, 15000.0]
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
