"""seed_spatial_bylaws

Revision ID: 1ddfa8438d38b
Revises: 08830d8c7079
Create Date: 2026-07-08 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '1ddfa8438d39'
down_revision: Union[str, Sequence[str], None] = '08830d8c7079'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── TAHAP 1: AKTIFKAN EKSTENSI POSTGIS (Zero Trust Setup) ───
    # Memastikan ekstensi PostGIS aktif pada PostgreSQL tujuan
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))

    # ─── TAHAP 2: PEMBUATAN TABEL RONA WILAYAH KABUPATEN BOGOR (PostGIS Core) ───
    # Tabel 1: Aliran Sungai Aktif (LINESTRING / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_sungai (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(LineString, 4326) NOT NULL
        )
    """))

    # Tabel 2: Lahan Sawah Dilindungi - LSD (POLYGON / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_sawah (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # Tabel 3: Kawasan Konservasi Gumuk Pasir (POLYGON / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_pasir (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # Tabel 4: Kawasan Perkebunan Aktif (POLYGON / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_kebun (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # Tabel 5: Kawasan Ladang / Pertanian Kering (POLYGON / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_ladang (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # Tabel 6: Zona Peruntukan Permukiman RDTR (POLYGON / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_pemukiman (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # Tabel 7: Koridor Jaringan Udara Tegangan Ekstra Tinggi - SUTET (LINESTRING / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_sutet (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(LineString, 4326) NOT NULL
        )
    """))

    # Tabel 8: Ruang Milik Jalan Rel Kereta Api (LINESTRING / EPSG:4326)
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_relka (
            id SERIAL PRIMARY KEY,
            nama VARCHAR(255) NOT NULL,
            geom geometry(LineString, 4326) NOT NULL
        )
    """))

    # Tabel 9: Peta Kelas Lereng Bappeda (POLYGON / EPSG:4326) [Bappeda 2]
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bogor_lereng (
            id SERIAL PRIMARY KEY,
            kelas VARCHAR(50) NOT NULL,              -- e.g., '0-8%', '8-15%', '>15%'
            keterangan VARCHAR(255) NOT NULL,        -- Datar, Sedang, Curam
            geom geometry(Polygon, 4326) NOT NULL
        )
    """))

    # ─── TAHAP 3: DAFTARKAN INDEKS SPASIAL GIST (Anti-Performance Lag) ───
    # Pengindeksan spasial wajib didaftarkan agar kueri irisan ST_Intersection instan (<10ms)
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_sungai_geom ON bogor_sungai USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_sawah_geom ON bogor_sawah USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_pasir_geom ON bogor_pasir USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_kebun_geom ON bogor_kebun USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_ladang_geom ON bogor_ladang USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_pemukiman_geom ON bogor_pemukiman USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_sutet_geom ON bogor_sutet USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_relka_geom ON bogor_relka USING GIST (geom)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_bogor_lereng_geom ON bogor_lereng USING GIST (geom)"))


    # ─── TAHAP 4: PENYEMAIAN DATA GEOSPASIAL ACUAN KABUPATEN BOGOR (Seeding) ───
    # Data koordinat bumi asli diletakkan beririsan secara taktis dengan data uji (Cibinong, Sentul, Gunung Putri)
    
    # 1. Aliran Sungai Cileungsi (Melintas dekat Bojonggede & Gunung Putri)
    op.execute(sa.text("""
        INSERT INTO bogor_sungai (nama, geom) VALUES (
            'Sungai Cileungsi Hulu', 
            ST_GeomFromText('LINESTRING(106.8400 -6.4800, 106.8415 -6.4815, 106.8430 -6.4830)', 4326)
        )
    """))

    # 2. Lahan Sawah Dilindungi - LSD (Menguji kegagalan paksa Kasus 5 - Gunung Putri)
    op.execute(sa.text("""
        INSERT INTO bogor_sawah (nama, geom) VALUES (
            'Kawasan Sawah Irigasi Teknis Gunung Putri', 
            ST_GeomFromText('POLYGON((106.8980 -6.4180, 106.9050 -6.4180, 106.9050 -6.4250, 106.8980 -6.4250, 106.8980 -6.4180))', 4326)
        )
    """))

    # 3. Konservasi Alam / Gumuk Pasir
    op.execute(sa.text("""
        INSERT INTO bogor_pasir (nama, geom) VALUES (
            'Cagar Alam Gumuk Pasir Klapanunggal', 
            ST_GeomFromText('POLYGON((106.9500 -6.3700, 106.9550 -6.3700, 106.9550 -6.3750, 106.9500 -6.3750, 106.9500 -6.3700))', 4326)
        )
    """))

    # 4. Kawasan Perkebunan
    op.execute(sa.text("""
        INSERT INTO bogor_kebun (nama, geom) VALUES (
            'Perkebunan Karet Hambalang Citeureup', 
            ST_GeomFromText('POLYGON((106.8500 -6.4500, 106.8600 -6.4500, 106.8600 -6.4600, 106.8500 -6.4600, 106.8500 -6.4500))', 4326)
        )
    """))

    # 5. Kawasan Ladang Kering
    op.execute(sa.text("""
        INSERT INTO bogor_ladang (nama, geom) VALUES (
            'Ladang Pertanian Kering Bojonggede', 
            ST_GeomFromText('POLYGON((106.7900 -6.4900, 106.8050 -6.4900, 106.8050 -6.4990, 106.7900 -6.4990, 106.7900 -6.4900))', 4326)
        )
    """))

    # 6. Jaringan Listrik SUTET (Batas aman sempadan SUTET 20m)
    op.execute(sa.text("""
        INSERT INTO bogor_sutet (nama, geom) VALUES (
            'Jalur SUTET PLN Cibinong-Muaratawar', 
            ST_GeomFromText('LINESTRING(106.8380 -6.4800, 106.8410 -6.4810, 106.8440 -6.4820)', 4326)
        )
    """))

    # 7. Jalur Rel Kereta Commuter Line Bojonggede (Sempadan rel kereta 15m)
    op.execute(sa.text("""
        INSERT INTO bogor_relka (nama, geom) VALUES (
            'Lintasan KAI Commuter Line Jakarta-Bogor', 
            ST_GeomFromText('LINESTRING(106.7980 -6.4950, 106.8010 -6.4960, 106.8040 -6.4970)', 4326)
        )
    """))

    # 8. Peta Kelas Lereng Bappeda (Menguji kelaikan kemiringan lereng) [Bappeda 2]
    # Seeding Kelas Lereng Sedang (8-15%)
    op.execute(sa.text("""
        INSERT INTO bogor_lereng (kelas, keterangan, geom) VALUES (
            '8-15%', 
            'Kemiringan Lereng Sedang - Konstruksi Membutuhkan Pondasi Bore Pile', 
            ST_GeomFromText('POLYGON((106.8150 -6.5940, 106.8200 -6.5940, 106.8200 -6.5990, 106.8150 -6.5990, 106.8150 -6.5940))', 4326)
        )
    """))
    # Seeding Kelas Lereng Curam (>15%)
    op.execute(sa.text("""
        INSERT INTO bogor_lereng (kelas, keterangan, geom) VALUES (
            '>15%', 
            'Kemiringan Lereng Curam - Rawan Longsor - Pembangunan Hunian Dilarang', 
            ST_GeomFromText('POLYGON((106.8650 -6.5550, 106.8750 -6.5550, 106.8750 -6.5650, 106.8650 -6.5650, 106.8650 -6.5550))', 4326)
        )
    """))


def downgrade() -> None:
    # ─── HAPUS TABEL SPASIAL ───
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_lereng CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_relka CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_sutet CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_pemukiman CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_ladang CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_kebun CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_pasir CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_sawah CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS bogor_sungai CASCADE"))