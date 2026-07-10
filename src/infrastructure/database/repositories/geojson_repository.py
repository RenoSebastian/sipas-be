"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — GeoJSON Repository [geojson_repository.py]
============================================================================
Peran: Menyediakan repositori spasial khusus yang berkohesi tinggi (High Cohesion)
       untuk memproduksi payload standar GeoJSON FeatureCollection secara asinkron.
       Kalkulasi dipindahkan sepenuhnya ke level database (PostGIS native)
       untuk menjamin skalabilitas performa tinggi pada lingkungan lokal.
============================================================================
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

# Inisialisasi Logger Dinas untuk Keperluan Audit Internal
logger = logging.getLogger("sipas-be")


class GeoJsonRepository:
    """
    Repositori Khusus (Pure Fabrication) untuk menangani data spasial
    dan mengekspornya dalam bentuk standar GeoJSON FeatureCollection.
    """

    def __init__(self, db: Session):
        """
        Inisialisasi repositori dengan menyuntikkan sesi database aktif.
        """
        self.db = db

    def get_siteplan_geojson(self, id_permohonan: str) -> Dict[str, Any]:
        """
        Mengambil detail geometri rencana tapak (jalan, kaveling, RTH, PSU)
        dari database dan merakitnya menjadi GeoJSON FeatureCollection terpadu.
        Eksekusi murni dijalankan secara sinkron di level database.
        """
        # Query SQL Native yang memanfaatkan fungsi C-speed dari PostgreSQL & PostGIS
        # ST_AsGeoJSON mengonversi koordinat biner (geom) langsung menjadi string GeoJSON
        query = text("""
            SELECT jsonb_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(jsonb_agg(features.feature), '[]'::jsonb)
            )
            FROM (
                SELECT jsonb_build_object(
                    'type', 'Feature',
                    'id', id,
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', jsonb_build_object(
                        'layer_name', layer_name,
                        -- Penentuan warna deklaratif berdasarkan nama layer arsitek
                        'color', CASE 
                            WHEN layer_name = 'PTSP_KDB' THEN '#475569'       -- Slate tebal untuk kaveling
                            WHEN layer_name = 'PTSP_PSU_JALAN' THEN '#cbd5e1' -- Slate ringan untuk jalan
                            WHEN layer_name = 'PTSP_KDH' THEN '#10b981'       -- Emerald hijau untuk RTH
                            WHEN layer_name = 'PTSP_PSU_MAKAM' THEN '#eab308' -- Amber untuk makam
                            ELSE '#14b8a6'                                   -- Teal default untuk PSU lainnya
                        END,
                        'fillOpacity', CASE 
                            WHEN layer_name = 'PTSP_PSU_JALAN' THEN 0.45
                            ELSE 0.65
                        END
                    )
                ) AS feature
                FROM site_plan_geometries
                WHERE id_permohonan = :id_permohonan
            ) f;
        """)

        try:
            # Eksekusi query dengan parameter terikat untuk mencegah celah SQL Injection
            raw_result = self.db.execute(query, {"id_permohonan": id_permohonan}).scalar()
            
            if not raw_result:
                logger.warning(f"[GEOJSON_REPO] Data spasial untuk ID Permohonan '{id_permohonan}' kosong.")
                return {"type": "FeatureCollection", "features": []}

            # PostgreSQL jsonb_build_object otomatis mengembalikan tipe data dict pada driver psycopg2
            if isinstance(raw_result, str):
                return json.loads(raw_result)
                
            return raw_result

        except Exception as e:
            logger.error(
                f"[GEOJSON_REPO_ERROR] Gagal mengompilasi GeoJSON dari PostGIS "
                f"untuk ID '{id_permohonan}': {str(e)}", 
                exc_info=True
            )
            raise RuntimeError(f"Gagal memproses visualisasi GeoJSON dari database: {str(e)}")

    async def get_siteplan_geojson_async(self, id_permohonan: str) -> Dict[str, Any]:
        """
        Menjembatani pemanggilan sinkron repositori database agar berjalan secara 
        asinkron (non-blocking) di dalam ThreadPool FastAPI menggunakan asyncio.
        Mencegah pemblokiran event loop utama saat database memproses geometri besar.
        """
        logger.debug(f"[GEOJSON_REPO] Memulai pemrosesan asinkron GeoJSON untuk ID: {id_permohonan}")
        return await asyncio.to_thread(self.get_siteplan_geojson, id_permohonan)