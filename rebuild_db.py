import sys
import os
from sqlalchemy import text
from alembic.config import Config
from alembic import command

# Sisipkan direktori root ke dalam sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def main():
    print("=" * 80)
    print("SIPAS DATABASE REBUILD UTILITY")
    print("=" * 80)
    
    # 1. Reset database schema
    print("[1/5] Dropping and recreating public schema (database reset)...")
    from src.infrastructure.database.connection import engine
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        print(" [OK] Public schema reset and PostGIS extension enabled.")
    except Exception as e:
        print(f" [FAIL] Failed to reset database: {str(e)}")
        sys.exit(1)

    # 2. Run Alembic migrations
    print("[2/5] Running Alembic migrations to build standard tables...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print(" [OK] Alembic migrations completed successfully.")
    except Exception as e:
        print(f" [FAIL] Alembic migration failed: {str(e)}")
        sys.exit(1)

    # 3. Add custom columns to users & permohonan
    print("[3/5] Adding custom columns and creating reference spatial tables...")
    statements_custom = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nip VARCHAR(50);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(255);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);",
        "ALTER TABLE permohonan ADD COLUMN IF NOT EXISTS tech_water_source VARCHAR(255);",
        "ALTER TABLE permohonan ADD COLUMN IF NOT EXISTS kabid_signature TEXT;",
        "ALTER TABLE lahan_kompensasi ADD COLUMN IF NOT EXISTS alamat_lokasi VARCHAR(500);",
        "ALTER TABLE permohonan_tpu ADD COLUMN IF NOT EXISTS koordinat VARCHAR(100);",
        "ALTER TABLE permohonan ADD COLUMN IF NOT EXISTS admin_lock_id INTEGER REFERENCES users(id) ON DELETE SET NULL;",
        "ALTER TABLE permohonan ADD COLUMN IF NOT EXISTS teknisi_lock_id INTEGER REFERENCES users(id) ON DELETE SET NULL;",
        "DROP TABLE IF EXISTS region_references CASCADE;",
        "DROP TABLE IF EXISTS system_feedbacks CASCADE;",
        "CREATE TABLE IF NOT EXISTS spatial_reference_layers (id SERIAL PRIMARY KEY, layer_key VARCHAR(50) NOT NULL, layer_name VARCHAR(100) NOT NULL, geom geometry(GEOMETRY, 4326) NOT NULL);",
        "CREATE INDEX IF NOT EXISTS idx_spatial_ref_layer_key ON spatial_reference_layers(layer_key);",
        "CREATE INDEX IF NOT EXISTS idx_spatial_ref_geom ON spatial_reference_layers USING gist(geom);"
    ]
    try:
        with engine.begin() as conn:
            for sql in statements_custom:
                conn.execute(text(sql))
        print(" [OK] Custom columns added.")
    except Exception as e:
        print(f" [FAIL] Failed to add custom user columns: {str(e)}")
        sys.exit(1)

    # 4. Alter columns to nullable in permohonan table (for Draft support)
    print("[4/5] Adjusting permohonan columns to be nullable for Drafts...")
    columns_to_alter = [
        "applicant_name", "applicant_npwp", "applicant_phone", "applicant_email", "applicant_address",
        "location_name", "location_village", "location_district", "location_city", "location_province",
        "location_full_address", "location_ownership_status", "location_certificate_number", "location_certificate_owner",
        "spatial_kkpr_number", "spatial_land_use", "consultant_name", "consultant_company_name", "consultant_pic_name",
        "housing_name", "developer_name", "land_area"
    ]
    try:
        with engine.begin() as conn:
            for col in columns_to_alter:
                query = text(f"ALTER TABLE permohonan ALTER COLUMN {col} DROP NOT NULL;")
                conn.execute(query)
        print(" [OK] Permohonan columns set to nullable.")
    except Exception as e:
        print(f" [FAIL] Failed to adjust permohonan columns: {str(e)}")
        sys.exit(1)

    # 5. Run Database Seeder
    print("[5/5] Seeding spatial and user data...")
    try:
        from src.infrastructure.database.seed import seed_spatial_data
        seed_spatial_data()
        print(" [OK] Seeding completed successfully.")
    except Exception as e:
        print(f" [FAIL] Seeding failed: {str(e)}")
        sys.exit(1)

    print("=" * 80)
    print("SUCCESS: Database rebuilt and seeded successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()
