import sys
from src.infrastructure.database.connection import engine
from sqlalchemy import text

def main():
    print("[MIGRATION] Altering core columns in permohonan table to be nullable...")
    
    columns_to_alter = [
        "housing_name",
        "developer_name",
        "land_area"
    ]
    
    try:
        with engine.begin() as conn:
            for col in columns_to_alter:
                query = text(f"ALTER TABLE permohonan ALTER COLUMN {col} DROP NOT NULL;")
                conn.execute(query)
                print(f" - Altered core column: {col} (nullable = True)")
        print("[MIGRATION] Successfully modified database schema for core columns.")
    except Exception as e:
        print(f"[MIGRATION_ERROR] Failed to alter core columns: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
