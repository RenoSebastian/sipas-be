"""
============================================================================
SIPAS DATABASE UTILITY — Spatial Database Seeder [seed.py] (REVISED v3 - CLEAN)
============================================================================
Peran: Mengisi database lokal PostgreSQL/PostGIS dengan data spasial awal
       (WGS84 / SRID 4326) di wilayah rona Kabupaten Bogor, menyemai data 
       batas aturan RDTR (bylaw), menyemai rincian checklist evaluasi,
       dan mendaftarkan pengguna awal (users) untuk kebutuhan autentikasi.
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
        # Konstruksi file url lokal
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
        # TAHAP 1: PENYEMAIAN DATA USER SIMULASI (Sesuai Kredensial Frontend)
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data kredensial user baru...")
        default_password_hash = hash_password("password123")
        
        users = [
            UserModel(
                username="pemohon@geocitra.com",
                email="pemohon@geocitra.com",
                hashed_password=default_password_hash,
                full_name="Pemohon",
                role="PEMOHON",
                is_active=True,
                nip="9120301938192",
                company="PT Maju Jaya Sentosa",
                phone="081234567890"
            ),
            UserModel(
                username="admin@geocitra.com",
                email="admin@geocitra.com",
                hashed_password=default_password_hash,
                full_name="Admin",
                role="ADMIN",
                is_active=True,
                nip="199208152018032001",
                company="Dinas PUPR Kabupaten Bogor",
                phone="081398765432"
            ),
            UserModel(
                username="tim_teknis@geocitra.com",
                email="tim_teknis@geocitra.com",
                hashed_password=default_password_hash,
                full_name="Tim Teknis",
                role="TIM_TEKNIS",
                is_active=True,
                nip="198005232005011002",
                company="Tim Teknis Penataan Ruang",
                phone="081223344556"
            ),
            UserModel(
                username="kabid@geocitra.com",
                email="kabid@geocitra.com",
                hashed_password=default_password_hash,
                full_name="Kepala Bidang",
                role="KABID_PUPR",
                is_active=True,
                nip="198402122010011003",
                company="Dinas PUPR Kabupaten Bogor",
                phone="081199887766"
            ),
            UserModel(
                username="superadmin@geocitra.com",
                email="superadmin@geocitra.com",
                hashed_password=default_password_hash,
                full_name="Super Admin",
                role="ADMIN",
                is_active=True,
                nip="198901012015011002",
                company="Dinas PUPR Kabupaten Bogor",
                phone="081111111111"
            )
        ]
        
        for user in users:
            db.add(user)
        db.commit() # Commit agar ID User ter-generate secara transaksional
        print(f"[SEEDER] Sukses mendaftarkan {len(users)} user simulasi ke database.")

        pemohon_user = db.query(UserModel).filter(UserModel.username == "pemohon@geocitra.com").first()
        pemohon_id = pemohon_user.id if pemohon_user else None

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
        # TAHAP 3: PENYEMAIAN DATA SPASIAL PERMOHONAN DENGAN METRIK DETAIL
        # ──────────────────────────────────────────────────────────────────────
        print("[SEEDER] Menyemai data spasial permohonan komparasi...")

        # KASUS 1: Cibinong Green Mansion (Status: Menunggu Verifikasi)
        outer_poly_1 = Polygon([
            (106.8400, -6.4800),
            (106.8430, -6.4800),
            (106.8430, -6.4830),
            (106.8400, -6.4830),
            (106.8400, -6.4800)
        ])

        permohonan_1 = PermohonanModel(
            id_permohonan="sub-1",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-001",
            housing_name="Cibinong Green Mansion",
            developer_name="PT Geocitra Pembangunan Mandiri (Ahmad Fauzi)",
            land_area=30000.0,
            submission_date=date(2026, 6, 20),
            status="Menunggu Verifikasi",
            buffer_sla=0,
            elapsed_days=0,
            applicant_type="BADAN_USAHA",
            applicant_name="PT Geocitra Pembangunan Mandiri",
            applicant_nik=None,
            applicant_nib="9120301938192",
            applicant_npwp="01.234.567.8-901.000",
            applicant_director_name="Ahmad Fauzi",
            applicant_phone="081234567890",
            applicant_email="pemohon@geocitra.com",
            applicant_address="Kawasan Niaga Tegar Beriman Blok A-3, Cibinong, Kabupaten Bogor",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Lahan Cibinong Raya",
            location_village="Cibinong",
            location_district="Cibinong",
            location_full_address="Jl. Raya Tegar Beriman No. 45, Cibinong, Kec. Cibinong, Kabupaten Bogor, Jawa Barat",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 10293/Cibinong",
            location_certificate_owner="PT Geocitra Pembangunan Mandiri",
            geom=from_shape(outer_poly_1, srid=4326),
            cad_file_name="blueprint_cibinong_mansion.dxf",
            cad_param_a=0.8875,
            cad_param_b=0.4612,
            cad_param_tx=106.8415,
            cad_param_ty=-6.4815,
            cad_scale=1.0024,
            cad_rotation=0.4812,
            spatial_kkpr_number="503/KKPR/PUPR/2026/089",
            spatial_land_use="Zona Perumahan Kepadatan Sedang",
            spatial_green_area=4600.0,
            tech_lot_count=150,
            tech_housing_type="NON_SUBSIDI",
            tech_cemetery_area=600.0,
            tech_road_row_main="12 Meter",
            tech_road_row_local="8 Meter",
            tech_water_system="PDAM Tirta Kahuripan",
            consultant_name="Ir. Hermawan Pratama",
            consultant_company_name="CV Rencana Semesta",
            consultant_pic_name="Hermawan Pratama",
            statement_agreed=True,

            # Proposed
            applicant_land_area=30000.0,
            applicant_building_area=16500.0,
            applicant_kdb=55.0,
            applicant_klb=2.1,
            applicant_kdh=15.0,
            applicant_gsb=5.0,
            applicant_rth_area=4600.0,

            # Bylaws (dari Cibinong-Cibinong-Perumahan)
            bylaw_max_kdb=60.0,
            bylaw_max_klb=3.2,
            bylaw_min_kdh=10.0,
            bylaw_min_gsb=5.0,
            bylaw_min_rth_area=1500.0
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
        outer_poly_2 = Polygon([
            (106.8000, -6.4950),
            (106.8020, -6.4950),
            (106.8020, -6.4970),
            (106.8000, -6.4970),
            (106.8000, -6.4950)
        ])

        permohonan_2 = PermohonanModel(
            id_permohonan="sub-2",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-002",
            housing_name="Bojonggede Residence",
            developer_name="PT Pabuaran Jaya Sentosa (Bambang Hariyadi)",
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
            applicant_address="Kawasan Permata Mansion Blok B-12, Bojonggede, Kabupaten Bogor",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Kaveling Bojong Raya",
            location_village="Pabuaran",
            location_district="Bojonggede",
            location_full_address="Jl. Raya Bojonggede No. 89, Pabuaran, Kec. Bojonggede, Kabupaten Bogor, Jawa Barat",
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
            tech_water_system="Sumur Bor Terstandar",
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",
            statement_agreed=True,

            # Proposed
            applicant_land_area=15000.0,
            applicant_building_area=8250.0,
            applicant_kdb=55.0,
            applicant_klb=1.8,
            applicant_kdh=15.0,
            applicant_gsb=5.0,
            applicant_rth_area=2500.0,

            # Bylaws
            bylaw_max_kdb=60.0,
            bylaw_max_klb=3.0,
            bylaw_min_kdh=10.0,
            bylaw_min_gsb=5.0,
            bylaw_min_rth_area=1400.0
        )
        db.add(permohonan_2)
        add_mock_files_for_permohonan(db, "sub-2", {
            "photoNorth": "https://images.unsplash.com/photo-1590069261209-f8e9b8642343?auto=format&fit=crop&w=400&q=80",
            "photoSouth": "https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&fit=crop&w=400&q=80",
            "photoEast": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80",
            "photoWest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=400&q=80",
            "photoAccess": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&q=80"
        }, category="PERUMAHAN")

        # KASUS 3: Sentul Clover Garden (Status: Menunggu Persetujuan)
        outer_poly_3 = Polygon([
            (106.8700, -6.5600),
            (106.8740, -6.5600),
            (106.8740, -6.5640),
            (106.8700, -6.5640),
            (106.8700, -6.5600)
        ])

        permohonan_3 = PermohonanModel(
            id_permohonan="sub-3",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-003",
            housing_name="Sentul Clover Garden",
            developer_name="PT Sentul City Sentosa (Ir. Hermawan S.)",
            land_area=45000.0,
            submission_date=date(2026, 6, 15),
            status="Menunggu Persetujuan",
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
            applicant_address="Menara Sentul Lt. 8, Babakan Madang, Kabupaten Bogor",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Bukit Sentul Clover",
            location_village="Babakan Madang",
            location_district="Babakan Madang",
            location_full_address="Kawasan Sentul City, Babakan Madang, Kec. Babakan Madang, Kabupaten Bogor, Jawa Barat",
            location_ownership_status="SHM",
            location_certificate_number="SHM No. 9081/Babakan",
            location_certificate_owner="PT Sentul City Sentosa",
            geom=from_shape(outer_poly_3, srid=4326),
            cad_file_name="blueprint_sentul_clover.dxf",
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
            tech_water_system="PDAM Tirta Kahuripan",
            consultant_name="Ir. Hermawan Pratama",
            consultant_company_name="CV Rencana Semesta",
            consultant_pic_name="Hermawan Pratama",
            statement_agreed=True,

            # Proposed
            applicant_land_area=45000.0,
            applicant_building_area=20250.0,
            applicant_kdb=45.0,
            applicant_klb=2.0,
            applicant_kdh=20.0,
            applicant_gsb=6.0,
            applicant_rth_area=6800.0,

            # Bylaws
            bylaw_max_kdb=50.0,
            bylaw_max_klb=2.5,
            bylaw_min_kdh=15.0,
            bylaw_min_gsb=6.0,
            bylaw_min_rth_area=2000.0
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
        outer_poly_4 = Polygon([
            (106.9600, -6.3800),
            (106.9625, -6.3800),
            (106.9625, -6.3825),
            (106.9600, -6.3825),
            (106.9600, -6.3800)
        ])

        permohonan_4 = PermohonanModel(
            id_permohonan="sub-4",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-004",
            housing_name="Cileungsi Green Valley",
            developer_name="PT Cileungsi Sukses Mandiri (Gunawan Wibisono)",
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
            applicant_address="Ruko Limus Blok C-10, Cileungsi, Kabupaten Bogor",
            submission_type="BARU",
            submission_category="PERUMAHAN",
            location_name="Lahan Limus Cileungsi",
            location_village="Limus Nunggal",
            location_district="Cileungsi",
            location_full_address="Jl. Raya Cileungsi No. 12, Limus Nunggal, Kec. Cileungsi, Kabupaten Bogor, Jawa Barat",
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
            tech_water_system="Sumur Bor Bersama",
            consultant_name="Ir. Wahyu Hidayat",
            consultant_company_name="PT Wahyu Konsultan Teknik",
            consultant_pic_name="Wahyu Hidayat",
            statement_agreed=True,
            signature_hash="sha256:7b952f4c9c1b48b52f6f1947b19a3b90875638c039a7bb2e80556f8f17e7ab43",
            signed_pdf_url="/api/v1/submissions/sub-4/download",
            kabid_signature="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAAAyCAYAAACq594cAAAABmJLR0QA/wD/AP+gvaeTAAAAcUlEQVR42u3SQQ0AIBDAsOH8OUcRDyagdyfAramS5OsB2GhkJCgJCQpKQlASEhSUhAQFJSFBCUkIUFISFJSEBCUkICFBCUkIUFISFJSEBCUkICFBCUkIUFISFJSEBCUkICFBCUlIUFISFJSEBAUlIUEJCUZ3o2Tf566ZAAAAAElFTkSuQmCC",

            # Proposed
            applicant_land_area=20000.0,
            applicant_building_area=11000.0,
            applicant_kdb=55.0,
            applicant_klb=2.2,
            applicant_kdh=15.0,
            applicant_gsb=5.0,
            applicant_rth_area=3100.0,

            # Bylaws
            bylaw_max_kdb=60.0,
            bylaw_max_klb=3.0,
            bylaw_min_kdh=10.0,
            bylaw_min_gsb=5.0,
            bylaw_min_rth_area=1400.0,

            # ─── REVISI: METRIK HASIL HITUNG VERIFIKATOR DINAS (VERIFIED) ───
            verified_kdb=55.0,
            verified_klb=2.2,
            verified_kdh=15.0,
            verified_gsb=5.0,
            verified_rth_area=3100.0,
            
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

        # Menyemai Checklist Evaluasi Untuk Kasus 4 (Lolos Semua)
        eval_items_4 = [
            EvaluasiChecklistItemModel(id_permohonan="sub-4", aspek_code="REQ_ZONING", aspek_label="Kesesuaian dengan RTRW/RDTR", status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="Sesuai rencana zona perumahan"),
            EvaluasiChecklistItemModel(id_permohonan="sub-4", aspek_code="REQ_LEGAL", aspek_label="Status & Legalitas Kepemilikan Lahan", status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="Sertifikat SHM No. 1023 Valid"),
            EvaluasiChecklistItemModel(id_permohonan="sub-4",
                aspek_code="REQ_BUILD_LIMIT", aspek_label="Kesesuaian KDB, KLB, KDH, GSB",
                status_kelayakan=ChecklistStatus.SESUAI, catatan_verifikator="KDB terhitung 55% memenuhi batas maks 60%"
            ),
        ]
        for ev in eval_items_4:
            db.add(ev)

        poly_kdb_4 = Polygon([
            (106.9605, -6.3805),
            (106.9618, -6.3805),
            (106.9618, -6.3818),
            (106.9605, -6.3818),
            (106.9605, -6.3805)
        ])
        geom_kdb_4 = SitePlanGeometryModel(
            id_permohonan="sub-4",
            layer_name="PTSP_KDB",
            geom=from_shape(poly_kdb_4, srid=4326)
        )
        db.add(geom_kdb_4)

        kompensasi_4 = LahanKompensasiModel(
            id_kompensasi="komp-104",
            id_permohonan="sub-4",
            tipe_kompensasi="LAHAN_MAKAM_FISIK",
            luas_kompensasi_m2=400.0,
            geom=from_shape(Polygon([
                (106.9580, -6.3790),
                (106.9590, -6.3790),
                (106.9590, -6.3798),
                (106.9580, -6.3798),
                (106.9580, -6.3790)
            ]), srid=4326),
            status_pemenuhan="TERPENUHI",
            nilai_nominal=0.0,
            bukti_legalitas_url="https://sipas.bogor.go.id/sertifikat/komp-104.pdf"
        )
        db.add(kompensasi_4)

        audit_4a = AuditTrailModel(
            submission_id="sub-4",
            actor_name="Pemohon",
            role="Pemohon",
            action="SUBMIT_UNIFIED_FORM",
            status_before="Draft",
            status_after="Menunggu Verifikasi",
            notes="Berkas pendaftaran diajukan.",
            created_at=datetime(2026, 6, 10, 9, 0, 0)
        )
        db.add(audit_4a)

        audit_4b = AuditTrailModel(
            submission_id="sub-4",
            actor_name="Admin",
            role="Admin",
            action="VERIFY_ADMIN_APPROVED",
            status_before="Menunggu Verifikasi",
            status_after="Verifikasi Administrasi",
            notes="Administrasi valid.",
            created_at=datetime(2026, 6, 11, 10, 0, 0)
        )
        db.add(audit_4b)

        audit_4c = AuditTrailModel(
            submission_id="sub-4",
            actor_name="Tim Teknis",
            role="Tim Teknis",
            action="VERIFY_TECHNICAL_APPROVED",
            status_before="Verifikasi Teknis",
            status_after="Menunggu Persetujuan",
            notes="Kelayakan spasial diverifikasi oleh Tim Teknis, BAPL diterbitkan.",
            created_at=datetime(2026, 6, 12, 14, 0, 0)
        )
        db.add(audit_4c)

        audit_4d = AuditTrailModel(
            submission_id="sub-4",
            actor_name="Kepala Bidang",
            role="KABID_PUPR",
            action="APPROVE_KABID_TTE",
            status_before="Proses TTE",
            status_after="Disetujui",
            notes="Pengesahan site plan berkas disetujui secara hukum menggunakan TTE Dinas resmi.",
            digital_signature_hash="sha256:7b952f4c9c1b48b52f6f1947b19a3b90875638c039a7bb2e80556f8f17e7ab43",
            created_at=datetime(2026, 6, 14, 16, 0, 0)
        )
        db.add(audit_4d)

        # KASUS 5: Gunung Putri Commercial Hub (Status: Ditolak / Gagal Verifikasi)
        outer_poly_5 = Polygon([
            (106.9000, -6.4200),
            (106.9015, -6.4200),
            (106.9015, -6.4215),
            (106.9000, -6.4215),
            (106.9000, -6.4200)
        ])

        permohonan_5 = PermohonanModel(
            id_permohonan="sub-5",
            user_id=pemohon_id,
            submission_no="SIPAS-2026-005",
            housing_name="Gunung Putri Commercial Hub",
            developer_name="PT Gunung Putri Eka Jaya (Suryadi Subagja)",
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
            applicant_address="Kawasan Industri Gunung Putri No. 4, Gunung Putri, Kabupaten Bogor",
            submission_type="BARU",
            submission_category="NON_PERUMAHAN",
            location_name="Lahan Gunung Putri",
            location_village="Gunung Putri",
            location_district="Gunung Putri",
            location_full_address="Jl. Raya Gunung Putri No. 7, Kec. Gunung Putri, Kabupaten Bogor, Jawa Barat",
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

            # ─── REVISI: METRIK HASIL HITUNG VERIFIKATOR DINAS (VERIFIED) ───
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
            (106.9005, -6.4205),
            (106.9010, -6.4205),
            (106.9010, -6.4210),
            (106.9005, -6.4210),
            (106.9005, -6.4205)
        ])
        geom_kdb_5 = SitePlanGeometryModel(
            id_permohonan="sub-5",
            layer_name="PTSP_KDB",
            geom=from_shape(poly_kdb_5, srid=4326)
        )
        db.add(geom_kdb_5)

        kompensasi_5 = LahanKompensasiModel(
            id_kompensasi="komp-105",
            id_permohonan="sub-5",
            tipe_kompensasi="LAHAN_SAWAH",
            luas_kompensasi_m2=12000.0,
            geom=from_shape(Polygon([
                (106.8980, -6.4180),
                (106.8995, -6.4180),
                (106.8995, -6.4195),
                (106.8980, -6.4195),
                (106.8980, -6.4180)
            ]), srid=4326),
            status_pemenuhan="BELUM_TERPENUHI",
            nilai_nominal=0.0,
            bukti_legalitas_url=None
        )
        db.add(kompensasi_5)

        # Seed Checklist Evaluasi bermasalah
        db.add(EvaluasiChecklistItemModel(
            id_permohonan="sub-5",
            aspek_code="REQ_ZONING",
            aspek_label="Kesesuaian dengan RTRW/RDTR",
            status_kelayakan=ChecklistStatus.SESUAI,
            catatan_verifikator="Sesuai Zona Komersial."
        ))
        db.add(EvaluasiChecklistItemModel(
            id_permohonan="sub-5",
            aspek_code="REQ_BUILD_LIMIT",
            aspek_label="Kesesuaian KDB, KLB, KDH, GSB",
            status_kelayakan=ChecklistStatus.TIDAK_SESUAI,
            catatan_verifikator="KDB riil dinas adalah 60.5% (Batas Maksimal 60%) & KDH 12.1% (Batas minimal 15.0%). Melanggar intensitas zonasi.",
            attachment_url="uploads/evaluasi/revisi_gunung_putri_kdb.pdf"
        ))

        audit_5 = AuditTrailModel(
            submission_id="sub-5",
            actor_name="Tim Teknis",
            role="TIM_TEKNIS",
            action="VERIFY_TECHNICAL_REJECTED",
            status_before="Verifikasi Teknis",
            status_after="Ditolak",
            notes="Berkas ditolak. Kavling melanggar KDB & KDH tata ruang daerah resapan air dekat aliran sungai Cileungsi.",
            created_at=datetime(2026, 6, 12, 14, 15, 0)
        )
        db.add(audit_5)

        db.commit()
        print("[SEEDER] Sukses menyemai seluruh data spasial, user, master RDTR, dan riwayat log audit.")

    except Exception as e:
        db.rollback()
        print(f"[SEEDER_FATAL] Kegagalan komit database: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_spatial_data()
