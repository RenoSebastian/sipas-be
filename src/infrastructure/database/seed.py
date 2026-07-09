# --- FILE: src/infrastructure/database/seed.py ---
"""
============================================================================
SIPAS DATABASE UTILITY — Spatial Database Seeder [seed.py] (REVISED v5)
============================================================================
Peran: Mengisi database lokal PostgreSQL/PostGIS dengan data spasial awal
       (WGS84 / SRID 4326) di wilayah rona Kabupaten Bogor, menyemai data 
       batas aturan RDTR (bylaw), menyemai rincian checklist evaluasi,
       mendaftarkan pengguna awal (users) untuk kebutuhan autentikasi, serta
       membuat snapshot historis dokumen Telaah Staf JSONB secara transaksional.
       Bebas dari peringatan Pylance Optional Member Access (Type-Safe).
============================================================================
"""

import sys
import os
from datetime import date, datetime, timezone

# Sisipkan direktori root proyek ke dalam sys.path agar aman dijalankan dari terminal mana pun
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.security.auth import hash_password  # Mengimpor modul Hashing Password
from src.domain.entities.permohonan import KKPRVerdict
from src.infrastructure.database.models import (
    UserModel,
    PermohonanModel,
    LahanKompensasiModel,
    AuditTrailModel,
    SitePlanGeometryModel,
    PermohonanFileModel,
    MasterRDTRModel,
    EvaluasiChecklistItemModel,
    TelaahStafModel,
    ChecklistStatus
)

def clear_existing_data(db) -> None:
    """Membersihkan database dari data lama agar seeder bersifat Idempotent (Anti-Duplikasi)."""
    print("[SEEDER] Memulai pembersihan tabel database...")
    try:
        db.query(AuditTrailModel).delete()
        db.query(LahanKompensasiModel).delete()
        db.query(SitePlanGeometryModel).delete()
        db.query(PermohonanFileModel).delete()
        db.query(EvaluasiChecklistItemModel).delete()
        db.query(TelaahStafModel).delete()  # Bersihkan tabel baru Telaah Staf (Fase 1)
        db.query(PermohonanModel).delete()
        db.query(MasterRDTRModel).delete()
        db.query(UserModel).delete()  # Bersihkan tabel user lama
        db.commit()
        print("[SEEDER] Sukses membersihkan tabel fisik database.")
    except Exception as e:
        db.rollback()
        print(f"[SEEDER_ERROR] Gagal membersihkan database: {str(e)}")
        sys.exit(1)

def add_mock_files_for_permohonan(db, id_permohonan: str, photos_dict: dict, category: str = "PERUMAHAN") -> None:
    """
    Menyisipkan 8 berkas dokumen terintegrasi secara lengkap ke dalam database.
    Nama file diatur menggunakan identitas yang manusiawi untuk menghindari visualisasi UUID yang membingungkan.
    """
    # Menentukan dokumen teknis dan andalalin secara kondisional berdasarkan kategori pengajuan (Slide 6)
    tech_doc_name = "AMDAL_Kawasan_Industri_Gunung_Putri.pdf" if category == "INDUSTRI" else "Rencana_Sistem_PSU_Kawasan_Hunian.pdf"
    support2_name = "Persetujuan_Teknis_Air_Limbah_Industri.pdf" if category == "INDUSTRI" else "Kajian_Andalalin_Dishub_Approved.pdf"

    documents = [
        {
            "file_key": "legalDoc",
            "file_name": "Sertifikat_Tanah_BPN_SHM_No_1023.pdf",
            "file_path": "uploads/permohonan/mock_legalDoc.pdf"
        },
        {
            "file_key": "technicalDoc",
            "file_name": tech_doc_name,
            "file_path": f"uploads/permohonan/mock_technicalDoc_{category.lower()}.pdf"
        },
        {
            "file_key": "supportDoc",
            "file_name": "SK_KKPR_Persetujuan_Awal_Dinas.pdf",
            "file_path": "uploads/permohonan/mock_supportDoc.pdf"
        },
        {
            "file_key": "supportDoc2",
            "file_name": support2_name,
            "file_path": "uploads/permohonan/mock_supportDoc2.pdf"
        },
        {
            "file_key": "skaDoc",
            "file_name": "Sertifikat_Keahlian_Arsitek_SKEA_IAI.pdf",
            "file_path": "uploads/permohonan/mock_skaDoc.pdf"
        },
        {
            "file_key": "cadDoc",
            "file_name": "site_plan_autocad_vector_coordinates.dxf",
            "file_path": "uploads/permohonan/mock_cadDoc.dxf"
        },
        {
            "file_key": "ktpDoc",
            "file_name": "KTP_Direktur_Utama_Budi_Santoso.jpg",
            "file_path": "uploads/permohonan/mock_ktpDoc.jpg"
        },
        {
            "file_key": "nibDoc",
            "file_name": "NIB_Lembaga_OSS_Maju_Bersama_Jaya.pdf",
            "file_path": "uploads/permohonan/mock_nibDoc.pdf"
        }
    ]

    # Menyimpan dokumen ke tabel fisik permohonan_files
    for doc in documents:
        file_url = f"http://localhost:8000/{doc['file_path']}"
        db.add(PermohonanFileModel(
            id_permohonan=id_permohonan,
            file_type="document",
            file_key=doc["file_key"],
            file_name=doc["file_name"],
            file_path=doc["file_path"],
            file_url=file_url
        ))
    
    # Menyimpan dokumentasi foto lapangan (5 penjuru arah mata angin)
    for k, url in photos_dict.items():
        db.add(PermohonanFileModel(
            id_permohonan=id_permohonan,
            file_type="photo",
            file_key=k,
            file_name=f"{k}.jpg",
            file_path=f"uploads/permohonan/mock_{k}.jpg",
            file_url=url
        ))

