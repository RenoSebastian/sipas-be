import sys
from sqlalchemy import text
from src.infrastructure.database.connection import engine

def main():
    print("[POSTGIS] Connecting to the database to enable PostGIS...")
    try:
        # Open connection and execute CREATE EXTENSION
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
        print("[POSTGIS] Success! PostGIS extension is enabled.")
    except Exception as e:
        print(f"[POSTGIS_ERROR] Failed to enable PostGIS: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
