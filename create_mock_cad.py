import sys
import math
import random
import json
import os
import ezdxf
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
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

def add_geometry_to_dxf(msp, geom, layer):
    """Recursively adds Shapely Polygons or MultiPolygons to DXF as closed polylines."""
    if geom.is_empty:
        return
    
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)[:-1]
        msp.add_lwpolyline(coords, dxfattribs={'layer': layer, 'flags': 1})
        for interior in geom.interiors:
            icoords = list(interior.coords)[:-1]
            msp.add_lwpolyline(icoords, dxfattribs={'layer': layer, 'flags': 1})
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            add_geometry_to_dxf(msp, poly, layer)
    elif geom.geom_type == 'LineString':
        coords = list(geom.coords)
        msp.add_lwpolyline(coords, dxfattribs={'layer': layer, 'flags': 0})
    elif geom.geom_type == 'MultiLineString':
        for line in geom.geoms:
            add_geometry_to_dxf(msp, line, layer)

def main():
    print("[MOCK_CAD] Generating a highly irregular, realistic site plan in WGS84 Kabupaten Bogor space...")
    try:
        # Deterministic settings to align with Polygon 1 of create_mock_shp.py
        base_lon = 106.802744
        base_lat = -6.471861
        rotation_deg = 12.0
        print(f"[MOCK_CAD] Selected center: Lon={base_lon:.6f}, Lat={base_lat:.6f} with rotation={rotation_deg:.1f}°")

        def to_wgs84(geom):
            return project_to_wgs84(geom, base_lon, base_lat, rotation_deg)

        # 2. Initialize DXF Document
        doc = ezdxf.new('R2018')
        msp = doc.modelspace()

        # Define layers
        layers = [
            ("PTSP_KDB", 1),          # Red for Building Footprint
            ("PTSP_KDH", 3),          # Green for Open Green Space
            ("PTSP_PSU_JALAN", 5),    # Blue for Roads
            ("PTSP_PSU_MAKAM", 2),    # Yellow for Cemetery Area
            ("PTSP_BATAS_LAHAN", 7),  # Property boundary line
        ]
        for name, color in layers:
            doc.layers.new(name, dxfattribs={'color': color})

        # 3. Generate Organic Outer Boundary (using seed 101 to match Polygon 1)
        boundary = generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, seed=101)
        add_geometry_to_dxf(msp, to_wgs84(boundary), 'PTSP_BATAS_LAHAN')

        # 4. Create Wavy Main Road running through the middle of the irregular shape
        road_points = []
        for rx in range(-100, 320, 10):
            ry = 45 + 20 * math.sin(rx / 60.0)
            road_points.append((rx, ry))
        road_line = LineString(road_points)
        road_poly = road_line.buffer(8)  # 16m wide street
        road_inside = boundary.intersection(road_poly)
        add_geometry_to_dxf(msp, to_wgs84(road_inside), 'PTSP_PSU_JALAN')

        # 5. Create Green Park (KDH)
        park_center = (50, 95)
        park_poly = Point(park_center).buffer(22)
        park_inside = boundary.intersection(park_poly).difference(road_poly)
        add_geometry_to_dxf(msp, to_wgs84(park_inside), 'PTSP_KDH')

        # 6. Create Cemetery Area (MAKAM)
        cemetery_center = (200, 20)
        cemetery_poly = Point(cemetery_center).buffer(18)
        cemetery_inside = boundary.intersection(cemetery_poly).difference(road_poly).difference(park_poly)
        add_geometry_to_dxf(msp, to_wgs84(cemetery_inside), 'PTSP_PSU_MAKAM')

        # 7. Generate House Blocks (KDB) inside boundary
        placed_houses = []
        boundary_buffered = boundary.buffer(-6) # 6m safety setback from irregular boundary

        # Grid scanning properties adjusted to irregular boundary size
        x_start, x_end = -80, 300
        y_start, y_end = -60, 180
        x_step, y_step = 10, 15

        for hx in range(x_start, x_end, x_step):
            for hy in range(y_start, y_end, y_step):
                hw, hh = 6, 12
                # Calculate organic rotation
                rot = math.radians(5 if hy > 45 else -5)
                
                # Construct rotated rectangle vertices
                rect_coords = [
                    (-hw/2, -hh/2), (hw/2, -hh/2), (hw/2, hh/2), (-hw/2, hh/2)
                ]
                rotated_coords = []
                for rx, ry in rect_coords:
                    nx = hx + (rx * math.cos(rot) - ry * math.sin(rot))
                    ny = hy + (rx * math.sin(rot) + ry * math.cos(rot))
                    rotated_coords.append((nx, ny))
                
                house_poly = Polygon(rotated_coords)
                
                # Check spatial constraints:
                if not boundary_buffered.contains(house_poly):
                    continue
                if house_poly.intersects(road_poly):
                    continue
                if house_poly.intersects(park_poly):
                    continue
                if house_poly.intersects(cemetery_poly):
                    continue
                
                overlapping = False
                for other_house in placed_houses:
                    if house_poly.intersects(other_house.buffer(2)): # Spacing
                        overlapping = True
                        break
                if overlapping:
                    continue
                
                placed_houses.append(house_poly)
                add_geometry_to_dxf(msp, to_wgs84(house_poly), 'PTSP_KDB')

        # Save to the root workspace directory
        output_path = "../sample_siteplan.dxf"
        doc.saveas(output_path)
        print(f"[MOCK_CAD] Success! Generated organic mock DXF file with {len(placed_houses)} houses at: {output_path}")

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Failed to generate mock CAD file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
