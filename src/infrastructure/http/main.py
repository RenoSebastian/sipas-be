"""
============================================================================
SIPAS BACKEND — HTTP Entry Adapter [main.py]
============================================================================
Peran: Bertindak sebagai Front Controller utama untuk menginisialisasi
       FastAPI, mengonfigurasi CORS, mendaftarkan router modular, dan
       menangani pengecualian global sistem secara terpusat.
============================================================================
"""

from dotenv import load_dotenv
# Load environment variables dynamically at startup
load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.infrastructure.http.routes.submissions import router as submissions_router
import logging

from src.domain.exceptions import SpatialValidationError

# Inisialisasi Logger Dinas untuk Keperluan Audit Trail [Bogor 7]
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sipas-be")

# 1. Inisialisasi Aplikasi Utama FastAPI
app = FastAPI(
    title="GEOSIPAS API",
    description="Sistem Informasi Pelayanan Pengesahan Site Plan Digital Kabupaten Bogor",
    version="1.0.0",
    docs_url="/api/docs",      # Swagger UI Endpoint
    redoc_url="/api/redoc",    # Redoc Endpoint
)

# 2. Konfigurasi Keamanan CORS (Cross-Origin Resource Sharing) [sipas-fe.txt]
# Menghindari wildcard '*' di produksi untuk mencegah celah keamanan.
ORIGINS = [
    "http://localhost:5173",  # Port standar Vite Pemohon [sipas-fe.txt]
    "http://127.0.0.1:5173",
    # Daftarkan domain produksi dinas di sini kelak
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# ─── SECTION: PROTECTED VARIATIONS (EXCEPTION HANDLERS) ───────────────────

@app.exception_handler(SpatialValidationError)
async def spatial_validation_exception_handler(request: Request, exc: SpatialValidationError):
    """Menangani error jika koordinat CAD atau SHP tidak valid atau melanggar Perda."""
    logger.warning(f"[SPATIAL_ERROR] Pelanggaran Spasial pada {request.url.path}: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "FAILED_SPATIAL_VALIDATION",
            "message": exc.message,
            "detail": exc.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Menangani kegagalan tipe data DTO / Skema Pydantic."""
    logger.warning(f"[VALIDATION_ERROR] Kegagalan skema data pada {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "VALIDATION_ERROR",
            "message": "Struktur data yang dikirimkan tidak sesuai dengan kontrak API.",
            "detail": exc.errors()
        }
    )
 
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Menangkap seluruh internal server crash (Anti-Smell Code)."""
    logger.error(f"[SYSTEM_CRASH] Kegagalan fatal pada {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "INTERNAL_SERVER_ERROR",
            "message": "Terjadi kesalahan internal pada server kami. Skenario crash telah direkam di sistem audit log.",
            "detail": str(exc) if app.debug else None
        }
    )

# ─── SECTION: ENDPOINTS & ROUTES ──────────────────────────────────────────

@app.get("/api/v1/health", tags=["System Health"])
async def health_check():
    """Endpoint verifikasi kesehatan sistem untuk monitoring."""
    return {
        "status": "HEALTHY",
        "service": "GEOSIPAS-BE",
        "database": "CONNECTED",  # Nanti disinkronkan dengan pemeriksaan DB asli
        "version": "1.0.0"
    }

app.include_router(submissions_router)
# Seluruh router dari folder http/routes akan didaftarkan di bawah ini kelak:
# app.include_router(submissions.router, prefix="/api/v1")