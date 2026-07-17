from src.infrastructure.database.connection import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text("SELECT id_permohonan, COUNT(*) FROM site_plan_geometries GROUP BY id_permohonan;")).all()
    print("site_plan_geometries count by permohonan:")
    for row in result:
        print(f"Permohonan ID: {row[0]}, Count: {row[1]}")
except Exception as e:
    print(f"Error querying: {str(e)}")
finally:
    db.close()