def seed_spatial_data() -> None:
    """Menyemai data user, aturan RDTR, dan spasial WGS84 nyata wilayah Kabupaten Bogor."""
    db = SessionLocal()
    clear_existing_data(db)

    print("[SEEDER] Memulai penyemaian data baru...")
    try:
        # ──────────────────────────────────────────────────────────────────────
        # TAHAP 1: PENYEMAIAN DATA USER SIMULASI (Sesuai Kredensial Frontend & Peran Baru)
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data kredensial user baru...")
        default_password_hash = hash_password("password123")
        
        users = [
            UserModel(
                username="pemohon@geocitra.com", email="pemohon@geocitra.com",
                hashed_password=default_password_hash, full_name="Pemohon",
                role="PEMOHON", is_active=True, nip="9120301938192",
                company="PT Geocitra Pembangunan Mandiri", phone="081234567890"
            ),
            UserModel(
                username="admin@geocitra.com", email="admin@geocitra.com",
                hashed_password=default_password_hash, full_name="Admin SIPAS",
                role="ADMIN", is_active=True, nip="199208152018032001",
                company="Dinas Penanaman Modal & PTSP", phone="081398765432"
            ),
            UserModel(
                username="tim_teknis@geocitra.com", email="tim_teknis@geocitra.com",
                hashed_password=default_password_hash, full_name="Tim Teknis Tata Ruang",
                role="TIM_TEKNIS", is_active=True, nip="198005232005011002",
                company="Dinas PUPR Kabupaten Bogor", phone="081223344556"
            ),
            UserModel(
                username="kabid@geocitra.com", email="kabid@geocitra.com",
                hashed_password=default_password_hash, full_name="Kepala Bidang Penataan Ruang",
                role="KABID_PUPR", is_active=True, nip="198402122010011003",
                company="Dinas PUPR Kabupaten Bogor", phone="081199887766"
            ),
            UserModel(
                # ─── BARU: KEPALA DINAS (KADIS) SEBAGAI OTORITAS FINAL TTE ───
                username="kadis@geocitra.com", email="kadis@geocitra.com",
                hashed_password=default_password_hash, full_name="Kepala Dinas DPMPTSP",
                role="KADIS", is_active=True, nip="197503112000031001",
                company="DPMPTSP Kabupaten Bogor", phone="081122334455"
            ),
            UserModel(
                username="superadmin@geocitra.com", email="superadmin@geocitra.com",
                hashed_password=default_password_hash, full_name="Super Admin System",
                role="ADMIN", is_active=True, nip="198901012015011002",
                company="Dinas Penanaman Modal & PTSP", phone="081111111111"
            )
        ]
        
        for user in users:
            db.add(user)
        db.commit()
        print(f"[SEEDER] Sukses mendaftarkan {len(users)} user simulasi ke database.")

        # Ambil record ID untuk pemetaan relasi
        pemohon_raw = db.query(UserModel).filter(UserModel.username == "pemohon@geocitra.com").first()
        admin_raw = db.query(UserModel).filter(UserModel.username == "admin@geocitra.com").first()
        tim_teknis_raw = db.query(UserModel).filter(UserModel.username == "tim_teknis@geocitra.com").first()
        kabid_raw = db.query(UserModel).filter(UserModel.username == "kabid@geocitra.com").first()
        kadis_raw = db.query(UserModel).filter(UserModel.username == "kadis@geocitra.com").first()

        # ─── TYPE NARROWING FOR PYLANCE (Menghilangkan reportOptionalMemberAccess) ───
        assert pemohon_raw is not None, "Gagal: User pemohon wajib terdaftar."
        assert admin_raw is not None, "Gagal: User admin wajib terdaftar."
        assert tim_teknis_raw is not None, "Gagal: User tim_teknis wajib terdaftar."
        assert kabid_raw is not None, "Gagal: User kabid wajib terdaftar."
        assert kadis_raw is not None, "Gagal: User kadis wajib terdaftar."

        pemohon: UserModel = pemohon_raw
        admin: UserModel = admin_raw
        tim_teknis: UserModel = tim_teknis_raw
        kabid: UserModel = kabid_raw
        kadis: UserModel = kadis_raw

        # ──────────────────────────────────────────────────────────────────────
        # TAHAP 2: PENYEMAIAN DATA MASTER ATURAN RDTR KABUPATEN BOGOR (Bylaws)
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data master batas aturan RDTR Kabupaten Bogor...")
        
        rdtr_rules = [
            MasterRDTRModel(
                district="Cibinong", village="Cibinong", category="PERUMAHAN",
                max_kdb=60.0, max_klb=3.2, min_kdh=10.0, min_gsb=5.0, min_rth_area=1500.0
            ),
            MasterRDTRModel(
                district="Bojonggede", village="Pabuaran", category="PERUMAHAN",
                max_kdb=60.0, max_klb=3.0, min_kdh=10.0, min_gsb=5.0, min_rth_area=1400.0
            ),
            MasterRDTRModel(
                district="Babakan Madang", village="Babakan Madang", category="PERUMAHAN",
                max_kdb=50.0, max_klb=2.5, min_kdh=15.0, min_gsb=6.0, min_rth_area=2000.0
            ),
            MasterRDTRModel(
                district="Cileungsi", village="Limus Nunggal", category="PERUMAHAN",
                max_kdb=60.0, max_klb=3.0, min_kdh=10.0, min_gsb=5.0, min_rth_area=1400.0
            ),
            MasterRDTRModel(
                district="Gunung Putri", village="Gunung Putri", category="NON_PERUMAHAN",
                max_kdb=60.0, max_klb=3.5, min_kdh=15.0, min_gsb=6.0, min_rth_area=1000.0
            )
        ]
        
        for rule in rdtr_rules:
            db.add(rule)
        db.commit()
        print(f"[SEEDER] Sukses menyemai {len(rdtr_rules)} baris batas aturan RDTR.")

        # ──────────────────────────────────────────────────────────────────────
        # TAHAP 3: PENYEMAIAN DATA SPASIAL PERMOHONAN DENGAN MATRIKS INTENSITAS
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data spasial permohonan komparasi...")

        import math
        
        BOUNDARY_VERTICES_1 = [
            (0, 0), (140, 15), (155, -45), (240, -30), (220, 70), (280, 110),
            (190, 160), (110, 115), (80, 140), (-40, 100), (-20, 50), (-60, 30), (0, 0)
        ]
        
        BOUNDARY_VERTICES_2 = [
            (0, 0), (90, -10), (110, -50), (180, -30), (160, 40), (200, 70),
            (130, 120), (80, 85), (50, 100), (-30, 70), (-10, 35), (-40, 20), (0, 0)
        ]

        def cad_to_wgs84_seed(vertices, base_lon, base_lat, rotation_deg=12):
            rad = math.radians(rotation_deg)
            lat_len = 111132.95
            lon_len = 111132.95 * math.cos(math.radians(base_lat))
            wgs84_coords = []
            for x, y in vertices:
                x_rot = x * math.cos(rad) - y * math.sin(rad)
                y_rot = x * math.sin(rad) + y * math.cos(rad)
                lon = base_lon + (x_rot / lon_len)
                lat = base_lat + (y_rot / lat_len)
                wgs84_coords.append((lon, lat))
            return Polygon(wgs84_coords)

        # KASUS 1: Cibinong Green Mansion (Status: Menunggu Verifikasi)
        outer_poly_1 = cad_to_wgs84_seed(BOUNDARY_VERTICES_1, base_lon=106.8400, base_lat=-6.4800, rotation_deg=12)

        permohonan_1 = PermohonanModel(
            id_permohonan="sub-1", user_id=pemohon.id, submission_no="SIPAS-2026-001",
            housing_name="Cibinong Green Mansion", developer_name="PT Geocitra Pembangunan Mandiri",
            land_area=30000.0, submission_date=date(2026, 6, 20), status="Menunggu Verifikasi",
            buffer_sla=0, elapsed_days=0, applicant_type="BADAN_USAHA",
            applicant_name="PT Geocitra Pembangunan Mandiri", applicant_nik=None, applicant_nib="9120301938192",
            applicant_npwp="01.234.567.8-901.000", applicant_director_name="Ahmad Fauzi",
            applicant_phone="081234567890", applicant_email="pemohon@geocitra.com",
            applicant_address="Niaga Tegar Beriman, Cibinong", submission_type="BARU", submission_category="PERUMAHAN",
            location_name="Cibinong", location_village="Cibinong", location_district="Cibinong",
            location_full_address="Jl. Raya Tegar Beriman, Cibinong", location_ownership_status="SHM",
            location_certificate_number="SHM No. 10293/Cibinong", location_certificate_owner="PT Geocitra Pembangunan Mandiri",
            geom=from_shape(outer_poly_1, srid=4326), cad_file_name="blueprint_cibinong.dxf",
            cad_param_a=0.8875, cad_param_b=0.4612, cad_param_tx=106.8415, cad_param_ty=-6.4815,
            cad_scale=1.0024, cad_rotation=0.4812, spatial_kkpr_number="503/KKPR/PUPR/2026/089",
            spatial_land_use="Zona Perumahan Kepadatan Sedang", spatial_green_area=4600.0,
            tech_lot_count=150, tech_housing_type="NON_SUBSIDI", tech_cemetery_area=600.0,
            tech_road_row_main="12 Meter", tech_road_row_local="8 Meter", tech_water_system="ADA",
            tech_water_source="PDAM Tirta Kahuripan", consultant_name="Ir. Hermawan Pratama",
            consultant_company_name="CV Rencana Semesta", consultant_pic_name="Hermawan Pratama", statement_agreed=True,
            
            # Proposed & Bylaw snapshots
            applicant_land_area=30000.0, applicant_building_area=16500.0, applicant_kdb=55.0,
            applicant_klb=2.1, applicant_kdh=15.0, applicant_gsb=5.0, applicant_rth_area=4600.0,
            bylaw_max_kdb=60.0, bylaw_max_klb=3.2, bylaw_min_kdh=10.0, bylaw_min_gsb=5.0, bylaw_min_rth_area=1500.0
        )
        db.add(permohonan_1)
        add_mock_files_for_permohonan(db, "sub-1", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="PERUMAHAN")


        # KASUS 2: Bojonggede Residence (Status: Verifikasi Administrasi)
        outer_poly_2 = cad_to_wgs84_seed(BOUNDARY_VERTICES_2, base_lon=106.8000, base_lat=-6.4950, rotation_deg=5)

        permohonan_2 = PermohonanModel(
            id_permohonan="sub-2",
            user_id=pemohon.id,
            submission_no="SIPAS-2026-002",
            housing_name="Bojonggede Residence",
            developer_name="PT Pabuaran Jaya Sentosa",
            land_area=15000.0,
            submission_date=date(2026, 6, 22),
            status="Verifikasi Administrasi",
            buffer_sla=1,
            elapsed_days=1,
            applicant_type="BADAN_USAHA",
            applicant_name="PT Pabuaran Jaya Sentosa",
            applicant_nik=None,
            applicant_nib="8120309918273",
            applicant_npwp="02.444.555.6-902.000",
            applicant_director_name="Bambang Hariyadi",
            applicant_phone="081255556666",
            applicant_email="pemohon@geocitra.com",
            applicant_address="Kawasan Permata, Bojonggede",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Bojong Raya",
            location_village="Pabuaran",
            location_district="Bojonggede",
            location_full_address="Jl. Raya Bojonggede, Bojonggede",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 673/Pabuaran",
            location_certificate_owner="PT Pabuaran Jaya Sentosa",
            geom=from_shape(outer_poly_2, srid=4326),
            cad_file_name="blueprint_bojonggede.dxf",
            cad_param_a=0.9125,
            cad_param_b=0.3812,
            cad_param_tx=106.8010,
            cad_param_ty=-6.4960,
            cad_scale=1.0012,
            cad_rotation=0.3512,
            spatial_kkpr_number="503/KKPR/PUPR/2026/092",
            spatial_land_use="Zona Perumahan Kepadatan Sedang",
            spatial_green_area=2500.0,
            tech_lot_count=70,
            tech_housing_type="CAMPURAN",
            tech_cemetery_area=300.0,
            tech_road_row_main="10 Meter",
            tech_road_row_local="8 Meter",
            tech_water_system="ADA",
            tech_water_source="Sumur Bor Terstandar",
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",
            statement_agreed=True,

            # Proposed & Bylaw
            applicant_land_area=15000.0, applicant_building_area=8250.0, applicant_kdb=55.0,
            applicant_klb=1.8, applicant_kdh=15.0, applicant_gsb=5.0, applicant_rth_area=2500.0,
            bylaw_max_kdb=60.0, bylaw_max_klb=3.0, bylaw_min_kdh=10.0, bylaw_min_gsb=5.0, bylaw_min_rth_area=1400.0
        )
        db.add(permohonan_2)
        add_mock_files_for_permohonan(db, "sub-2", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="PERUMAHAN")


        # KASUS 3: Sentul Clover Garden (─── BARU: Menunggu Rekomendasi ───)
        # Skenario: Tim Teknis telah memformulasikan draf, kini antre ulasan Kabid
        outer_poly_3 = cad_to_wgs84_seed(BOUNDARY_VERTICES_1, base_lon=106.8700, base_lat=-6.5600, rotation_deg=15)

        permohonan_3 = PermohonanModel(
            id_permohonan="sub-3",
            user_id=pemohon.id,
            submission_no="SIPAS-2026-003",
            housing_name="Sentul Clover Garden",
            developer_name="PT Sentul City Sentosa",
            land_area=45000.0,
            submission_date=date(2026, 6, 15),
            status="Menunggu Rekomendasi",  # Status Baru (Review Kabid)
            buffer_sla=3,
            elapsed_days=3,
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentul City Sentosa",
            applicant_nik=None,
            applicant_nib="9130402837194",
            applicant_npwp="03.111.222.3-903.000",
            applicant_director_name="Ir. Hermawan S.",
            applicant_phone="081199887766",
            applicant_email="pemohon@geocitra.com",
            applicant_address="Menara Sentul, Babakan Madang",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Bukit Sentul",
            location_village="Babakan Madang",
            location_district="Babakan Madang",
            location_full_address="Sentul City, Babakan Madang",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 9081/Babakan",
            location_certificate_owner="PT Sentul City Sentosa",
            geom=from_shape(outer_poly_3, srid=4326),
            cad_file_name="blueprint_sentul.dxf",
            cad_param_a=0.9015,
            cad_param_b=0.4125,
            cad_param_tx=106.8720,
            cad_param_ty=-6.5620,
            cad_scale=1.0018,
            cad_rotation=0.4012,
            spatial_kkpr_number="503/KKPR/PUPR/2026/099",
            spatial_land_use="Zona Perumahan Kepadatan Sedang",
            spatial_green_area=6800.0,
            tech_lot_count=210,
            tech_housing_type="NON_SUBSIDI",
            tech_cemetery_area=900.0,
            tech_road_row_main="14 Meter",
            tech_road_row_local="8 Meter",
            tech_water_system="ADA",
            tech_water_source="PDAM Tirta Kahuripan",
            consultant_name="Ir. Hermawan Pratama",
            consultant_company_name="CV Rencana Semesta",
            consultant_pic_name="Hermawan Pratama",
            statement_agreed=True,

            # Proposed & Bylaw
            applicant_land_area=45000.0, applicant_building_area=20250.0, applicant_kdb=45.0,
            applicant_klb=2.0, applicant_kdh=20.0, applicant_gsb=6.0, applicant_rth_area=6800.0,
            bylaw_max_kdb=50.0, bylaw_max_klb=2.5, bylaw_min_kdh=15.0, bylaw_min_gsb=6.0, bylaw_min_rth_area=2000.0
        )
        db.add(permohonan_3)
        add_mock_files_for_permohonan(db, "sub-3", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="PERUMAHAN")


        # KASUS 4: Cileungsi Green Valley (Status: Disetujui / Selesai TTE)
        # Skenario: Berkas disahkan, paraf Kabid & TTE Kadis tertanam lengkap!
        outer_poly_4 = cad_to_wgs84_seed(BOUNDARY_VERTICES_2, base_lon=106.9600, base_lat=-6.3800, rotation_deg=8)

        permohonan_4 = PermohonanModel(
            id_permohonan="sub-4",
            user_id=pemohon.id,
            submission_no="SIPAS-2026-004",
            housing_name="Cileungsi Green Valley",
            developer_name="PT Cileungsi Sukses Mandiri",
            land_area=20000.0,
            submission_date=date(2026, 6, 10),
            status="Disetujui",
            buffer_sla=4,
            elapsed_days=4,
            applicant_type="BADAN_USAHA",
            applicant_name="PT Cileungsi Sukses Mandiri",
            applicant_nik=None,
            applicant_nib="9140302837184",
            applicant_npwp="04.888.777.6-904.000",
            applicant_director_name="Gunawan Wibisono",
            applicant_phone="081288889999",
            applicant_email="pemohon@geocitra.com",
            applicant_address="Ruko Limus, Cileungsi",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Limus Cileungsi",
            location_village="Limus Nunggal",
            location_district="Cileungsi",
            location_full_address="Jl. Raya Cileungsi No. 12, Cileungsi",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 1023/Limus",
            location_certificate_owner="PT Cileungsi Sukses Mandiri",
            geom=from_shape(outer_poly_4, srid=4326),
            cad_file_name="blueprint_cileungsi.dxf",
            cad_param_a=0.8925,
            cad_param_b=0.3925,
            cad_param_tx=106.9610,
            cad_param_ty=-6.3810,
            cad_scale=1.0020,
            cad_rotation=0.3812,
            spatial_kkpr_number="503/KKPR/PUPR/2026/084",
            spatial_land_use="Zona Perumahan Kepadatan Sedang",
            spatial_green_area=3100.0,
            tech_lot_count=90,
            tech_housing_type="SUBSIDI",
            tech_cemetery_area=400.0,
            tech_road_row_main="10 Meter",
            tech_road_row_local="8 Meter",
            tech_water_system="ADA",
            tech_water_source="Sumur Bor Bersama",
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",
            statement_agreed=True,
            
            # Bukti Hukum TTE (Pembaruan: ditandatangani Kadis, diparaf Kabid)
            signature_hash="sha256:7b952f4c9c1b48b52f6f1947b19a3b90875638c039a7bb2e80556f8f17e7ab43",
            signed_pdf_url="/api/v1/submissions/sub-4/download",
            
            # Paraf verifikasi internal Kabid
            kabid_signature="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAAAyCAYAAACq594cAAAABmJLR0QA/wD/AP+gvaeTAAAAcUlEQVR42u3SQQ0AIBDAsOH8OUcRDyagdyfAramS5OsB2GhkJCgJCQpKQlASEhSUhAQFJSFBCUkIUFISFJSEBCUkICFBCUkIUFISFJSEBCUkICFBCUkIUFISFJSEBCUkICFBCUkIUFISFJSEBCUkICFBCUlIUFISFJSEBAUlIUEJCUZ3o2Tf566ZAAAAAElFTkSuQmCC",
            # TTE Kriptografis Final Kepala Dinas (Kadis)
            kadis_signature="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABmJLR0QA/wD/AP+gvaeTAAAAbElEQVR42u3SARAAMAgDwOL8O0cZ8CAgN5fAralV8noALBoJBYKQCAlBQUgICgpCQoICkhCghCQEKSkJCEpCAhIQEJCAhAQlJCFISELb7u869fTkyZOnp0+f9jM8CQpKQoISkhCgpCQoKAnBy90A81GjdSve4/sAAAAASUVORK5CYII=",

            # Snapshot perbandingan intensitas
            applicant_land_area=20000.0, applicant_building_area=11000.0, applicant_kdb=55.0,
            applicant_klb=2.2, applicant_kdh=15.0, applicant_gsb=5.0, applicant_rth_area=3100.0,
            bylaw_max_kdb=60.0, bylaw_max_klb=3.0, bylaw_min_kdh=10.0, bylaw_min_gsb=5.0, bylaw_min_rth_area=1400.0,
            verified_kdb=55.0, verified_klb=2.2, verified_kdh=15.0, verified_gsb=5.0, verified_rth_area=3100.0,
            
            kkpr_verdict=KKPRVerdict.SESUAI,
            kkpr_verified_at=datetime(2026, 6, 12, 14, 0, 0),
            kkpr_verifier_name="Tim Teknis Penataan Ruang"
        )
        db.add(permohonan_4)
        add_mock_files_for_permohonan(db, "sub-4", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="PERUMAHAN")

        # Seeding Checklist Evaluasi bersertifikat audit kelayakan
        eval_items_4 = [
            EvaluasiChecklistItemModel(
                id_permohonan="sub-4", aspek_code="M1_ZONING", aspek_label="Kesesuaian Rencana Pola Ruang", 
                status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="Sesuai rencana zonasi perumahan",
                verified_by_id=admin.id, verified_at=datetime(2026, 6, 11, 10, 0)
            ),
            EvaluasiChecklistItemModel(
                id_permohonan="sub-4", aspek_code="M2_BOUNDARY", aspek_label="Batas Fisik Bidang Tanah & Sertifikat", 
                status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="Sertifikat SHM No. 1023 Valid",
                verified_by_id=admin.id, verified_at=datetime(2026, 6, 11, 10, 5)
            ),
            EvaluasiChecklistItemModel(
                id_permohonan="sub-4", aspek_code="M3_KDB", aspek_label="Koefisien Dasar Bangunan (KDB)",
                status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="KDB terhitung 55% memenuhi batas maks 60%",
                verified_by_id=tim_teknis.id, verified_at=datetime(2026, 6, 12, 11, 0)
            ),
        ]
        for ev in eval_items_4:
            db.add(ev)

        # Seeding geometries detail kaveling
        kdb_coords_local = [(x * 0.6 + 20, y * 0.6 + 20) for x, y in BOUNDARY_VERTICES_2]
        poly_kdb_4 = cad_to_wgs84_seed(kdb_coords_local, base_lon=106.9600, base_lat=-6.3800, rotation_deg=8)
        geom_kdb_4 = SitePlanGeometryModel(
            id_permohonan="sub-4", layer_name="PTSP_KDB", geom=from_shape(poly_kdb_4, srid=4326)
        )
        db.add(geom_kdb_4)

        kompensasi_4 = LahanKompensasiModel(
            id_kompensasi="komp-104", id_permohonan="sub-4", tipe_kompensasi="LAHAN_MAKAM_FISIK",
            luas_kompensasi_m2=400.0, geom=from_shape(Polygon([
                (106.9580, -6.3790), (106.9590, -6.3790), (106.9590, -6.3798), (106.9580, -6.3798), (106.9580, -6.3790)
            ]), srid=4326), status_pemenuhan="TERPENUHI", nilai_nominal=0.0,
            bukti_legalitas_url="https://sipas.bogor.go.id/sertifikat/komp-104.pdf"
        )
        db.add(kompensasi_4)

        # Seeding snapshot dokumen Telaah Staf untuk sub-4 (Idempotent)
        telaah_4_payload = {
            "id_telaah": "tel-sub-4",
            "id_permohonan": "sub-4",
            "verdict": "Sesuai / Dapat Disetujui",
            "created_at": "2026-06-12T14:00:00Z",
            "verifier": {
                "name": tim_teknis.full_name,
                "nip": tim_teknis.nip,
                "timestamp": "2026-06-12T13:45:00Z"
            },
            "endorser": {
                "name": kabid.full_name,
                "nip": kabid.nip,
                "timestamp": "2026-06-13T09:30:00Z"
            },
            "administrative_checklist": [
                {
                    "doc_key": "legalDoc",
                    "doc_label": "Sertifikat Tanah Hak Milik (SHM/HGB)",
                    "file_name": "Sertifikat_Tanah_BPN_SHM_No_1023.pdf",
                    "status": "SESUAI",
                    "notes": "Sertifikat SHM No. 1023 atas nama pengembang valid dan bebas sengketa."
                }
            ],
            "technical_matrix": [
                {
                    "code": "KDB",
                    "label": "Koefisien Dasar Bangunan (KDB)",
                    "unit": "%",
                    "proposed_val": "55.0",
                    "bylaw_val": "60.0",
                    "verified_val": "55.0",
                    "status": "SESUAI",
                    "notes": "KDB terhitung 55% memenuhi batas maksimal aturan RDTR Cileungsi (60%)."
                }
            ],
            "is_overridden": False,
            "override_reason": None
        }
        db.add(TelaahStafModel(
            id_telaah="tel-sub-4",
            id_permohonan="sub-4",
            verdict="Sesuai / Dapat Disetujui",
            is_overridden=False,
            created_at=datetime(2026, 6, 12, 14, 0, 0),
            document_payload=telaah_4_payload
        ))

        # Seeding log audit birokrasi berjenjang (Fase 1 status update)
        audits_sub_4 = [
            AuditTrailModel(submission_id="sub-4", actor_name="Pemohon", role="Pemohon", action="SUBMIT_UNIFIED_FORM", status_before="Draft", status_after="Menunggu Verifikasi", notes="Berkas pendaftaran berhasil diserahkan ke loket.", created_at=datetime(2026, 6, 10, 9, 0)),
            AuditTrailModel(submission_id="sub-4", actor_name=admin.full_name, role="Admin", action="VERIFY_ADMIN_APPROVED", status_before="Menunggu Verifikasi", status_after="Verifikasi Administrasi", notes="Pemeriksaan dokumen administrasi valid. Berkas diteruskan.", created_at=datetime(2026, 6, 11, 10, 10)),
            AuditTrailModel(submission_id="sub-4", actor_name=tim_teknis.full_name, role="Tim Teknis", action="VERIFY_TECHNICAL_APPROVED", status_before="Verifikasi Teknis", status_after="Menunggu Rekomendasi", notes="Hasil analisis spasial terlampir lengkap pada draf Telaah Staf. Dikirim ke Kabid.", created_at=datetime(2026, 6, 12, 14, 0)),
            AuditTrailModel(submission_id="sub-4", actor_name=kabid.full_name, role="KABID_PUPR", action="ENDORSE_TELAAH", status_before="Menunggu Rekomendasi", status_after="Menunggu Persetujuan", notes="Dokumen Telaah Staf disetujui. Rekomendasi draf SK dikirim ke Kepala Dinas.", created_at=datetime(2026, 6, 13, 9, 35)),
            AuditTrailModel(submission_id="sub-4", actor_name=kadis.full_name, role="KADIS", action="APPROVE_KADIS_TTE", status_before="Proses TTE", status_after="Disetujui", notes="SK Site Plan disahkan secara hukum menggunakan TTE Dinas resmi.", digital_signature_hash="sha256:7b952f4c9c1b48b52f6f1947b19a3b90875638c039a7bb2e80556f8f17e7ab43", created_at=datetime(2026, 6, 14, 16, 0))
        ]
        for au in audits_sub_4:
            db.add(au)


        # KASUS 5: Gunung Putri Commercial Hub (Status: Ditolak / Gagal Verifikasi)
        outer_poly_5 = Polygon([
            (106.9000, -6.4200), (106.9015, -6.4200), (106.9015, -6.4215), (106.9000, -6.4215), (106.9000, -6.4200)
        ])

        permohonan_5 = PermohonanModel(
            id_permohonan="sub-5",
            user_id=pemohon.id,
            submission_no="SIPAS-2026-005",
            housing_name="Gunung Putri Commercial Hub",
            developer_name="PT Gunung Putri Eka Jaya",
            land_area=12000.0,
            submission_date=date(2026, 6, 8),
            status="Ditolak",
            buffer_sla=0,
            elapsed_days=2,
            applicant_type="BADAN_USAHA",
            applicant_name="PT Gunung Putri Eka Jaya",
            applicant_nik=None,
            applicant_nib="8150403918274",
            applicant_npwp="05.999.888.7-905.000",
            applicant_director_name="Suryadi Subagja",
            applicant_phone="081255556666",
            applicant_email="pemohon@geocitra.com",
            applicant_address="Kawasan Industri Gunung Putri",
            submission_type="BARU",
            submission_category="NON_PERUMAHAN",
            location_name="Lahan Gunung Putri",
            location_village="Gunung Putri",
            location_district="Gunung Putri",
            location_full_address="Jl. Raya Gunung Putri No. 7",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 673/GunungPutri",
            location_certificate_owner="PT Gunung Putri Eka Jaya",
            geom=from_shape(outer_poly_5, srid=4326),
            cad_file_name="blueprint_gunung_putri.dxf",
            cad_param_a=0.9125,
            cad_param_b=0.3812,
            cad_param_tx=106.9008,
            cad_param_ty=-6.4208,
            cad_scale=1.0012,
            cad_rotation=0.3512,
            spatial_kkpr_number="503/KKPR/PUPR/2026/304",
            spatial_land_use="Zona Cagar Budaya & Resapan Air",
            spatial_green_area=1452.0,
            tech_building_blocks=2,
            tech_kdb=60.5,
            tech_klb=3.2,
            tech_kdh=12.1,
            tech_parking_capacity=40,
            tech_max_floors=3,
            tech_total_floor_area=9000.0,
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",
            statement_agreed=True,

            # Proposed
            applicant_land_area=12000.0,
            applicant_building_area=7260.0,
            applicant_kdb=60.5,
            applicant_klb=3.2,
            applicant_kdh=12.1,
            applicant_gsb=6.0,
            applicant_rth_area=1452.0,

            # Bylaws
            bylaw_max_kdb=60.0,
            bylaw_max_klb=3.5,
            bylaw_min_kdh=15.0,
            bylaw_min_gsb=6.0,
            bylaw_min_rth_area=1000.0,

            # Verified
            verified_kdb=60.5,
            verified_klb=3.2,
            verified_kdh=12.1,
            verified_gsb=6.0,
            verified_rth_area=1452.0,

            kkpr_verdict=KKPRVerdict.TIDAK_SESUAI,
            kkpr_verified_at=datetime(2026, 6, 12, 14, 15, 0),
            kkpr_verifier_name="Ir. Budi Santoso"
        )
        db.add(permohonan_5)
        add_mock_files_for_permohonan(db, "sub-5", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="NON_PERUMAHAN")

        poly_kdb_5 = Polygon([
            (106.9005, -6.4205), (106.9010, -6.4205), (106.9010, -6.4210), (106.9005, -6.4210), (106.9005, -6.4205)
        ])
        geom_kdb_5 = SitePlanGeometryModel(
            id_permohonan="sub-5", layer_name="PTSP_KDB", geom=from_shape(poly_kdb_5, srid=4326)
        )
        db.add(geom_kdb_5)

        kompensasi_5 = LahanKompensasiModel(
            id_kompensasi="komp-105", id_permohonan="sub-5", tipe_kompensasi="LAHAN_SAWAH",
            luas_kompensasi_m2=12000.0, geom=from_shape(Polygon([
                (106.8980, -6.4180), (106.8995, -6.4180), (106.8995, -6.4195), (106.8980, -6.4195), (106.8980, -6.4180)
            ]), srid=4326), status_pemenuhan="BELUM_TERPENUHI", nilai_nominal=0.0, bukti_legalitas_url=None
        )
        db.add(kompensasi_5)

        # Seed Checklist Evaluasi bermasalah (Fase 1 verifier audit)
        db.add(EvaluasiChecklistItemModel(
            id_permohonan="sub-5", aspek_code="M1_ZONING", aspek_label="Kesesuaian Rencana Pola Ruang",
            status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="Sesuai rencana tata wilayah",
            verified_by_id=admin.id, verified_at=datetime(2026, 6, 11, 14, 0)
        ))
        db.add(EvaluasiChecklistItemModel(
            id_permohonan="sub-5", aspek_code="M3_KDB", aspek_label="Koefisien Dasar Bangunan (KDB)",
            status_kelayakan=ChecklistStatus.TIDAK_SESUAI, catatan_verifikator="KDB riil dinas adalah 60.5% (Batas Maksimal 60%) & KDH 12.1% (Batas minimal 15.0%). Melanggar intensitas zonasi.",
            attachment_url="uploads/evaluasi/revisi_gunung_putri_kdb.pdf",
            verified_by_id=tim_teknis.id, verified_at=datetime(2026, 6, 12, 14, 10)
        ))

        # Seeding snapshot dokumen Telaah Staf untuk sub-5 (Ditolak)
        telaah_5_payload = {
            "id_telaah": "tel-sub-5",
            "id_permohonan": "sub-5",
            "verdict": "Tidak Sesuai / Ditolak",
            "created_at": "2026-06-12T14:15:00Z",
            "verifier": {
                "name": tim_teknis.full_name,
                "nip": tim_teknis.nip,
                "timestamp": "2026-06-12T14:10:00Z"
            },
            "endorser": None,
            "administrative_checklist": [
                {
                    "doc_key": "legalDoc",
                    "doc_label": "Sertifikat Tanah Hak Milik (SHM/HGB)",
                    "file_name": "Sertifikat_Tanah_BPN_SHM_No_673.pdf",
                    "status": "SESUAI",
                    "notes": "Sertifikat valid."
                }
            ],
            "technical_matrix": [
                {
                    "code": "KDB",
                    "label": "Koefisien Dasar Bangunan (KDB)",
                    "unit": "%",
                    "proposed_val": "60.5",
                    "bylaw_val": "60.0",
                    "verified_val": "60.5",
                    "status": "TIDAK_SESUAI",
                    "notes": "KDB riil dinas adalah 60.5% melanggar aturan maks 60%."
                }
            ],
            "is_overridden": False,
            "override_reason": None
        }
        db.add(TelaahStafModel(
            id_telaah="tel-sub-5",
            id_permohonan="sub-5",
            verdict="Tidak Sesuai / Ditolak",
            is_overridden=False,
            created_at=datetime(2026, 6, 12, 14, 15, 0),
            document_payload=telaah_5_payload
        ))

        # Log audit birokrasi penolakan
        audit_5 = AuditTrailModel(
            submission_id="sub-5",
            actor_name="Tim Teknis",
            role="TIM_TEKNIS",
            action="VERIFY_TECHNICAL_REJECTED",
            status_before="Verifikasi Teknis",
            status_after="Ditolak",
            notes="Berkas ditolak oleh dinas. Kavling melanggar KDB & KDH tata ruang daerah resapan air dekat aliran sungai Cileungsi.",
            created_at=datetime(2026, 6, 12, 14, 15, 0)
        )
        db.add(audit_5)

        db.commit()
        print("[SEEDER] Sukses menyemai seluruh data spasial, user, master RDTR, dokumen Telaah Staf, dan riwayat log audit.")

    except Exception as e:
        db.rollback()
        print(f"[SEEDER_FATAL] Kegagalan komit database: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_spatial_data()