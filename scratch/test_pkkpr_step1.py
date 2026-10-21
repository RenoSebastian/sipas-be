import sys
from src.infrastructure.database.connection import SessionLocal
from src.use_cases.pkkpr.pkkpr_service import PKKPRService
from src.infrastructure.http.schemas.pkkpr_schemas import (
    SubmitPKKPRRequest,
    GeoJSONPolygonGeometry,
    PKKPRFileItemRequest
)
from src.infrastructure.database.models import UserModel, PKKPRSubmissionModel, PKKPRFileModel

def run_test():
    db = SessionLocal()
    service = PKKPRService(db)
    
    # 1. Get a test applicant user (e.g. PEMOHON)
    user = db.query(UserModel).filter(UserModel.role == "PEMOHON").first()
    if not user:
        user = db.query(UserModel).first()
    print(f"Using user: {user.full_name} (ID: {user.id}, Role: {user.role})")

    # 2. Prepare submission request with ownership & files
    sample_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [106.827153, -6.597147],
                [106.828153, -6.597147],
                [106.828153, -6.598147],
                [106.827153, -6.598147],
                [106.827153, -6.597147]
            ]
        ]
    }

    files = [
        PKKPRFileItemRequest(
            file_type="BUKTI_HAK_TANAH",
            file_name="sertifikat_shm_01234.pdf",
            file_path="uploads/pkkpr/test_shm.pdf",
            file_size=102400,
            mime_type="application/pdf"
        ),
        PKKPRFileItemRequest(
            file_type="PROPOSAL_TEKNIS",
            file_name="proposal_kegiatan.pdf",
            file_path="uploads/pkkpr/test_proposal.pdf",
            file_size=204800,
            mime_type="application/pdf"
        )
    ]

    req = SubmitPKKPRRequest(
        applicant_type="BADAN_USAHA",
        applicant_name="PT Sentosa Mandiri Properti",
        applicant_nik="3201012345678901",
        applicant_nib="9120001234567",
        applicant_npwp="01.234.567.8-403.000",
        applicant_phone="081234567890",
        applicant_email="sentosa@properti.co.id",
        category="BERUSAHA_PENILAIAN",
        activity_description="Pembangunan Perumahan dan Kawasan Komersial Terpadu",
        kbli_code="68111",
        location_address="Jl. Raya Sukaraja No. 45",
        location_village="Cijujung",
        location_district="Sukaraja",
        location_city="Kabupaten Bogor",
        land_ownership_status="SHM",
        certificate_number="SHM No. 04821/Cijujung",
        certificate_owner="PT Sentosa Mandiri Properti",
        proposed_land_area_m2=12500.0,
        geometry=GeoJSONPolygonGeometry(**sample_geom),
        files=files
    )

    try:
        detail = service.submit_new_pkkpr(user_id=user.id, req=req)
        print("Submission created successfully!")
        print(f"ID: {detail.id}")
        print(f"Submission No: {detail.submission_no}")
        print(f"Land Ownership Status: {detail.land_ownership_status}")
        print(f"Certificate Number: {detail.certificate_number}")
        print(f"Certificate Owner: {detail.certificate_owner}")
        print(f"Attached Files Count: {len(detail.files)}")
        for f in detail.files:
            print(f"  - [{f.file_type}] {f.file_name} ({f.file_size} bytes)")

        # Verify assertions
        assert detail.land_ownership_status == "SHM"
        assert detail.certificate_number == "SHM No. 04821/Cijujung"
        assert len(detail.files) == 2
        print("ALL ASSERTIONS PASSED!")

        # Clean up test submission
        db.query(PKKPRFileModel).filter(PKKPRFileModel.pkkpr_id == detail.id).delete()
        db.query(PKKPRSubmissionModel).filter(PKKPRSubmissionModel.id == detail.id).delete()
        db.commit()
        print("Test record cleaned up cleanly.")
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
