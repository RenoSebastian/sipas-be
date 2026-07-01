import sys
import ezdxf

def main():
    print("[MOCK_CAD] Creating a new DXF file using ezdxf...")
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

        # 1. Add Building Footprints (PTSP_KDB) - Closed Polylines (flags=1)
        # Building Block A
        msp.add_lwpolyline(
            [(10.0, 10.0), (30.0, 10.0), (30.0, 25.0), (10.0, 25.0)],
            dxfattribs={'layer': 'PTSP_KDB', 'flags': 1}
        )
        # Building Block B
        msp.add_lwpolyline(
            [(40.0, 10.0), (60.0, 10.0), (60.0, 25.0), (40.0, 25.0)],
            dxfattribs={'layer': 'PTSP_KDB', 'flags': 1}
        )

        # 2. Add Open Green Space / RTH (PTSP_KDH)
        msp.add_lwpolyline(
            [(10.0, 30.0), (60.0, 30.0), (60.0, 38.0), (10.0, 38.0)],
            dxfattribs={'layer': 'PTSP_KDH', 'flags': 1}
        )

        # 3. Add Internal Road Networks (PTSP_PSU_JALAN)
        msp.add_lwpolyline(
            [(0.0, 0.0), (80.0, 0.0), (80.0, 5.0), (0.0, 5.0)],
            dxfattribs={'layer': 'PTSP_PSU_JALAN', 'flags': 1}
        )

        # 4. Add Cemetery Area (PTSP_PSU_MAKAM)
        msp.add_lwpolyline(
            [(65.0, 10.0), (75.0, 10.0), (75.0, 20.0), (65.0, 20.0)],
            dxfattribs={'layer': 'PTSP_PSU_MAKAM', 'flags': 1}
        )

        # Save to the root workspace directory
        output_path = "../sample_siteplan.dxf"
        doc.saveas(output_path)
        print(f"[MOCK_CAD] Success! Generated mock CAD file at: {output_path}")

    except Exception as e:
        print(f"[MOCK_CAD_ERROR] Failed to generate mock CAD file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
