import sys
import math
import random
import os
import ezdxf
from shapely.geometry import Polygon, LineString, Point

def generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, num_points=12, seed=42):
    """
    Menghasilkan batas luar lahan organik tidak beraturan (non-convex)
    pada koordinat kartesian lokal meter (Tanpa WGS84).
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


def generate_irregular_lot_local(center_x, center_y, size=8, seed=None):
    """
    Menghasilkan kaveling bangunan berbentuk organik (trapezoid / jajar genjang acak).
    Sama sekali menghindari bentuk persegi kaku.
    """
    if seed is not None:
        random.seed(seed)

    # Berikan variasi panjang acak pada setiap sumbu kaveling
    dx1 = random.uniform(0.75, 1.25) * (size / 2)
    dx2 = random.uniform(0.75, 1.25) * (size / 2)
    dy1 = random.uniform(0.75, 1.25) * (size / 2)
    dy2 = random.uniform(0.75, 1.25) * (size / 2)

    # Bentuk Trapesium / Jajar Genjang asimetris
    local_coords = [
        (-dx1, -dy1),                      # Pojok Kiri Bawah
        (dx2, -dy1 * random.uniform(0.9, 1.1)), # Pojok Kanan Bawah
        (dx2 * random.uniform(0.7, 0.9), dy2), # Pojok Kanan Atas (menyempit)
        (-dx1 * random.uniform(1.0, 1.2), dy2 * random.uniform(0.95, 1.05)), # Pojok Kiri Atas
    ]
    
    # Geser ke titik pusat kaveling
    return Polygon([(x + center_x, y + center_y) for x, y in local_coords])


def add_geometry_to_dxf(msp, geom, layer):
    """Membakar koordinat spasial Shapely menjadi poligon tertutup di file CAD DXF."""
    if geom.is_empty:
        return
    
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)[:-1]
        msp.add_lwpolyline(coords, dxfattribs={'layer': layer, 'flags': 1})
        for interior in geom.interiors:
            icoords = list(interior.coords)[:-1]
            msp.add_lwpolyline(icoords, dxfattribs={'layer': layer, 'flags': 1})
    elif geom.geom_type == 'LineString':
        coords = list(geom.coords)
        msp.add_lwpolyline(coords, dxfattribs={'layer': layer, 'flags': 0})


def main():
    print("[MOCK_CAD] Memulai pembuatan berkas CAD site plan organik kartesian murni...")
    try:
        doc = ezdxf.new('R2018')
        msp = doc.modelspace()

        # Daftarkan standar layer OGC dinas [sipas-be.txt]
        layers = [
            ("PTSP_KDB", 1),          # Merah untuk kaveling bangunan
            ("PTSP_KDH", 3),          # Hijau untuk area terbuka hijau (RTH)
            ("PTSP_PSU_JALAN", 5),    # Biru untuk as jalan
            ("PTSP_PSU_MAKAM", 2),    # Kuning untuk area pemakaman
            ("PTSP_BATAS_LAHAN", 7),  # Putih/Abu untuk batas terluar bidang tanah
        ]
        for name, color in layers:
            doc.layers.new(name, dxfattribs={'color': color})

        # 1. Batas Terluar Lahan Organik Lokal (Seed 101 - Presisi Sesuai dengan SHP)
        boundary = generate_random_irregular_boundary(center_x=110, center_y=55, base_radius=140, seed=101)
        add_geometry_to_dxf(msp, boundary, 'PTSP_BATAS_LAHAN')

        # 2. Jalan Utama Meliuk Lokal (Wavy Road)
        road_points = []
        for rx in range(-100, 320, 10):
            ry = 45 + 20 * math.sin(rx / 60.0)
            road_points.append((rx, ry))
        road_line = LineString(road_points)
        road_poly = road_line.buffer(8)  # Lebar jalan 16m
        road_inside = boundary.intersection(road_poly)
        add_geometry_to_dxf(msp, road_inside, 'PTSP_PSU_JALAN')

        # 3. Taman Publik Hijau Organik Lokal (KDH)
        park_center = (50, 95)
        park_poly = Point(park_center).buffer(22)
        park_inside = boundary.intersection(park_poly).difference(road_poly)
        add_geometry_to_dxf(msp, park_inside, 'PTSP_KDH')

        # 4. Area Makam Organik Lokal (TPU)
        cemetery_center = (200, 20)
        cemetery_poly = Point(cemetery_center).buffer(18)
        cemetery_inside = boundary.intersection(cemetery_poly).difference(road_poly).difference(park_poly)
        add_geometry_to_dxf(msp, cemetery_inside, 'PTSP_PSU_MAKAM')

        # 5. Kaveling Hunian Trapesium / Jajar Genjang Lokal (KDB)
        placed_houses = []
        boundary_buffered = boundary.buffer(-6) # Jarak aman setback dari jalan/batas terluar

        x_start, x_end = -80, 300
        y_start, y_end = -60, 180
        x_step, y_step = 10, 15

        random.seed(42)
        for hx in range(x_start, x_end, x_step):
            for hy in range(y_start, y_end, y_step):
                # Buat bentuk kaveling acak non-persegi
                house_poly = generate_irregular_lot_local(hx, hy, size=8)

                # Validasi kelayakan spasial kaveling
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
                    if house_poly.intersects(other_house.buffer(2)):
                        overlapping = True
                        break
                if overlapping:
                    continue

                placed_houses.append(house_poly)
                add_geometry_to_dxf(msp, house_poly, 'PTSP_KDB')

        output_path = "../sample_siteplan.dxf"
        doc.saveas(output_path)
        print(f"[MOCK_CAD] Sukses! Berkas CAD lokal meter berhasil dibuat di: {output_path}")

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Gagal memproduksi berkas CAD spasial: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()