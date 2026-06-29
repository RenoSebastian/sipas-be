"""
============================================================================
SIPAS DATABASE UTILITY — Spatial Database Seeder [seed.py]
============================================================================
Peran: Mengisi database lokal PostgreSQL/PostGIS dengan data spasial awal
       (WGS84 / SRID 4326) di wilayah rona Kabupaten Bogor, sekaligus
       menyemai data kredensial pengguna awal (users) untuk kebutuhan
       autentikasi JWT terintegrasi.
============================================================================
"""

import sys
import os
from datetime import date, datetime

# Sisipkan direktori root proyek ke dalam sys.path agar aman dijalankan dari terminal mana pun
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.security.auth import hash_password  # Mengimpor modul hashing password
from src.infrastructure.database.models import (
    UserModel,
    PermohonanModel,
    LahanKompensasiModel,
    AuditTrailModel,
    SitePlanGeometryModel
)

def clear_existing_data(db) -> None:
    """Membersihkan database dari data lama agar seeder bersifat Idempotent (Anti-Duplikasi)."""
    print("[SEEDER] Memulai pembersihan tabel database...")
    try:
        db.query(AuditTrailModel).delete()
        db.query(LahanKompensasiModel).delete()
        db.query(SitePlanGeometryModel).delete()
        db.query(PermohonanModel).delete()
        db.query(UserModel).delete()  # Bersihkan tabel user lama
        db.commit()
        print("[SEEDER] Sukses membersihkan tabel fisik database.")
    except Exception as e:
        db.rollback()
        print(f"[SEEDER_ERROR] Gagal membersihkan database: {str(e)}")
        sys.exit(1)

