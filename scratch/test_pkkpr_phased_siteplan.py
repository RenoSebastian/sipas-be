"""
============================================================================
TEST SCRIPT — PKKPR Phased Site Plan Integration (Perbup Bogor No. 4/2025)
============================================================================
Menguji seluruh alur validasi backend:
1. Penerbitan SK PKKPR (Alur lengkap hulu).
2. Pengajuan Site Plan Tahap 1 (Kuota Terpakai sebagian).
3. Pengecekan Quota Summary & Envelope Autofill.
4. Pengajuan Site Plan Tahap 2 (Non-overlapping & sisa kuota berkurang).
5. Pencegahan Pelanggaran Kuota Kumulatif (Error saat melebihi sisa kuota).
6. Pencegahan Pelanggaran Batas Wilayah Spasial (Error saat keluar batas PKKPR).
7. Pencegahan Tumpang Tindih Antar Tahap (Error saat overlap dengan tahap sebelumnya).
8. Pencegahan Pengajuan dengan SK PKKPR yang belum terbit/Disetujui.
============================================================================
"""

import sys
import os
from datetime import date, datetime, timezone

# Add backend root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import UserModel
from src.infrastructure.database.repositories.pkkpr_repository import PKKPRRepository
from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
from src.infrastructure.database.repositories.audit_trail_repository import AuditTrailRepository
from src.use_cases.pkkpr.pkkpr_service import PKKPRService
from src.use_cases.submit_permohonan import SubmitPermohonanUseCase, SubmitPermohonanInputDto
from src.infrastructure.http.schemas.pkkpr_schemas import (
    SubmitPKKPRRequest,
    GeoJSONPolygonGeometry,
    VerifyPKKPRAdminRequest,
    EvaluatePKKPRSpatialRequest,
    RecordFPRReviewRequest,
    DraftPKKPRSKRequest,
    SignPKKPRKadisRequest
)


