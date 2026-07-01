import sys
from src.infrastructure.database.connection import engine
from sqlalchemy import text

def main():
    print("[DB_CHECK] Querying permohonan table...")
    try:
        with engine.connect() as conn:
            # Query all permohonan records ordered by submission date/ID
            result = conn.execute(text("SELECT id_permohonan, submission_no, housing_name, status, ST_AsText(geom) as geom_text FROM permohonan;"))
            rows = result.fetchall()
            
            print(f"[DB_CHECK] Found {len(rows)} records in permohonan table:")
            for row in rows:
                print(f" - ID: {row[0]}")
                print(f"   No Pengajuan: {row[1]}")
                print(f"   Nama Perumahan: {row[2]}")
                print(f"   Status: {row[3]}")
                geom_desc = f"{row[4][:80]}..." if row[4] else "NULL"
                print(f"   Batas Spasial (Geom): {geom_desc}")
                print("-" * 50)
    except Exception as e:
        print(f"[DB_CHECK_ERROR] Failed to query database: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
