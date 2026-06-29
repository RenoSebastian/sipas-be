"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — GeoServer REST Client [geoserver_client.py]
============================================================================
Peran: Mengimplementasikan GeoServerPort menggunakan HTTP REST Client.
       Berkomunikasi dengan GeoServer untuk mempublikasikan, memutakhirkan
       metadata bBox, dan me-refresh cache layer spasial tunggal 
       `site_plan_geometries` Kabupaten Bogor [Bogor 3].
============================================================================
"""

import os
import requests
import logging
from requests.auth import HTTPBasicAuth

from src.use_cases.calibrate_cad import GeoServerPort

logger = logging.getLogger("sipas-be")

class GeoServerClient(GeoServerPort):
    def __init__(self):
        # Membaca konfigurasi dari environment variables (.env) [sipas-fe.txt]
        self.geoserver_url = os.getenv("GEOSERVER_URL", "http://localhost:8080/geoserver")
        self.username = os.getenv("GEOSERVER_USER", "admin")
        self.password = os.getenv("GEOSERVER_PASSWORD", "geoserver")
        self.workspace = os.getenv("GEOSERVER_WORKSPACE", "sipas_bogor")
        self.datastore = os.getenv("GEOSERVER_DATASTORE", "postgis_store")
        
        # Nama layer global spasial tunggal sesuai standardisasi PostGIS [sipas-be.txt]
        self.global_layer = "site_plan_geometries"
        
        # Konfigurasi otentikasi dasar GeoServer
        self.auth = HTTPBasicAuth(self.username, self.password)
        self.headers = {"Content-Type": "application/json"}

    def publish_submission_layers(self, id_permohonan: str) -> None:
        """
        Memerintahkan GeoServer untuk menyelaraskan koordinat dan me-refresh cache
        ubin peta spasial global terkait data permohonan terkalibrasi [Bogor 3, 5].
        """
        logger.info(f"[GEOSERVER] Menyiapkan sinkronisasi visual peta untuk permohonan ID: {id_permohonan}")

        # Endpoint untuk mendeteksi / mempublikasikan FeatureType global dari PostGIS [Bogor 3]
        base_endpoint = f"{self.geoserver_url}/rest/workspaces/{self.workspace}/datastores/{self.datastore}/featuretypes"
        check_endpoint = f"{base_endpoint}/{self.global_layer}.json"

        try:
            # 1. Pengecekan Eksistensi: Periksa apakah layer global sudah terpublikasikan di GeoServer
            response = requests.get(check_endpoint, auth=self.auth, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"[GEOSERVER] Layer global '{self.global_layer}' sudah aktif. Memicu kalkulasi ulang bounding box...")
                self._recalculate_layer_bounds()
            else:
                logger.info(f"[GEOSERVER] Layer global '{self.global_layer}' belum terpublikasi. Memulai registrasi layer...")
                self._register_global_layer(base_endpoint)

            # 2. Pembersihan Cache Visual: Bersihkan tile cache GeoWebCache agar peta ter-update secara real-time
            self._trigger_tile_cache_clear()

        except requests.exceptions.Timeout:
            logger.error("[GEOSERVER_TIMEOUT] GeoServer REST API tidak merespons dalam batasan waktu tunggu.")
            return
        except Exception as e:
            logger.error(f"[GEOSERVER_CRASH] Gagal berkomunikasi dengan GeoServer: {str(e)}", exc_info=True)
            return

    def _register_global_layer(self, endpoint: str) -> None:
        """Mendaftarkan (POST) tabel site_plan_geometries sebagai layer WMS/WFS pertama kali di GeoServer."""
        payload = {
            "featureType": {
                "name": self.global_layer,
                "title": "Rencana Tapak Spasial Global - GEOSIPAS",
                "nativeSRS": "EPSG:4326",
                "srs": "EPSG:4326",
                "projectionPolicy": "FORCE_DECLARED",
                "enabled": True
            }
        }
        
        response = requests.post(endpoint, auth=self.auth, headers=self.headers, json=payload, timeout=10)
        
        if response.status_code == 201:
            logger.info(f"[GEOSERVER] Sukses meregistrasikan layer spasial '{self.global_layer}' ke WMS/WFS.")
        else:
            logger.warning(f"[GEOSERVER_WARNING] GeoServer menolak pendaftaran layer baru: {response.text}")

    def _recalculate_layer_bounds(self) -> None:
        """
        Memaksa GeoServer memperbarui metadata spasial dan menghitung ulang bounding box (bBox)
        tabel PostgreSQL setelah adanya penambahan poligon koordinat baru [Bogor 3].
        """
        # Perintah PUT dengan query 'recalculate' adalah standard industri GIS untuk meng-update batas koordinat peta
        recalculate_url = (
            f"{self.geoserver_url}/rest/workspaces/{self.workspace}/datastores/{self.datastore}/"
            f"featuretypes/{self.global_layer}?recalculate=nativebBox,latLonbBox"
        )
        
        # Kirim PUT request kosong ke GeoServer REST
        response = requests.put(recalculate_url, auth=self.auth, headers=self.headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"[GEOSERVER] Sukses melakukan kalkulasi ulang bounding box untuk layer '{self.global_layer}'.")
        else:
            logger.warning(f"[GEOSERVER_WARNING] Gagal memperbarui bBox layer: {response.text}")

    def _trigger_tile_cache_clear(self) -> None:
        """Memerintahkan GeoWebCache untuk membersihkan seluruh ubin peta lama (Anti-Jittering Visual)."""
        gwc_endpoint = f"{self.geoserver_url}/gwc/rest/masstruncate"
        
        payload = f"""
        <truncateLayer>
           <layerName>{self.workspace}:{self.global_layer}</layerName>
        </truncateLayer>
        """
        xml_headers = {"Content-Type": "text/xml"}
        
        try:
            response = requests.post(gwc_endpoint, auth=self.auth, headers=xml_headers, data=payload, timeout=5)
            if response.status_code == 200:
                logger.info(f"[GEOSERVER] Cache ubin GeoWebCache untuk layer '{self.global_layer}' berhasil dibersihkan.")
        except Exception as e:
            logger.warning(f"[GEOSERVER_WARNING] Gagal membersihkan cache GWC: {str(e)}")