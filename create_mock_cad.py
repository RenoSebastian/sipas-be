import sys
import ezdxf

def main():
    print("[MOCK_CAD] Creating a highly detailed DXF file using ezdxf...")
    try:
        # Create a new DXF R2018 document
        doc = ezdxf.new('R2018')
        msp = doc.modelspace()

        # Define allowed OGC standard layers in Kabupaten Bogor
        layers = [
            ("PTSP_KDB", 1),       # Red for Building Footprint (KDB)
            ("PTSP_KDH", 3),       # Green for Open Green Space (KDH)
            ("PTSP_PSU_JALAN", 5), # Blue for Internal Roads
            ("PTSP_PSU_MAKAM", 2), # Yellow for Cemetery Area
        ]

        # Add layers to the document
        for name, color in layers:
            doc.layers.new(name, dxfattribs={'color': color})
            print(f" - Created layer: {name} (color: {color})")

        # Utility function to draw a closed rectangular polyline (LWPOLYLINE)
        def draw_box(x, y, w, h, layer):
            msp.add_lwpolyline(
                [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                dxfattribs={'layer': layer, 'flags': 1}
            )

        # 1. Add Building Footprints (PTSP_KDB) - 48 houses (6m x 12m each)
        # Organized across 8 blocks: A, B, C, D, E, F, G, H
        # West blocks (x=10..46), East blocks (x=58..94)
        x_offsets_west = [10, 16, 22, 28, 34, 40]
        x_offsets_east = [58, 64, 70, 76, 82, 88]
        y_rows = [
            (10, "Block A/B"),  # Row 1 (y=10..22)
            (28, "Block C/D"),  # Row 2 (y=28..40)
            (50, "Block E/F"),  # Row 3 (y=50..62)
            (68, "Block G/H")   # Row 4 (y=68..80)
        ]

        for y, label in y_rows:
            # West block
            for x in x_offsets_west:
                draw_box(x, y, 6, 12, 'PTSP_KDB')
            # East block
            for x in x_offsets_east:
                draw_box(x, y, 6, 12, 'PTSP_KDB')

        # 2. Add Open Green Spaces / RTH (PTSP_KDH)
        # North-West central park
        draw_box(0, 80, 46, 15, 'PTSP_KDH')
        # North-East park
        draw_box(58, 80, 62, 15, 'PTSP_KDH')
        # West side buffer strip
        draw_box(0, 0, 10, 80, 'PTSP_KDH')

        # 3. Add Internal Road Network (PTSP_PSU_JALAN)
        # Main horizontally running avenue (10m wide)
        draw_box(0, 40, 120, 10, 'PTSP_PSU_JALAN')
        # Horizontal street 1 (6m wide)
        draw_box(0, 22, 120, 6, 'PTSP_PSU_JALAN')
        # Horizontal street 3 (6m wide)
        draw_box(0, 62, 120, 6, 'PTSP_PSU_JALAN')
        # Main vertical street connecting blocks (12m wide)
        draw_box(46, 0, 12, 95, 'PTSP_PSU_JALAN')

        # 4. Add Cemetery Area (PTSP_PSU_MAKAM)
        # South-East corner dedicated cemetery area (20m x 25m)
        draw_box(98, 10, 20, 25, 'PTSP_PSU_MAKAM')

        # Save to the root workspace directory
        output_path = "../sample_siteplan.dxf"
        doc.saveas(output_path)
        print(f"[MOCK_CAD] Success! Generated highly detailed mock CAD file at: {output_path}")

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Failed to generate mock CAD file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
