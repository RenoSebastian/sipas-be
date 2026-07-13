import sys
import os

# Insert backend root directory to sys.path
sys.path.append(os.path.abspath('.'))

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import SitePlanGeometryModel
from geoalchemy2.shape import to_shape

def main():
    db = SessionLocal()
    geoms = db.query(SitePlanGeometryModel).filter(SitePlanGeometryModel.id_permohonan == "sub-4").all()
    for g in geoms:
        shape = to_shape(g.geom)
        print(f"Layer: {g.layer_name}, Type: {shape.geom_type}, Bounds: {shape.bounds}")

if __name__ == "__main__":
    main()
