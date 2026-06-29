"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Background Task Runner [tasks.py]
============================================================================
Peran: Menggantikan fungsi Celery Worker dengan thread independen di dalam
       proses aplikasi utama menggunakan FastAPI BackgroundTasks.
       Membaca CAD lokal, mentranslasikannya ke koordinat bumi WGS84
       berdasarkan parameter titik ikat yang dikirim secara dinamis, 
       menyimpannya ke tabel spasial PostGIS, lalu mengaktifkan sinkronisasi 
       WMS/WFS di GeoServer pasca-transaksi database selesai.
============================================================================
"""

import os
import logging
from typing import Dict, Any, Tuple
from pathlib import Path

from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import SitePlanGeometryModel
from src.domain.value_objects.spatial_params import solveHelmert2D, HelmertParameters
from src.infrastructure.gis.cad_parser import CadParser
from src.infrastructure.gis.geoserver_client import GeoServerClient

# Inisialisasi Logger Dinas
logger = logging.getLogger("sipas-be")

def execute_cad_parsing_background(
    file_path: str,
    id_permohonan: str,
    anchor_cad_1: Tuple[float, float] = (0.0, 0.0),
    anchor_cad_2: Tuple[float, float] = (100.0, 100.0),
    anchor_map_1: Tuple[float, float] = (106.8272, -6.5971),
    anchor_map_2: Tuple[float, float] = (106.8295, -6.5990),
) -> Dict[str, Any]:
    """
    Mengeksekusi parsing file CAD secara asinkron di dalam ThreadPool FastAPI.
    Fungsi ini dipanggil oleh endpoint HTTP untuk melakukan komputasi berat
    tanpa menghalangi (blocking) I/O request user lain.

    Menerima parameter koordinat jangkar dinamis dari Frontend untuk menghasilkan
    perhitungan matriks Helmert 2D yang akurat dan tepat sasaran [Jakarta 5].
    """
    logger.info(f"[BG_TASK] Memulai pemrosesan asinkron untuk berkas CAD permohonan ID: {id_permohonan}")

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        error_msg = f"Berkas CAD tidak ditemukan pada jalur fisik: {file_path}"
        logger.error(f"[BG_TASK_ERROR] {error_msg}")
        return {"status": "FAILED", "error": error_msg}

    db = SessionLocal()
    try:
        # 1. Ekstrak data mentah koordinat lokal dari berkas CAD
        parser = CadParser()
        raw_cad_layers = parser.parse_and_extract_layers(file_path)

        # 2. Perhitungan dinamis parameter Helmert 2D berdasarkan penambat aktual kiriman user [Jakarta 5]
        # Menghapus keterikatan statis (hardcoded) demi kepatuhan terhadap prinsip Protected Variations
        helmert_res = solveHelmert2D(
            p1=anchor_cad_1,
            p2=anchor_cad_2,
            P1=anchor_map_1,
            P2=anchor_map_2
        )
        transform_params = HelmertParameters(
            A=helmert_res["A"], B=helmert_res["B"],
            Tx=helmert_res["Tx"], Ty=helmert_res["Ty"],
            scale=helmert_res["scale"], rotation_rad=helmert_res["rotation"]
        )

        # 3. Hapus data spasial lama milik permohonan ini jika ada (Idempotent)
        db.query(SitePlanGeometryModel).filter(SitePlanGeometryModel.id_permohonan == id_permohonan).delete()

        # 4. Transformasikan titik lokal CAD dan simpan fisiknya ke PostGIS
        saved_count = 0
        for layer_name, polylines in raw_cad_layers.items():
            for polyline in polylines:
                # Lakukan transformasi Helmert 2D ke WGS84 per titik
                calibrated_coords = []
                for x, y in polyline:
                    world_coord = transform_params.transform(x, y)
                    calibrated_coords.append((world_coord.longitude, world_coord.latitude))

                # Pastikan poligon tertutup secara matematis
                if calibrated_coords[0] != calibrated_coords[-1]:
                    calibrated_coords.append(calibrated_coords[0])

                # Konversi menjadi objek geometri spasial PostGIS menggunakan Shapely
                shapely_polygon = Polygon(calibrated_coords)
                spatial_record = SitePlanGeometryModel(
                    id_permohonan=id_permohonan,
                    layer_name=layer_name,
                    geom=from_shape(shapely_polygon, srid=4326)
                )
                db.add(spatial_record)
                saved_count += 1

        # 5. Eksekusi komit transaksi database fisik PostGIS
        db.commit()
        logger.info(f"[BG_TASK] Sukses menyimpan {saved_count} poligon spasial terkalibrasi ke database PostGIS.")

        # 6. SINKRONISASI GEOSERVER (Menyelesaikan Race Condition)
        # Menjalankan pemanggilan layer publikasi di GeoServer HANYA setelah
        # data biner fisik koordinat benar-benar sukses dikomit di dalam database [Bogor 3]
        try:
            logger.info(f"[BG_TASK] Memicu publikasi layer peta di GeoServer untuk permohonan ID: {id_permohonan}")
            geoserver_client = GeoServerClient()
            geoserver_client.publish_submission_layers(id_permohonan)
            logger.info(f"[BG_TASK] Sinkronisasi visual GeoServer berhasil dilewati.")
        except Exception as geoserver_error:
            # Sesuai prinsip Protected Variations, kegagalan integrasi eksternal
            # tidak boleh menggagalkan status keberhasilan komit database internal
            logger.error(f"[BG_TASK_WARNING] Sinkronisasi GeoServer gagal namun data spasial internal aman: {str(geoserver_error)}")

        return {
            "status": "SUCCESS",
            "id_permohonan": id_permohonan,
            "polygons_saved": saved_count
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[BG_TASK_CRASH] Gagal memproses spasial: {str(e)}", exc_info=True)
        return {"status": "FAILED", "error": str(e)}
    finally:
        db.close()