def run_test():
    db = SessionLocal()
    print("=" * 70)
    print("MULAI PENGUJIAN INTEGRASI BACKEND PKKPR & SITE PLAN BERTAHAP")
    print("=" * 70)

    try:
        # 1. SETUP USERS
        pemohon = db.query(UserModel).filter(UserModel.role == "PEMOHON").first()
        admin = db.query(UserModel).filter(UserModel.role == "ADMIN").first()
        teknisi = db.query(UserModel).filter(UserModel.role == "TIM_TEKNIS").first()
        kabid = db.query(UserModel).filter(UserModel.role == "KABID_PUPR").first()
        kadis = db.query(UserModel).filter(UserModel.role == "KADIS").first()

        assert pemohon and admin and teknisi and kabid and kadis, "User roles lengkap harus tersedia di database!"

        pkkpr_service = PKKPRService(db)
        pkkpr_repo = PKKPRRepository(db)
        permohonan_repo = PermohonanRepository(db)
        audit_repo = AuditTrailRepository(db)

        submit_siteplan_uc = SubmitPermohonanUseCase(
            permohonan_repo=permohonan_repo,
            audit_trail_repo=audit_repo,
            pkkpr_repo=pkkpr_repo
        )

        # Poligon Induk PKKPR: Area Kotak Besar 30,000 m² (kurang lebih)
        # Koordinat: (106.8000, -6.5800) s.d (106.8040, -6.5840)
        pkkpr_polygon_coords = [
            [106.8000, -6.5800],
            [106.8040, -6.5800],
            [106.8040, -6.5840],
            [106.8000, -6.5840],
            [106.8000, -6.5800]
        ]

        # ─── LANGKAH 1: PENGAJUAN & PENERBITAN SK PKKPR ─────────────────────────
        print("\n[TEST 1] Mengajukan PKKPR Baru...")
        pkkpr_submit_req = SubmitPKKPRRequest(
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120301938192",
            applicant_npwp="01.234.567.8-901.000",
            applicant_phone="081234567890",
            applicant_email="info@sentosaland.co.id",
            category="BERUSAHA_PENILAIAN",
            activity_description="Pembangunan Kawasan Terpadu Sentosa Eco-Park (Master Plan)",
            kbli_code="68111",
            location_address="Jl. Raya Sukaraja No. 88",
            location_village="Cikeas",
            location_district="Sukaraja",
            location_city="Kabupaten Bogor",
            proposed_land_area_m2=30000.0,
            geometry=GeoJSONPolygonGeometry(
                type="Polygon",
                coordinates=[pkkpr_polygon_coords]
            )
        )
        pkkpr_detail = pkkpr_service.submit_new_pkkpr(user_id=pemohon.id, req=pkkpr_submit_req)
        pkkpr_id = pkkpr_detail.id
        print(f"  [OK] PKKPR terdaftar: {pkkpr_id} ({pkkpr_detail.submission_no})")

        # Admin Claim & Verify
        pkkpr_service.claim_admin_lock(pkkpr_id, admin.id)
        pkkpr_service.verify_admin_document(pkkpr_id, admin.id, VerifyPKKPRAdminRequest(action="APPROVE", notes="Dokumen formal lengkap."))
        print("  [OK] Verifikasi Administrasi: LULUS")

        # Technical Claim & Evaluate Spatial
        pkkpr_service.claim_technical_lock(pkkpr_id, teknisi.id)
        pkkpr_service.evaluate_spatial(
            pkkpr_id, 
            teknisi.id, 
            EvaluatePKKPRSpatialRequest(
                approved_land_area_m2=30000.0,
                approved_kdb_max=60.0,
                approved_klb_max=3.0,
                approved_kdh_min=15.0,
                approved_gsb_min=5.0,
                approved_max_floors=4,
                spatial_zone_code="R-2",
                spatial_zone_name="Zona Perumahan Kepadatan Sedang",
                technical_notes="Analisis spasial sesuai pola ruang RDTR Sukaraja."
            )
        )
        print("  [OK] Kajian Teknis Spasial: SELESAI (Luas Disetujui: 30,000 m²)")

        # Record FPR Review
        pkkpr_service.record_fpr_review(
            pkkpr_id,
            teknisi.id,
            RecordFPRReviewRequest(
                meeting_date=date.today(),
                official_report_no=f"BA-FPR/2026/{pkkpr_id[-4:]}",
                recommendation="DISETUJUI_SELURUHNYA",
                zoning_compliance_notes="Kawasan direkomendasikan untuk pengembangan perumahan bertahap."
            )
        )
        print("  [OK] Sidang Komite FPR: DISETUJUI SELURUHNYA")

        # Kabid Draft SK
        pkkpr_service.draft_sk(
            pkkpr_id,
            kabid.id,
            DraftPKKPRSKRequest(
                draft_sk_number=f"503/PKKPR/DPMPTSP/2026/{pkkpr_id[-4:]}",
                considerations=["Menimbang kepentingan tata ruang Kabupaten Bogor"],
                legal_bases=["Perbup Bogor No. 4 Tahun 2025"],
                dictum_clauses={"kesatu": "Menetapkan PKKPR untuk PT Sentosa Land Properti"},
                obligations=["Menyusun Master Plan dan Site Plan Bertahap"]
            )
        )
        print("  [OK] Draf SK Kabid: DIPARAF")

        # Kadis TTE Sign
        final_sk = f"SK-PKKPR-2026-{pkkpr_id[-4:]}"
        pkkpr_approved = pkkpr_service.sign_kadis_tte(
            pkkpr_id,
            kadis.id,
            SignPKKPRKadisRequest(
                final_sk_number=final_sk,
                passphrase_pin="BogorPastiBisa2026!"
            )
        )
        assert pkkpr_approved.status == "DISETUJUI", "Status harus DISETUJUI setelah TTE Kadis!"
        print(f"  [OK] TTE Kadis: BERHASIL (SK Terbit: {pkkpr_approved.sk_number})")

        # ─── LANGKAH 2: PENGAJUAN SITE PLAN TAHAP 1 ──────────────────────────────
        print("\n[TEST 2] Mengajukan Site Plan Tahap 1 (Alokasi: 12,000 m²)...")
        # Sub-polygon Tahap 1: Sisi Barat (106.8000 s.d 106.8020)
        sp1_coords = [
            [106.8001, -6.5801],
            [106.8019, -6.5801],
            [106.8019, -6.5839],
            [106.8001, -6.5839],
            [106.8001, -6.5801]
        ]
        sp1_id = f"sub-sp1-{int(datetime.now(timezone.utc).timestamp())}"
        sp1_no = f"SIPAS-PH1-{int(datetime.now(timezone.utc).timestamp())}"
        dto_sp1 = SubmitPermohonanInputDto(
            id_permohonan=sp1_id,
            submission_no=sp1_no,
            housing_name="Sentosa Eco-Park Tahap 1 (Cluster Amaryllis)",
            developer_name="PT Sentosa Land Properti",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120304050607",
            land_area=12000.0,
            applicant_land_area=12000.0,
            polygon=sp1_coords,
            pkkpr_id=pkkpr_id,
            pkkpr_origin="INTERNAL",
            spatial_kkpr_number=final_sk,
            location_village="Cikeas",
            location_district="Sukaraja",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        sp1_entity = submit_siteplan_uc.execute(dto_sp1)
        permohonan_repo.commit()
        print(f"  [OK] Site Plan Tahap 1 Berhasil Diajukan: ID={sp1_entity.id_permohonan}, Status={sp1_entity.status.value}")

        # ─── LANGKAH 3: VERIFIKASI QUOTA SUMMARY PASCA TAHAP 1 ───────────────────
        print("\n[TEST 3] Memeriksa Kuota Kumulatif Pasca Tahap 1...")
        summary1 = pkkpr_repo.get_quota_summary(pkkpr_id)
        assert summary1 is not None
        print(f"  Total Izin PKKPR : {summary1['total_approved_area_m2']} m²")
        print(f"  Kuota Terpakai   : {summary1['used_area_m2']} m² (Siteplans: {summary1['siteplans_count']})")
        print(f"  Sisa Kuota       : {summary1['remaining_area_m2']} m² ({100 - summary1['utilization_percent']}%)")
        assert summary1['used_area_m2'] == 12000.0, "Used area harus 12,000 m²!"
        assert summary1['remaining_area_m2'] == 18000.0, "Remaining area harus 18,000 m²!"
        print("  [OK] Quota Summary Pasca Tahap 1: VALID 100%")

        # ─── LANGKAH 4: PENGAJUAN SITE PLAN TAHAP 2 ──────────────────────────────
        print("\n[TEST 4] Mengajukan Site Plan Tahap 2 (Alokasi: 10,000 m², Non-overlapping)...")
        # Sub-polygon Tahap 2: Sisi Timur (106.8021 s.d 106.8039)
        sp2_coords = [
            [106.8021, -6.5801],
            [106.8039, -6.5801],
            [106.8039, -6.5839],
            [106.8021, -6.5839],
            [106.8021, -6.5801]
        ]
        sp2_id = f"sub-sp2-{int(datetime.now(timezone.utc).timestamp())}"
        sp2_no = f"SIPAS-PH2-{int(datetime.now(timezone.utc).timestamp())}"
        dto_sp2 = SubmitPermohonanInputDto(
            id_permohonan=sp2_id,
            submission_no=sp2_no,
            housing_name="Sentosa Eco-Park Tahap 2 (Cluster Bougenville)",
            developer_name="PT Sentosa Land Properti",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120304050607",
            land_area=10000.0,
            applicant_land_area=10000.0,
            polygon=sp2_coords,
            pkkpr_id=pkkpr_id,
            pkkpr_origin="INTERNAL",
            spatial_kkpr_number=final_sk,
            location_village="Cikeas",
            location_district="Sukaraja",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        sp2_entity = submit_siteplan_uc.execute(dto_sp2)
        permohonan_repo.commit()
        print(f"  [OK] Site Plan Tahap 2 Berhasil Diajukan: ID={sp2_entity.id_permohonan}, Status={sp2_entity.status.value}")

        summary2 = pkkpr_repo.get_quota_summary(pkkpr_id)
        assert summary2['used_area_m2'] == 22000.0, "Used area kumulatif harus 22,000 m²!"
        assert summary2['remaining_area_m2'] == 8000.0, "Remaining area harus 8,000 m²!"
        assert summary2['siteplans_count'] == 2, "Harus ada 2 Site Plan bertahap aktif!"
        print(f"  [OK] Quota Summary Pasca Tahap 2: Terpakai 22,000 m², Sisa 8,000 m² (VALID)")

        # ─── LANGKAH 5: UJI PENCEGAHAN PELANGGARAN KUOTA (OVER-QUOTA) ───────────
        print("\n[TEST 5] Menguji Penolakan Jika Alokasi Melampaui Sisa Kuota (Minta 10,000 m², sisa hanya 8,000 m²)...")
        sp3_coords_safe = [
            [106.8021, -6.5801],
            [106.8039, -6.5801],
            [106.8039, -6.5820],
            [106.8021, -6.5820],
            [106.8021, -6.5801]
        ]
        sp3_id = f"sub-sp3-fail-{int(datetime.now(timezone.utc).timestamp())}"
        dto_sp3_overquota = SubmitPermohonanInputDto(
            id_permohonan=sp3_id,
            submission_no="SIPAS-2026-PHASE-3-FAIL",
            housing_name="Sentosa Eco-Park Tahap 3 (Rakus Kuota)",
            developer_name="PT Sentosa Land Properti",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120304050607",
            land_area=10000.0, # Melebihi sisa 8,000 m²
            applicant_land_area=10000.0,
            polygon=sp3_coords_safe,
            pkkpr_id=pkkpr_id,
            pkkpr_origin="INTERNAL",
            spatial_kkpr_number=final_sk,
            location_village="Cikeas",
            location_district="Sukaraja",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        try:
            submit_siteplan_uc.execute(dto_sp3_overquota)
            permohonan_repo.rollback()
            raise AssertionError("Gagal: Sistem seharusnya menolak pengajuan yang melebihi kuota!")
        except ValueError as err:
            permohonan_repo.rollback()
            print(f"  [OK] Sistem Berhasil Menolak (Sesuai Aturan): {err}")
            assert "melampaui sisa kuota SK PKKPR" in str(err)

        # ─── LANGKAH 6: UJI PENCEGAHAN PELANGGARAN BATAS SPASIAL PKKPR ──────────
        print("\n[TEST 6] Menguji Penolakan Jika Poligon Keluar dari Batas Izin PKKPR...")
        # Poligon yang menabrak batas barat ke 106.7980 (di luar 106.8000)
        sp_out_coords = [
            [106.7980, -6.5801], # KELUAR BATAS!
            [106.8010, -6.5801],
            [106.8010, -6.5820],
            [106.7980, -6.5820],
            [106.7980, -6.5801]
        ]
        dto_sp_outside = SubmitPermohonanInputDto(
            id_permohonan=f"sub-out-{int(datetime.now(timezone.utc).timestamp())}",
            submission_no="SIPAS-2026-OUTSIDE-FAIL",
            housing_name="Sentosa Eco-Park Tahap Melanggar Batas",
            developer_name="PT Sentosa Land Properti",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120304050607",
            land_area=5000.0,
            applicant_land_area=5000.0,
            polygon=sp_out_coords,
            pkkpr_id=pkkpr_id,
            pkkpr_origin="INTERNAL",
            spatial_kkpr_number=final_sk,
            location_village="Cikeas",
            location_district="Sukaraja",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        try:
            submit_siteplan_uc.execute(dto_sp_outside)
            permohonan_repo.rollback()
            raise AssertionError("Gagal: Sistem seharusnya menolak poligon di luar batas PKKPR!")
        except ValueError as err:
            permohonan_repo.rollback()
            print(f"  [OK] Sistem Berhasil Menolak (Sesuai Aturan): {err}")
            assert "melanggar batas izin SK PKKPR" in str(err)

        # ─── LANGKAH 7: UJI PENCEGAHAN TUMPANG TINDIH ANTAR TAHAP ────────────────
        print("\n[TEST 7] Menguji Penolakan Jika Poligon Menindih Site Plan Tahap 1...")
        # Poligon yang menabrak Tahap 1 persis di area (106.8001 s.d 106.8015)
        sp_overlap_coords = [
            [106.8005, -6.5805],
            [106.8015, -6.5805],
            [106.8015, -6.5825],
            [106.8005, -6.5825],
            [106.8005, -6.5805]
        ]
        dto_sp_overlap = SubmitPermohonanInputDto(
            id_permohonan=f"sub-overlap-{int(datetime.now(timezone.utc).timestamp())}",
            submission_no="SIPAS-2026-OVERLAP-FAIL",
            housing_name="Sentosa Eco-Park Menindih Tahap 1",
            developer_name="PT Sentosa Land Properti",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Sentosa Land Properti",
            applicant_nib="9120304050607",
            land_area=4000.0,
            applicant_land_area=4000.0,
            polygon=sp_overlap_coords,
            pkkpr_id=pkkpr_id,
            pkkpr_origin="INTERNAL",
            spatial_kkpr_number=final_sk,
            location_village="Cikeas",
            location_district="Sukaraja",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        try:
            submit_siteplan_uc.execute(dto_sp_overlap)
            permohonan_repo.rollback()
            raise AssertionError("Gagal: Sistem seharusnya menolak poligon yang tumpang tindih dengan tahap sebelumnya!")
        except ValueError as err:
            permohonan_repo.rollback()
            print(f"  [OK] Sistem Berhasil Menolak (Sesuai Aturan): {err}")
            assert "Tumpang tindih spasial terdeteksi terhadap Site Plan Tahap Sebelumnya" in str(err)

        # ─── LANGKAH 8: UJI PENCEGAHAN PENGAJUAN PADA PKKPR BELUM DISETUJUI ──────
        print("\n[TEST 8] Menguji Penolakan Pengajuan Pada PKKPR yang Masih DRAFT/Belum Terbit SK...")
        draft_pkkpr_req = SubmitPKKPRRequest(
            applicant_type="BADAN_USAHA",
            applicant_name="PT Draft Sejahtera",
            activity_description="Kegiatan Usaha Masih Draf",
            location_address="Jl. Baru",
            location_village="Cikeas",
            location_district="Sukaraja",
            proposed_land_area_m2=10000.0,
            geometry=GeoJSONPolygonGeometry(
                type="Polygon",
                coordinates=[pkkpr_polygon_coords]
            )
        )
        draft_pkkpr = pkkpr_service.submit_new_pkkpr(user_id=pemohon.id, req=draft_pkkpr_req)

        dto_sp_draft_pkkpr = SubmitPermohonanInputDto(
            id_permohonan=f"sub-draft-fail-{int(datetime.now(timezone.utc).timestamp())}",
            submission_no="SIPAS-2026-DRAFT-PKKPR-FAIL",
            housing_name="Site Plan Meninduk Pada PKKPR Draf",
            developer_name="PT Draft Sejahtera",
            applicant_type="BADAN_USAHA",
            applicant_name="PT Draft Sejahtera",
            applicant_nib="9120304050608",
            land_area=5000.0,
            applicant_land_area=5000.0,
            polygon=sp2_coords,
            pkkpr_id=draft_pkkpr.id, # Masih DRAFT
            pkkpr_origin="INTERNAL",
            statement_agreed=True,
            is_draft=False,
            user_id=pemohon.id
        )

        try:
            submit_siteplan_uc.execute(dto_sp_draft_pkkpr)
            permohonan_repo.rollback()
            raise AssertionError("Gagal: Sistem seharusnya menolak pengajuan yang merujuk pada PKKPR yang belum terbit SK!")
        except ValueError as err:
            permohonan_repo.rollback()
            print(f"  [OK] Sistem Berhasil Menolak (Sesuai Aturan): {err}")
            assert "belum berstatus 'DISETUJUI'" in str(err)

        print("\n" + "=" * 70)
        print("SEMUA 8 PENGUJIAN INTEGRASI BACKEND PKKPR BERTAHAP LULUS 100%!")
        print("Sesuai Amanat Perbup Bogor No. 4 Tahun 2025.")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_test()
