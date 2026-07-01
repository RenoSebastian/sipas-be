import sys
from src.infrastructure.database.connection import engine
from sqlalchemy import text

def main():
    print("[MIGRATION] Altering columns in permohonan table to be nullable...")
    
    # Columns to alter to nullable (DROP NOT NULL)
    columns_to_alter = [
        "applicant_name",
        "applicant_npwp",
        "applicant_phone",
        "applicant_email",
        "applicant_address",
        "location_name",
        "location_village",
        "location_district",
        "location_city",
        "location_province",
        "location_full_address",
        "location_ownership_status",
        "location_certificate_number",
        "location_certificate_owner",
        "spatial_kkpr_number",
        "spatial_land_use",
        "consultant_name",
        "consultant_company_name",
        "consultant_pic_name"
    ]
    
    try:
        with engine.begin() as conn:
            for col in columns_to_alter:
                query = text(f"ALTER TABLE permohonan ALTER COLUMN {col} DROP NOT NULL;")
                conn.execute(query)
                print(f" - Altered column: {col} (nullable = True)")
        print("[MIGRATION] Successfully modified database schema.")
    except Exception as e:
        print(f"[MIGRATION_ERROR] Failed to alter columns: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
