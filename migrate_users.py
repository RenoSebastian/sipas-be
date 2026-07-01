import sys
from src.infrastructure.database.connection import engine
from sqlalchemy import text

def main():
    print("[MIGRATION] Altering users table to add new security and profile columns...")
    
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS nip VARCHAR(50);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(255);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);"
    ]
    
    try:
        with engine.begin() as conn:
            for sql in statements:
                conn.execute(text(sql))
                print(f" - Executed: {sql}")
        print("[MIGRATION] Successfully updated users table schema.")
    except Exception as e:
        print(f"[MIGRATION_ERROR] Failed to alter users table: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