def seed_spatial_data() -> None:
    """Menyemai data user dan spasial WGS84 nyata wilayah Kabupaten Bogor."""
    db = SessionLocal()
    clear_existing_data(db)

    print("[SEEDER] Memulai penyemaian data baru...")
    try:
        # ──────────────────────────────────────────────────────────────────────
        # TAHAP 1: PENYEMAIAN DATA USER SIMULASI (Sesuai Kredensial Frontend)
        # Password default semua user diset seragam: "password123"
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data kredensial user baru...")
        default_password_hash = hash_password("password123")
        
        users = [
            UserModel(
                username="ahmad_fauzi",
                email="fauzi@ptmajusentosa.com",
                hashed_password=default_password_hash,
                full_name="Ahmad Fauzi",
                role="PEMOHON",
                is_active=True
            ),
            UserModel(
                username="siti_rahma",
                email="siti.rahma@sipas.go.id",
                hashed_password=default_password_hash,
                full_name="Siti Rahma",
                role="ADMIN",
                is_active=True
            ),
            UserModel(
                username="budi_santoso",
                email="budi.teknis@sipas.go.id",
                hashed_password=default_password_hash,
                full_name="Ir. Budi Santoso",
                role="TIM_TEKNIS",
                is_active=True
            ),
            UserModel(
                username="hendra_wijaya",
                email="hendra.kabid@sipas.go.id",
                hashed_password=default_password_hash,
                full_name="Dr. Hendra Wijaya",
                role="KABID_PUPR",
                is_active=True
            )
        ]
        
        for user in users:
            db.add(user)
        db.commit() # Commit agar ID User ter-generate secara transaksional
        print(f"[SEEDER] Sukses mendaftarkan {len(users)} user simulasi ke database.")

        # Ambil reference user_id untuk relasi permohonan
        pemohon_user = db.query(UserModel).filter(UserModel.username == "ahmad_fauzi").first()
        pemohon_id = pemohon_user.id if pemohon_user else None

        # ──────────────────────────────────────────────────────────────────────
        # TAHAP 2: PENYEMAIAN DATA SPASIAL PERMOHONAN & KOMPENSASI
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data spasial permohonan dan kompensasi...")

        # KASUS 1: Grand Bogor Residence (Status: Menunggu Verifikasi)
        # Batas luar bidang tanah BPN (WGS84)
        outer_poly_1 = Polygon([
            (106.8160, -6.5945),
            (106.8175, -6.5945),
            (106.8175, -6.5960),
            (106.8160, -6.5960),
            (106.8160, -6.5945)
        ])

        permohonan_1 = PermohonanModel(
            id_permohonan="sub-1",
            user_id=pemohon_id, # Hubungkan relasi user secara asing (Foreign Key)
            submission_no="SIPAS-2026-001",
            housing_name="Grand Bogor Residence",
            developer_name="PT Maju Jaya Sentosa (Ahmad Fauzi)",
            land_area=25000.0,
            submission_date=date(2026, 6, 20),
            status="Menunggu Verifikasi",
            buffer_sla=0,
            elapsed_days=0,

            # TAHAP 1: DATA PEMOHON
            applicant_type="BADAN_USAHA",
            applicant_name="PT Maju Jaya Sentosa",
            applicant_nik=None,
            applicant_nib="9120301938192",
            applicant_npwp="01.234.567.8-901.000",
            applicant_director_name="Ahmad Fauzi",
            applicant_phone="081234567890",
            applicant_email="fauzi@ptmajusentosa.com",
            applicant_address="Gedung Sentosa Lt. 4, Jl. Jend. Sudirman No. 10, Jakarta Pusat",

            # TAHAP 2: DATA PENGAJUAN
            submission_type="BARU",
            submission_category="PERUMAHAN",

            # TAHAP 3: DATA LOKASI & TANAH
            location_name="Lahan Baranangsiang",
            location_village="Baranangsiang",
            location_district="Bogor Timur",
            location_city="Kota Bogor",
            location_province="Jawa Barat",
            location_full_address="Jl. Raya Pajajaran No.21, Baranangsiang, Kec. Bogor Timur, Kota Bogor, Jawa Barat",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 10293/Baranangsiang",
            location_certificate_owner="PT Maju Jaya Sentosa",

            # TAHAP 4: GEOMETRI BIDANG LUAR BPN & HELMERT
            geom=from_shape(outer_poly_1, srid=4326),
            cad_file_name="blueprint_grand_bogor.dxf",
            cad_param_a=0.8875,
            cad_param_b=0.4612,
            cad_param_tx=106.816629,
            cad_param_ty=-6.595189,
            cad_scale=1.0024,
            cad_rotation=0.4812,

            # TAHAP 5: TATA RUANG
            spatial_kkpr_number="503/KKPR/PUPR/2026/089",
            spatial_land_use="Zona Perumahan Kepadatan Sedang",
            spatial_green_area=3850.0,

            # TAHAP 6: PARAMETER TEKNIS (PERUMAHAN)
            tech_lot_count=120,
            tech_housing_type="NON_SUBSIDI",
            tech_cemetery_area=500.0,
            tech_road_row_main="12 Meter",
            tech_road_row_local="8 Meter",
            tech_water_system="PDAM Tirta Pakuan",

            # TAHAP 7: KONSULTAN
            consultant_name="Ir. Hermawan Pratama",
            consultant_company_name="CV Rencana Semesta",
            consultant_pic_name="Hermawan Pratama",

            # TAHAP 9: URL DOKUMENTASI FOTO JALAN / RONAL AWAL
            photo_north="https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            photo_south="https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            photo_east="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            photo_west="https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            photo_access="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80",

            # TAHAP 10: PERNYATAAN PEMOHON
            statement_agreed=True
        )
        db.add(permohonan_1)

        # Poligon KDB Internal Rencana (Site Plan Geometries)
        poly_kdb_1 = Polygon([
            (106.8160, -6.5945),
            (106.8175, -6.5945),
            (106.8175, -6.5960),
            (106.8160, -6.5960),
            (106.8160, -6.5945)
        ])
        geom_kdb_1 = SitePlanGeometryModel(
            id_permohonan="sub-1",
            layer_name="PTSP_KDB",
            geom=from_shape(poly_kdb_1, srid=4326)
        )
        db.add(geom_kdb_1)

        # Lahan Kompensasi Makam Fisik 2% (Perbaikan Typo Enum)
        kompensasi_1 = LahanKompensasiModel(
            id_kompensasi="komp-101",
            id_permohonan="sub-1",
            tipe_kompensasi="LAHAN_MAKAM_FISIK",
            luas_kompensasi_m2=500.0,
            geom=from_shape(Polygon([
                (106.8155, -6.5940),
                (106.8160, -6.5940),
                (106.8160, -6.5945),
                (106.8155, -6.5945),
                (106.8155, -6.5940)
            ]), srid=4326),
            status_pemenuhan="PROSES_VERIFIKASI",
            nilai_nominal=0.0,
            bukti_legalitas_url="https://sipas.bogor.go.id/sertifikat/komp-101.pdf"
        )
        db.add(kompensasi_1)

        # Log audit perdana pendaftaran berkas
        audit_1 = AuditTrailModel(
            submission_id="sub-1",
            actor_name="Ahmad Fauzi",
            role="Pemohon",
            action="SUBMIT_UNIFIED_FORM",
            status_before="Draft",
            status_after="Menunggu Verifikasi",
            notes="Berkas pendaftaran awal tipe 'Site Plan' berhasil didaftarkan secara mandiri melalui satu pintu.",
            created_at=datetime(2026, 6, 20, 9, 30, 0)
        )
        db.add(audit_1)

        # KASUS 2: Batu Tulis Residence (Status: Ditolak / Butuh Revisi)
        outer_poly_2 = Polygon([
            (106.8105, -6.6205),
            (106.8120, -6.6205),
            (106.8120, -6.6220),
            (106.8105, -6.6220),
            (106.8105, -6.6205)
        ])

        permohonan_2 = PermohonanModel(
            id_permohonan="sub-5",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-005",
            housing_name="Batu Tulis Residence",
            developer_name="PT Jaya Real Estate (Ir. Heru Prasetyo)",
            land_area=12000.0,
            submission_date=date(2026, 6, 8),
            status="Ditolak",
            buffer_sla=0,
            elapsed_days=2,

            # TAHAP 1: DATA PEMOHON
            applicant_type="BADAN_USAHA",
            applicant_name="PT Jaya Real Estate",
            applicant_nik=None,
            applicant_nib="8120304918273",
            applicant_npwp="01.333.444.5-666.000",
            applicant_director_name="Ir. Heru Prasetyo",
            applicant_phone="081255556666",
            applicant_email="heru.p@jayarealestate.com",
            applicant_address="Jaya Tower Lt. 12, Jl. MH Thamrin No. 8, Jakarta Pusat",

            # TAHAP 2: DATA PENGAJUAN
            submission_type="BARU",
            submission_category="NON_PERUMAHAN",

            # TAHAP 3: DATA LOKASI & TANAH
            location_name="Lahan Batu Tulis",
            location_village="Batutulis",
            location_district="Bogor Selatan",
            location_city="Kota Bogor",
            location_province="Jawa Barat",
            location_full_address="Batu Tulis, Kec. Bogor Selatan, Kota Bogor, Jawa Barat",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 673/Batutulis",
            location_certificate_owner="Ir. Heru Prasetyo",

            # TAHAP 4: GEOMETRI BIDANG LUAR BPN
            geom=from_shape(outer_poly_2, srid=4326),
            cad_file_name="blueprint_batu_tulis.dxf",
            cad_param_a=0.9125,
            cad_param_b=0.3812,
            cad_param_tx=106.811234,
            cad_param_ty=-6.621234,
            cad_scale=1.0012,
            cad_rotation=0.3512,

            # TAHAP 5: TATA RUANG
            spatial_kkpr_number="503/KKPR/PUPR/2026/304",
            spatial_land_use="Zona Cagar Budaya & Resapan Air",
            spatial_green_area=1452.0,

            # TAHAP 6: PARAMETER TEKNIS (NON-PERUMAHAN)
            tech_building_blocks=2,
            tech_kdb=60.5,
            tech_klb=3.2,
            tech_kdh=12.1,
            tech_parking_capacity=40,
            tech_max_floors=3,
            tech_total_floor_area=9000.0,

            # TAHAP 7: KONSULTAN
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",

            # TAHAP 9: URL DOKUMENTASI FOTO JALAN / RONAL AWAL
            photo_north="https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            photo_south="https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            photo_east="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            photo_west="https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            photo_access="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80",

            # TAHAP 10: PERNYATAAN PEMOHON
            statement_agreed=True
        )
        db.add(permohonan_2)

        # Poligon Kavling KDB melanggar sempadan sungai Cipakancilan
        poly_kdb_2 = Polygon([
            (106.8110, -6.6210),
            (106.8120, -6.6210),
            (106.8120, -6.6220),
            (106.8110, -6.6220),
            (106.8110, -6.6210)
        ])
        geom_kdb_2 = SitePlanGeometryModel(
            id_permohonan="sub-5",
            layer_name="PTSP_KDB",
            geom=from_shape(poly_kdb_2, srid=4326)
        )
        db.add(geom_kdb_2)

        # Kompensasi pengganti konversi sawah basah (KP2B) 1:1
        kompensasi_2 = LahanKompensasiModel(
            id_kompensasi="komp-102",
            id_permohonan="sub-5",
            tipe_kompensasi="LAHAN_SAWAH",
            luas_kompensasi_m2=12000.0,
            geom=from_shape(Polygon([
                (106.8110, -6.6210),
                (106.8120, -6.6210),
                (106.8120, -6.6220),
                (106.8110, -6.6220),
                (106.8110, -6.6210)
            ]), srid=4326),
            status_pemenuhan="BELUM_TERPENUHI",
            nilai_nominal=0.0,
            bukti_legalitas_url=None
        )
        db.add(kompensasi_2)

        # Log audit penolakan teknis akibat melanggar sempadan
        audit_2 = AuditTrailModel(
            submission_id="sub-5",
            actor_name="Ir. Budi Santoso",
            role="Tim Teknis",
            action="VERIFY_TECHNICAL_REJECTED",
            status_before="Verifikasi Teknis",
            status_after="Ditolak",
            notes="Berkas dikembalikan untuk REVISI teknis. Rencana jalan dan kaveling nomor 12 s/d 18 terbukti melanggar batas sempadan sungai Cipakancilan (WGS84) sejauh 5 meter.",
            created_at=datetime(2026, 6, 12, 14, 15, 0)
        )
        db.add(audit_2)

        db.commit()
        print("[SEEDER] Sukses menyemai seluruh data spasial, user, dan riwayat log audit.")

    except Exception as e:
        db.rollback()
        print(f"[SEEDER_FATAL] Kegagalan komit database: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_spatial_data()