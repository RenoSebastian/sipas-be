"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — PostGIS Spatial Audit Adapter [postgis_audit_adapter.py]
============================================================================
Peran: Mengimplementasikan SpatialAuditPort menggunakan PostGIS untuk melakukan
       kalkulasi overlay spasial dan deteksi tumpang tindih secara real.
============================================================================
"""

import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.use_cases.audit_spatial import SpatialAuditPort

logger = logging.getLogger("sipas-be")

class PostGisSpatialAuditAdapter(SpatialAuditPort):
    def __init__(self, db: Session):
        self.db = db

    def audit_geometry_against_layers(self, id_permohonan: str, category: str) -> List[Dict[str, Any]]:
        logger.info(f"[POSTGIS_AUDIT] Menjalankan audit spasial riil menggunakan PostGIS untuk permohonan ID: {id_permohonan}")
        
        results = []

        # 1. Cek Sempadan Sungai 25m (ST_Buffer 25m)
        query_sungai = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, ST_Buffer(s.geom::geography, 25)::geometry)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_sungai s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, ST_Buffer(s.geom::geography, 25)::geometry)
        """)
        clash_sungai = float(self.db.execute(query_sungai, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-river",
            "layer_name": "Sempadan Sungai 25m",
            "clash_area_sqm": round(clash_sungai, 2),
            "description": f"Terdapat tumpang tindih dengan sempadan sungai (buffer 25m) seluas {clash_sungai:.2f} m²." if clash_sungai > 0
                           else "Clean — tidak ada tumpang tindih dengan Sempadan Sungai 25m.",
            "severity": "danger" if clash_sungai > 0 else "info",
            "zoning_note": "PP No. 38/2011 tentang Sungai"
        })

        # 2. Cek Lahan Sawah Dilindungi - LSD
        query_sawah = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_sawah s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
        """)
        clash_sawah = float(self.db.execute(query_sawah, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-lsd",
            "layer_name": "Lahan Sawah Dilindungi (LSD)",
            "clash_area_sqm": round(clash_sawah, 2),
            "description": f"Terdapat tumpang tindih dengan Lahan Sawah Dilindungi (LSD) seluas {clash_sawah:.2f} m²." if clash_sawah > 0
                           else "Clean — tidak ada tumpang tindih dengan Lahan Sawah Dilindungi (LSD).",
            "severity": "danger" if clash_sawah > 0 else "info",
            "zoning_note": "Perpres No. 59/2019 tentang Pengendalian Alih Fungsi Lahan Sawah"
        })

        # 3. Cek Cagar Alam Gumuk Pasir
        query_pasir = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_pasir s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
        """)
        clash_pasir = float(self.db.execute(query_pasir, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-pasir",
            "layer_name": "Kawasan Konservasi Gumuk Pasir",
            "clash_area_sqm": round(clash_pasir, 2),
            "description": f"Terdapat tumpang tindih dengan Kawasan Konservasi Gumuk Pasir seluas {clash_pasir:.2f} m²." if clash_pasir > 0
                           else "Clean — tidak ada tumpang tindih dengan Kawasan Konservasi Gumuk Pasir.",
            "severity": "danger" if clash_pasir > 0 else "info",
            "zoning_note": "UU No. 5/1990 tentang Konservasi SDA Hayati dan Ekosistemnya"
        })

        # 4. Cek Kawasan Perkebunan Aktif
        query_kebun = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_kebun s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
        """)
        clash_kebun = float(self.db.execute(query_kebun, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-kebun",
            "layer_name": "Kawasan Perkebunan Aktif",
            "clash_area_sqm": round(clash_kebun, 2),
            "description": f"Terdapat tumpang tindih dengan Kawasan Perkebunan Aktif seluas {clash_kebun:.2f} m²." if clash_kebun > 0
                           else "Clean — tidak ada tumpang tindih dengan Kawasan Perkebunan Aktif.",
            "severity": "warning" if clash_kebun > 0 else "info",
            "zoning_note": "UU No. 39/2014 tentang Perkebunan"
        })

        # 5. Cek Kawasan Ladang / Pertanian Kering
        query_ladang = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_ladang s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
        """)
        clash_ladang = float(self.db.execute(query_ladang, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-ladang",
            "layer_name": "Kawasan Ladang / Pertanian Kering",
            "clash_area_sqm": round(clash_ladang, 2),
            "description": f"Terdapat tumpang tindih dengan Kawasan Ladang / Pertanian Kering seluas {clash_ladang:.2f} m²." if clash_ladang > 0
                           else "Clean — tidak ada tumpang tindih dengan Kawasan Ladang / Pertanian Kering.",
            "severity": "warning" if clash_ladang > 0 else "info",
            "zoning_note": "UU No. 41/2009 tentang Lahan Pertanian Pangan Berkelanjutan"
        })

        # 6. Cek Zona Peruntukan Pemukiman RDTR
        query_pemukiman = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_pemukiman s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
        """)
        clash_pemukiman = float(self.db.execute(query_pemukiman, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-pemukiman",
            "layer_name": "Zona Peruntukan Pemukiman",
            "clash_area_sqm": round(clash_pemukiman, 2),
            "description": f"Terdapat tumpang tindih dengan Zona Peruntukan Pemukiman seluas {clash_pemukiman:.2f} m²." if clash_pemukiman > 0
                           else "Clean — tidak ada tumpang tindih dengan Zona Peruntukan Pemukiman.",
            "severity": "info",
            "zoning_note": "UU No. 1/2011 tentang Perumahan"
        })

        # 7. Cek Sempadan SUTET 20m (ST_Buffer 20m)
        query_sutet = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, ST_Buffer(s.geom::geography, 20)::geometry)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_sutet s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, ST_Buffer(s.geom::geography, 20)::geometry)
        """)
        clash_sutet = float(self.db.execute(query_sutet, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-sutet",
            "layer_name": "Sempadan SUTET 20m",
            "clash_area_sqm": round(clash_sutet, 2),
            "description": f"Terdapat tumpang tindih dengan sempadan SUTET (buffer 20m) seluas {clash_sutet:.2f} m²." if clash_sutet > 0
                           else "Clean — tidak ada tumpang tindih dengan Jaringan Listrik SUTET.",
            "severity": "danger" if clash_sutet > 0 else "info",
            "zoning_note": "Peraturan Menteri ESDM No. 18/2015"
        })

        # 8. Cek Sempadan Rel Kereta 15m (ST_Buffer 15m)
        query_relka = text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(p.geom, ST_Buffer(s.geom::geography, 15)::geometry)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_relka s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, ST_Buffer(s.geom::geography, 15)::geometry)
        """)
        clash_relka = float(self.db.execute(query_relka, {"id_permohonan": id_permohonan}).scalar() or 0.0)
        results.append({
            "layer_id": "layer-relka",
            "layer_name": "Sempadan Rel Kereta 15m",
            "clash_area_sqm": round(clash_relka, 2),
            "description": f"Terdapat tumpang tindih dengan sempadan rel kereta (buffer 15m) seluas {clash_relka:.2f} m²." if clash_relka > 0
                           else "Clean — tidak ada tumpang tindih dengan Jalur Rel Kereta Commuter Line.",
            "severity": "danger" if clash_relka > 0 else "info",
            "zoning_note": "UU No. 23/2007 tentang Perkeretaapian"
        })

        # 9 & 10. Kemiringan Lereng (Sedang 8-15% dan Curam >15%)
        query_lereng = text("""
            SELECT s.kelas, s.keterangan, COALESCE(SUM(ST_Area(ST_Intersection(p.geom, s.geom)::geography)), 0.0) AS clash_area
            FROM permohonan p, bogor_lereng s
            WHERE p.id_permohonan = :id_permohonan AND ST_Intersects(p.geom, s.geom)
            GROUP BY s.kelas, s.keterangan
        """)
        db_lereng = self.db.execute(query_lereng, {"id_permohonan": id_permohonan}).all()
        
        clash_lereng_sedang = 0.0
        clash_lereng_curam = 0.0
        
        for row in db_lereng:
            if row.kelas == "8-15%":
                clash_lereng_sedang = float(row.clash_area)
            elif row.kelas == ">15%":
                clash_lereng_curam = float(row.clash_area)
                
        results.append({
            "layer_id": "layer-lereng-sedang",
            "layer_name": "Kemiringan Lereng Sedang (8-15%)",
            "clash_area_sqm": round(clash_lereng_sedang, 2),
            "description": f"Terdapat tumpang tindih dengan Kemiringan Lereng Sedang (8-15%) seluas {clash_lereng_sedang:.2f} m²." if clash_lereng_sedang > 0
                           else "Clean — tidak ada tumpang tindih dengan Kemiringan Lereng Sedang (8-15%).",
            "severity": "warning" if clash_lereng_sedang > 0 else "info",
            "zoning_note": "Konstruksi Membutuhkan Pondasi Bore Pile"
        })
        
        results.append({
            "layer_id": "layer-lereng-curam",
            "layer_name": "Kemiringan Lereng Curam (>15%)",
            "clash_area_sqm": round(clash_lereng_curam, 2),
            "description": f"Terdapat tumpang tindih dengan Kemiringan Lereng Curam (>15%) Rawan Longsor seluas {clash_lereng_curam:.2f} m²." if clash_lereng_curam > 0
                           else "Clean — tidak ada tumpang tindih dengan Kemiringan Lereng Curam (>15%).",
            "severity": "danger" if clash_lereng_curam > 0 else "info",
            "zoning_note": "Pembangunan Hunian Dilarang - Rawan Longsor"
        })

        return results
