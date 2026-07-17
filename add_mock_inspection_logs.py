import sys
from datetime import datetime
from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import FieldInspectionLogModel

def main():
    print("[MOCK_SEED] Seeding field inspection logs for sub-3...")
    db = SessionLocal()
    try:
        # Clear existing logs for sub-3 first
        db.query(FieldInspectionLogModel).filter(FieldInspectionLogModel.id_permohonan == "sub-3").delete()
        
        # Add new logs
        logs = [
            # 3 overlapping points at the exact same location
            FieldInspectionLogModel(
                id_permohonan="sub-3",
                inspector_name="Tim Teknis Lapangan A",
                timestamp=datetime(2026, 7, 17, 4, 30, 0), # 04:30:00 UTC (11:30:00 WIB)
                latitude=-6.5595,
                longitude=106.8711,
                distance_from_boundary_meters=0.0,
                is_verified=True,
                photo_url="https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
                notes="Inspeksi utama patok batas sebelah timur perumahan. Kondisi aman."
            ),
            FieldInspectionLogModel(
                id_permohonan="sub-3",
                inspector_name="Tim Teknis Lapangan B",
                timestamp=datetime(2026, 7, 17, 4, 35, 0), # 04:35:00 UTC (11:35:00 WIB)
                latitude=-6.5595,
                longitude=106.8711,
                distance_from_boundary_meters=0.0,
                is_verified=True,
                photo_url="https://images.unsplash.com/photo-1541888946425-d81bb19240f5?auto=format&fit=crop&w=400&q=80",
                notes="Re-verifikasi patok batas timur di koordinat yang sama untuk double check."
            ),
            FieldInspectionLogModel(
                id_permohonan="sub-3",
                inspector_name="Tim Teknis Lapangan C",
                timestamp=datetime(2026, 7, 17, 4, 40, 0), # 04:40:00 UTC (11:40:00 WIB)
                latitude=-6.5595,
                longitude=106.8711,
                distance_from_boundary_meters=45.2,
                is_verified=False,
                photo_url="https://images.unsplash.com/photo-1581094288338-2314dddb7eed?auto=format&fit=crop&w=400&q=80",
                notes="Pengambilan foto ketiga di patok timur, namun sensor GPS melenceng terdeteksi luar lokasi."
            ),
            # 1 standalone point
            FieldInspectionLogModel(
                id_permohonan="sub-3",
                inspector_name="Tim Teknis Lapangan A",
                timestamp=datetime(2026, 7, 17, 5, 0, 0), # 05:00:00 UTC (12:00:00 WIB)
                latitude=-6.5590,
                longitude=106.8705,
                distance_from_boundary_meters=1.5,
                is_verified=True,
                photo_url="https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=400&q=80",
                notes="Inspeksi gerbang utama masuk perumahan sebelah barat."
            )
        ]
        
        db.add_all(logs)
        db.commit()
        print("[MOCK_SEED] Successfully seeded 4 mock inspection logs for sub-3!")
        
    except Exception as e:
        db.rollback()
        print(f"[MOCK_SEED_ERROR] Seeding failed: {str(e)}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
