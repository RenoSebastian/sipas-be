"""
============================================================================
SIPAS BACKEND — Database Connection Adapter [connection.py]
============================================================================
Peran: Menginisialisasi mesin SQLAlchemy 2.0, membuat session maker,
       dan menyediakan dependency generator get_db() untuk disuntikkan
       ke controller HTTP secara aman.
============================================================================
"""

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("sipas-be")

# 1. Membaca URL Database dari Environment Variable (.env) [sipas-fe.txt]
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:naufal@localhost:5432/sipas_db"
)

# 2. Membuat Engine Koneksi Database
# Mengaktifkan pool_pre_ping=True untuk mendeteksi secara dini jika koneksi terputus (Anti-Jitter)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600, # Recycle koneksi setiap 1 jam untuk menghemat memori server
    echo=False         # Set ke True jika ingin mencetak SQL query asli di terminal saat debug
)

# 3. Membuat SessionLocal Factory
# Menggunakan model transaksional eksplisit (autocommit=False, autoflush=False)
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# 4. Membuat Base Declarative Class untuk Mapping Model Database
Base = declarative_base()

# ─── SECTION: DEPENDENCY INJECTION GENERATOR (get_db) ─────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Generator Sesi Database (FastAPI Dependency).
    Menjamin bahwa setiap request HTTP mendapatkan satu sesi database terisolasi,
    dan sesi tersebut WAJIB ditutup secara aman saat request selesai diproses.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"[DB_TRANSACTION_ERROR] Terjadi kegagalan transaksi, database rollback dipicu: {str(e)}")
        db.rollback()
        raise e
    finally:
        db.close()


# Import Ports and Adapters to enable dynamic dependency injection [sipas-fe.txt]
from src.use_cases.ports.integration_ports import BpnValidationPort, OssSyncPort, SimtaruSyncPort
from src.infrastructure.adapters.mock_integrations import MockBpnAdapter, MockOssAdapter, MockSimtaruAdapter

def get_bpn_port() -> BpnValidationPort:
    return MockBpnAdapter()

def get_oss_port() -> OssSyncPort:
    return MockOssAdapter()

def get_simtaru_port() -> SimtaruSyncPort:
    return MockSimtaruAdapter()