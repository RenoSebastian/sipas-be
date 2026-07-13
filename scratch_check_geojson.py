import sys
import os

# Insert backend root directory to sys.path
sys.path.append(os.path.abspath('.'))

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import PermohonanModel, SitePlanGeometryModel

def main():
    db = SessionLocal()
    subs = db.query(PermohonanModel).all()
    print("TOTAL SUBMISSIONS IN DB:", len(subs))
    for s in subs:
        print(f"- ID: {s.id_permohonan}, No: {s.submission_no}, Name: {s.housing_name}")
        
    geoms = db.query(SitePlanGeometryModel).all()
    print("TOTAL SITE PLAN GEOMETRIES IN DB:", len(geoms))
    from collections import Counter
    c = Counter(g.id_permohonan for g in geoms)
    print("GEOMETRIES PER SUBMISSION:", dict(c))

if __name__ == "__main__":
    main()
