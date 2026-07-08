import sys
import math
import random
import ezdxf
from shapely.geometry import Polygon, LineString, Point, MultiPolygon

# Real-world surveyed irregular parcel boundary vertices (non-convex, notches, tails)
BOUNDARY_VERTICES = [
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
    print("[MOCK_CAD] Generating a highly irregular, realistic site plan in local CAD space...")
    try:
        # 1. Initialize DXF Document
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

        # 2. Generate Organic Outer Boundary
        boundary = Polygon(BOUNDARY_VERTICES)
        add_geometry_to_dxf(msp, boundary, 'PTSP_BATAS_LAHAN')

        # 3. Create Wavy Main Road running through the middle of the irregular shape
        road_points = []
        for rx in range(-100, 320, 10):
            ry = 45 + 20 * math.sin(rx / 60.0)
            road_points.append((rx, ry))
        road_line = LineString(road_points)
        road_poly = road_line.buffer(8)  # 16m wide street
        road_inside = boundary.intersection(road_poly)
        add_geometry_to_dxf(msp, road_inside, 'PTSP_PSU_JALAN')

        # 4. Create Green Park (KDH)
        park_center = (50, 95)
        park_poly = Point(park_center).buffer(22)
        park_inside = boundary.intersection(park_poly).difference(road_poly)
        add_geometry_to_dxf(msp, park_inside, 'PTSP_KDH')

        # 5. Create Cemetery Area (MAKAM)
        cemetery_center = (200, 20)
        cemetery_poly = Point(cemetery_center).buffer(18)
        cemetery_inside = boundary.intersection(cemetery_poly).difference(road_poly).difference(park_poly)
        add_geometry_to_dxf(msp, cemetery_inside, 'PTSP_PSU_MAKAM')

        # 6. Generate House Blocks (KDB) inside boundary
        placed_houses = []
        boundary_buffered = boundary.buffer(-6) # 6m safety setback from irregular boundary

        # Grid scanning properties adjusted to irregular boundary size
        x_start, x_end = -80, 300
        y_start, y_end = -60, 180
        x_step, y_step = 10, 15

        random.seed(42)
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
                add_geometry_to_dxf(msp, house_poly, 'PTSP_KDB')

        # Save to the root workspace directory
        output_path = "../sample_siteplan.dxf"
        doc.saveas(output_path)
        print(f"[MOCK_CAD] Success! Generated organic mock DXF file with {len(placed_houses)} houses at: {output_path}")

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Failed to generate mock CAD file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
