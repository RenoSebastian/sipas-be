import sys
from src.infrastructure.database.connection import engine
from sqlalchemy import text

def main():
    print("[MIGRATION] Adding kabid_signature column to permohonan table...")
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE permohonan ADD COLUMN IF NOT EXISTS kabid_signature TEXT;"))
            print(" - Column kabid_signature successfully added to permohonan table.")
    except Exception as e:
        print(f"[MIGRATION_ERROR] Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
