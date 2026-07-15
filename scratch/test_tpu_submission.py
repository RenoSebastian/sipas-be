import sys
import uuid
from datetime import date
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database.connection import engine
from src.infrastructure.database.repositories.permohonan_repository import PermohonanRepository
from src.infrastructure.database.repositories.audit_trail_repository import AuditTrailRepository
from src.use_cases.submit_permohonan import SubmitPermohonanUseCase, SubmitPermohonanInputDto
from src.infrastructure.database.models import PermohonanModel, PermohonanTpuModel, LahanKompensasiModel

def run_test():
    print("[TEST] Initializing database session...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        id_perm = f"test-sub-{uuid.uuid4().hex[:8]}"
        sub_no = f"SIPAS-TEST-{uuid.uuid4().hex[:6]}"

        print(f"[TEST] Preparing input DTO for submission ID: {id_perm}...")
        dto = SubmitPermohonanInputDto(
            id_permohonan=id_perm,
            submission_no=sub_no,
            housing_name="Maju Jaya Estate",
            developer_name="PT Developer Sukses",
            land_area=15000.0,
            actor_name="System Tester",
            role="SYSTEM",
            is_draft=True,

            # TPU Details
            tpu_method="KERJASAMA",
            tpu_area=350.0,
            tpu_nama="Makam Muslim Sukamaju",
            tpu_pengurus="Pak Haji Sobri",
            tpu_no_pks="PKS/123/TPU/2026",
            tpu_nominal=0.0,
            tpu_address="Kecamatan Jonggol, Bogor",
            tpu_bukti_dokumen="http://localhost/uploads/tpu/pks_tpu.pdf",

            # Self declared compensations (e.g. LP2B / Sawah replacement)
            self_declared_compensations=[
                {
                    "type": "LAHAN_SAWAH",
                    "requiredAreaM2": 1000.0,
                    "nominalAmount": 0.0,
                    "documentUrl": "http://localhost/uploads/comp/shm_sawah.pdf"
                }
            ]
        )

        permohonan_repo = PermohonanRepository(db)
        audit_repo = AuditTrailRepository(db)
        use_case = SubmitPermohonanUseCase(permohonan_repo, audit_repo)

        print("[TEST] Executing SubmitPermohonanUseCase...")
        result = use_case.execute(dto)

        # Flush to DB to get generated model columns synchronized without committing
        db.flush()

        print("[TEST] Querying PermohonanModel...")
        model = db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_perm).first()
        if not model:
            print("[TEST_FAILED] PermohonanModel not found in database!")
            sys.exit(1)
        
        print("[TEST] Verifying PermohonanTpuModel 1:1 relationship...")
        if not model.tpu_detail:
            print("[TEST_FAILED] PermohonanTpuModel record not created!")
            sys.exit(1)
        
        tpu = model.tpu_detail
        print(f" - TPU ID: {tpu.id_tpu}")
        print(f" - TPU Metode: {tpu.metode}")
        print(f" - TPU Luas: {tpu.luas}")
        print(f" - TPU Nama: {tpu.nama_tpu}")
        print(f" - TPU No PKS: {tpu.no_pks}")
        
        assert tpu.metode == "KERJASAMA"
        assert tpu.luas == 350.0
        assert tpu.nama_tpu == "Makam Muslim Sukamaju"
        assert tpu.no_pks == "PKS/123/TPU/2026"
        assert tpu.bukti_dokumen_url == "http://localhost/uploads/tpu/pks_tpu.pdf"

        print("[TEST] Verifying LahanKompensasiModel relationship...")
        comp_records = db.query(LahanKompensasiModel).filter(LahanKompensasiModel.id_permohonan == id_perm).all()
        if len(comp_records) != 1:
            print(f"[TEST_FAILED] LahanKompensasiModel record count is {len(comp_records)}, expected 1!")
            sys.exit(1)
        
        comp = comp_records[0]
        print(f" - Comp ID: {comp.id_kompensasi}")
        print(f" - Comp Type: {comp.tipe_kompensasi}")
        print(f" - Comp Area: {comp.luas_kompensasi_m2}")
        print(f" - Comp Url: {comp.bukti_legalitas_url}")

        assert comp.tipe_kompensasi == "LAHAN_SAWAH"
        assert comp.luas_kompensasi_m2 == 1000.0
        assert comp.bukti_legalitas_url == "http://localhost/uploads/comp/shm_sawah.pdf"

        # ─── PENGUJIAN BARU: VERIFIKASI PENGHAPUSAN DATA TPU YATIM (PROBLEM 2) ───
        print("[TEST] Verifying Orphan TPU deletion (Problem 2)...")
        dto_update = SubmitPermohonanInputDto(
            id_permohonan=id_perm,
            submission_no=sub_no,
            housing_name="Maju Jaya Estate (Updated)",
            developer_name="PT Developer Sukses",
            land_area=15000.0,
            actor_name="System Tester",
            role="SYSTEM",
            is_draft=True,

            # TPU diubah menjadi None / Dihapus oleh pemohon
            tpu_method=None,
            tpu_area=None,
            tpu_nama=None,
            tpu_pengurus=None,
            tpu_no_pks=None,
            tpu_nominal=None,
            tpu_address=None,
            tpu_bukti_dokumen=None,
            self_declared_compensations=None
        )

        use_case.execute(dto_update)
        db.flush()

        tpu_deleted = db.query(PermohonanTpuModel).filter(PermohonanTpuModel.id_permohonan == id_perm).first()
        if tpu_deleted is not None:
            print("[TEST_FAILED] PermohonanTpuModel record was not deleted when TPU details were cleared!")
            sys.exit(1)
        print(" - TPU record successfully deleted from database.")

        # Re-insert TPU details for subsequent VerifySubmissionUseCase test path
        print("[TEST] Re-preparing TPU details for verification path...")
        dto_reinsert = SubmitPermohonanInputDto(
            id_permohonan=id_perm,
            submission_no=sub_no,
            housing_name="Maju Jaya Estate",
            developer_name="PT Developer Sukses",
            land_area=15000.0,
            actor_name="System Tester",
            role="SYSTEM",
            is_draft=True,
            tpu_method="KERJASAMA",
            tpu_area=350.0,
            tpu_nama="Makam Muslim Sukamaju",
            tpu_pengurus="Pak Haji Sobri",
            tpu_no_pks="PKS/123/TPU/2026",
            tpu_nominal=0.0,
            tpu_address="Kecamatan Jonggol, Bogor",
            tpu_bukti_dokumen="http://localhost/uploads/tpu/pks_tpu.pdf",
            self_declared_compensations=[
                {
                    "type": "LAHAN_SAWAH",
                    "requiredAreaM2": 1000.0,
                    "nominalAmount": 0.0,
                    "documentUrl": "http://localhost/uploads/comp/shm_sawah.pdf"
                }
            ]
        )
        use_case.execute(dto_reinsert)
        db.flush()

        # Re-fetch new tpu reference
        db.refresh(model)
        tpu = model.tpu_detail

        # Transition permohonan to VERIFIKASI_TEKNIS status to perform technical review
        print("[TEST] Transitioning status to Verifikasi Teknis...")
        model.status = "Verifikasi Teknis"
        db.flush()

        print("[TEST] Executing VerifySubmissionUseCase...")
        from src.use_cases.verify_submission import VerifySubmissionUseCase, VerifySubmissionInputDto, EvaluasiChecklistItemDto as UsecaseEvaluasiChecklistItemDto
        from src.infrastructure.database.repositories.telaah_staf_repository import TelaahStafRepository
        from src.infrastructure.database.repositories.sk_draft_repository import SkDraftRepository
        from src.infrastructure.document.pdf_engine import HtmlToPdfEngine
        from src.infrastructure.security.bsre_client import BsreClient

        telaah_repo = TelaahStafRepository(db)
        sk_repo = SkDraftRepository(db)
        doc_gen = HtmlToPdfEngine()
        bsre = BsreClient()

        verify_use_case = VerifySubmissionUseCase(
            permohonan_repo=permohonan_repo,
            telaah_staf_repo=telaah_repo,
            sk_draft_repo=sk_repo,
            document_generator=doc_gen,
            digital_signature_client=bsre,
            audit_trail_repo=audit_repo
        )

        verify_dto = VerifySubmissionInputDto(
            id_permohonan=id_perm,
            actor_name="Tim Teknis Verifikator",
            role="TIM_TEKNIS",
            action_type="SAVE_TECHNICAL_MATRIX",
            notes="Penilaian spasial TPU dan Sawah selesai.",
            kkpr_verdict="SESUAI",
            nip="199208152018032001",
            passphrase=None,
            checklist_items=[
                UsecaseEvaluasiChecklistItemDto(
                    aspek_code="tech_cemetery",
                    aspek_label="Penyediaan Makam",
                    status_kelayakan="SESUAI",
                    catatan_verifikator="Telah diperiksa di peta mini, aman."
                ),
                UsecaseEvaluasiChecklistItemDto(
                    aspek_code=comp.id_kompensasi,
                    aspek_label="Sawah Pengganti",
                    status_kelayakan="SESUAI",
                    catatan_verifikator="Dokumen AJB terlampir lengkap."
                )
            ]
        )

        import asyncio
        asyncio.run(verify_use_case.execute(verify_dto))

        # Flush to check database values
        db.flush()

        print("[TEST] Verifying auto-synced TPU verification status...")
        db.refresh(tpu)
        print(f" - TPU Status setelah Verifikasi: {tpu.status_verifikasi}")
        print(f" - TPU Catatan setelah Verifikasi: {tpu.catatan_verifikasi}")
        assert tpu.status_verifikasi == "APPROVED"
        assert tpu.catatan_verifikasi == "Telah diperiksa di peta mini, aman."

        print("[TEST] Verifying auto-synced LahanKompensasi status...")
        db.refresh(comp)
        print(f" - Comp Status setelah Verifikasi: {comp.status_pemenuhan}")
        assert comp.status_pemenuhan == "TERPENUHI"

        print("[TEST_SUCCESS] All assertions passed successfully!")
    
    except Exception as e:
        print(f"[TEST_ERROR] Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("[TEST] Rolling back database changes to clean up...")
        db.rollback()
        db.close()

if __name__ == "__main__":
    run_test()
