"""
============================================================================
SIPAS USE CASE SERVICE — PKKPR Business Orchestrator [pkkpr_service.py]
============================================================================
Peran: Mengorkestrasi aturan bisnis, state machine, audit trail, serta
       kalkulasi spasial untuk modul PKKPR secara utuh dan transaksional.
============================================================================
"""

import hashlib
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session

from src.infrastructure.database.repositories.pkkpr_repository import PKKPRRepository
from src.infrastructure.database.models import (
    PKKPRSubmissionModel,
    AuditTrailModel,
    UserModel
)
from src.domain.entities.pkkpr import PermohonanPKKPR, FPRReview, PKKPRDraftSK
from src.domain.value_objects.pkkpr_status import (
    PKKPRStatus,
    PKKPRCategory,
    FPRRecommendation,
    SpatialEnvelope
)
from src.infrastructure.http.schemas.pkkpr_schemas import (
    SubmitPKKPRRequest,
    VerifyPKKPRAdminRequest,
    EvaluatePKKPRSpatialRequest,
    RecordFPRReviewRequest,
    DraftPKKPRSKRequest,
    SignPKKPRKadisRequest,
    PKKPRListItemResponse,
    PKKPRDetailResponse,
    PKKPRFileResponse,
    FPRReviewResponse,
    PKKPRDraftSKResponse
)


class PKKPRService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PKKPRRepository(db)

    def _log_audit(
        self,
        pkkpr_id: str,
        action: str,
        actor_id: int,
        details: str,
        status_before: str = "DRAFT",
        status_after: str = "DRAFT"
    ) -> None:
        """Mencatat aktivitas mutasi ke tabel audit_trail."""
        actor = self.db.query(UserModel).filter(UserModel.id == actor_id).first()
        actor_name = actor.full_name if actor else f"User#{actor_id}"
        log = AuditTrailModel(
            submission_id=pkkpr_id,
            action=action,
            actor_name=actor_name,
            role=actor.role if actor else "SYSTEM",
            status_before=status_before,
            status_after=status_after,
            notes=details
        )
        self.db.add(log)
        self.db.commit()

    def submit_new_pkkpr(
        self,
        user_id: int,
        req: SubmitPKKPRRequest
    ) -> PKKPRDetailResponse:
        """Pemohon mengajukan permohonan PKKPR baru."""
        # 1. Cek tumpang tindih spasial
        conflicts = self.repo.check_spatial_overlap(req.geometry.model_dump())
        if conflicts:
            conflict_names = ", ".join([f"{c['submission_no']} ({c['applicant_name']})" for c in conflicts])
            # Catatan: Bila ingin hard blocking atau soft warning, kita sertakan rincian
            # Di sini kita izinkan jika tumpang tindih bukan 100%, tapi jika tabrakan izin disetujui, beri peringatan

        # 2. Generate Nomor & ID
        pkkpr_id = self.repo.generate_id()
        submission_no = self.repo.generate_submission_no()

        # 3. Buat Entitas Domain
        entity = PermohonanPKKPR(
            id=pkkpr_id,
            submission_no=submission_no,
            user_id=user_id,
            applicant_name=req.applicant_name,
            activity_description=req.activity_description,
            location_address=req.location_address,
            location_village=req.location_village,
            location_district=req.location_district,
            location_city=req.location_city,
            proposed_land_area_m2=req.proposed_land_area_m2,
            geom_geojson=req.geometry.model_dump(),
            category=PKKPRCategory(req.category),
            applicant_type=req.applicant_type,
            applicant_nik=req.applicant_nik,
            applicant_nib=req.applicant_nib,
            applicant_npwp=req.applicant_npwp,
            applicant_phone=req.applicant_phone,
            applicant_email=req.applicant_email,
            kbli_code=req.kbli_code,
            land_ownership_status=req.land_ownership_status,
            certificate_number=req.certificate_number,
            certificate_owner=req.certificate_owner
        )

        # Aktifkan permohonan resmi
        entity.submit_application()

        # 4. Simpan ke Database
        files_data = [f.model_dump() for f in req.files] if req.files else None
        saved_model = self.repo.save_submission(entity, files=files_data)

        # 5. Audit Log
        self._log_audit(
            pkkpr_id,
            "SUBMIT_PKKPR",
            user_id,
            f"Pengajuan permohonan PKKPR baru nomor {submission_no} dengan luas {req.proposed_land_area_m2} m²."
        )

        return self.get_detail(pkkpr_id)

    def claim_admin_lock(self, pkkpr_id: str, admin_user_id: int) -> PKKPRDetailResponse:
        """Admin mengunci berkas verifikasi administrasi."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if model.admin_lock_id and model.admin_lock_id != admin_user_id:
            locked_by = model.admin_lock.full_name if model.admin_lock else f"User#{model.admin_lock_id}"
            raise ValueError(f"Berkas sedang dikunci oleh admin lain ({locked_by}).")

        model.admin_lock_id = admin_user_id
        model.status = PKKPRStatus.VERIFIKASI_ADMINISTRASI.value
        self.db.commit()

        self._log_audit(pkkpr_id, "CLAIM_ADMIN", admin_user_id, "Admin mengunci berkas untuk verifikasi berkas formal.")
        return self.get_detail(pkkpr_id)

    def release_admin_lock(self, pkkpr_id: str, admin_user_id: int) -> PKKPRDetailResponse:
        """Admin melepaskan kunci berkas."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if model.admin_lock_id != admin_user_id:
            raise ValueError("Anda tidak memiliki hak untuk melepaskan kunci berkas ini.")

        model.admin_lock_id = None
        self.db.commit()

        self._log_audit(pkkpr_id, "RELEASE_ADMIN", admin_user_id, "Admin melepaskan kunci berkas.")
        return self.get_detail(pkkpr_id)

    def verify_admin_document(
        self,
        pkkpr_id: str,
        admin_user_id: int,
        req: VerifyPKKPRAdminRequest
    ) -> PKKPRDetailResponse:
        """Admin memverifikasi berkas formal (Approve / Reject)."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if req.action == "APPROVE":
            model.status = PKKPRStatus.KAJIAN_TEKNIS_SPASIAL.value
            model.admin_lock_id = None
            action_desc = "Admin meloloskan berkas administrasi. Berkas diteruskan ke Tim Teknis PUPR."
        else:
            model.status = PKKPRStatus.DITOLAK.value
            model.admin_lock_id = None
            action_desc = f"Admin menolak berkas formal. Catatan: {req.notes or '-'}"

        self.db.commit()
        self._log_audit(pkkpr_id, f"VERIFY_ADMIN_{req.action}", admin_user_id, action_desc)
        return self.get_detail(pkkpr_id)

    def claim_technical_lock(self, pkkpr_id: str, tech_user_id: int) -> PKKPRDetailResponse:
        """Tim Teknis mengunci berkas untuk telaah spasial."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if model.technical_lock_id and model.technical_lock_id != tech_user_id:
            locked_by = model.technical_lock.full_name if model.technical_lock else f"User#{model.technical_lock_id}"
            raise ValueError(f"Berkas sedang ditelaah oleh tim teknis lain ({locked_by}).")

        model.technical_lock_id = tech_user_id
        self.db.commit()

        self._log_audit(pkkpr_id, "CLAIM_TECHNICAL", tech_user_id, "Tim Teknis mengunci berkas untuk telaah spasial.")
        return self.get_detail(pkkpr_id)

    def release_technical_lock(self, pkkpr_id: str, tech_user_id: int) -> PKKPRDetailResponse:
        """Tim Teknis melepaskan kunci berkas."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if model.technical_lock_id != tech_user_id:
            raise ValueError("Anda tidak memiliki hak untuk melepaskan kunci berkas ini.")

        model.technical_lock_id = None
        self.db.commit()

        self._log_audit(pkkpr_id, "RELEASE_TECHNICAL", tech_user_id, "Tim Teknis melepaskan kunci berkas.")
        return self.get_detail(pkkpr_id)

    def evaluate_spatial(
        self,
        pkkpr_id: str,
        tech_user_id: int,
        req: EvaluatePKKPRSpatialRequest
    ) -> PKKPRDetailResponse:
        """Tim Teknis memasukkan parameter hasil analisis spasial dinas."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        if req.approved_land_area_m2 > model.proposed_land_area_m2:
            raise ValueError(
                f"Luas disetujui ({req.approved_land_area_m2} m²) tidak boleh melebihi luas permohonan ({model.proposed_land_area_m2} m²)."
            )

        model.approved_land_area_m2 = req.approved_land_area_m2
        model.approved_kdb_max = req.approved_kdb_max
        model.approved_klb_max = req.approved_klb_max
        model.approved_kdh_min = req.approved_kdh_min
        model.approved_gsb_min = req.approved_gsb_min
        model.approved_max_floors = req.approved_max_floors
        model.spatial_zone_code = req.spatial_zone_code
        model.spatial_zone_name = req.spatial_zone_name
        model.status = PKKPRStatus.SIDANG_FPR.value
        self.db.commit()

        self._log_audit(
            pkkpr_id,
            "SPATIAL_EVALUATED",
            tech_user_id,
            f"Kajian spasial selesai: Zona {req.spatial_zone_code}, Luas Disetujui {req.approved_land_area_m2} m², KDB maks {req.approved_kdb_max}%. Status lanjut ke Sidang FPR."
        )
        return self.get_detail(pkkpr_id)

    def record_fpr_review(
        self,
        pkkpr_id: str,
        actor_id: int,
        req: RecordFPRReviewRequest
    ) -> PKKPRDetailResponse:
        """Mencatat notula dan rekomendasi sidang komite Forum Penataan Ruang (FPR)."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        review_entity = FPRReview(
            id=None,
            pkkpr_id=pkkpr_id,
            meeting_date=req.meeting_date,
            official_report_no=req.official_report_no,
            recommendation=FPRRecommendation(req.recommendation),
            zoning_compliance_notes=req.zoning_compliance_notes,
            created_by_id=actor_id,
            ptp_bpn_number=req.ptp_bpn_number,
            ptp_bpn_date=req.ptp_bpn_date,
            ptp_notes=req.ptp_notes,
            infrastructure_notes=req.infrastructure_notes,
            environmental_notes=req.environmental_notes,
            minutes_pdf_url=req.minutes_pdf_url
        )
        self.repo.add_fpr_review(review_entity)

        if req.recommendation in ("DISETUJUI_SELURUHNYA", "DISETUJUI_SEBAGIAN"):
            model.status = PKKPRStatus.MENUNGGU_REKOMENDASI_KABID.value
            action_desc = f"Sidang FPR merekomendasikan: {req.recommendation}. Berkas diteruskan ke Kabid untuk draf SK."
        else:
            model.status = PKKPRStatus.DITOLAK.value
            action_desc = f"Sidang FPR menolak permohonan. Catatan: {req.zoning_compliance_notes}"

        model.technical_lock_id = None
        self.db.commit()

        self._log_audit(pkkpr_id, "RECORD_FPR_REVIEW", actor_id, action_desc)
        return self.get_detail(pkkpr_id)

    def draft_sk(
        self,
        pkkpr_id: str,
        kabid_user_id: int,
        req: DraftPKKPRSKRequest
    ) -> PKKPRDetailResponse:
        """Kabid menyusun draf diktum SK penetapan PKKPR."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        draft_entity = PKKPRDraftSK(
            id=None,
            pkkpr_id=pkkpr_id,
            draft_sk_number=req.draft_sk_number,
            prepared_by_id=kabid_user_id,
            considerations=req.considerations,
            legal_bases=req.legal_bases,
            dictum_clauses=req.dictum_clauses,
            obligations=req.obligations,
            kabid_notes=req.kabid_notes,
            kabid_paraf_hash=req.kabid_paraf_hash
        )
        self.repo.save_sk_draft(draft_entity)

        model.status = PKKPRStatus.MENUNGGU_TTE_KADIS.value
        self.db.commit()

        self._log_audit(
            pkkpr_id,
            "DRAFT_SK_KABID",
            kabid_user_id,
            f"Kabid memaraf draf SK nomor {req.draft_sk_number}. Berkas siap ditandatangani TTE oleh Kadis."
        )
        return self.get_detail(pkkpr_id)

    def sign_kadis_tte(
        self,
        pkkpr_id: str,
        kadis_user_id: int,
        req: SignPKKPRKadisRequest
    ) -> PKKPRDetailResponse:
        """Kepala Dinas menerbitkan dan menandatangani SK resmi dengan TTE BSrE."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        # Simulasi verifikasi passphrase TTE
        if len(req.passphrase_pin) < 4:
            raise ValueError("Passphrase TTE tidak valid.")

        # Generate Hash Integritas Kriptografis
        raw_token = f"{pkkpr_id}:{req.final_sk_number}:{datetime.utcnow().isoformat()}"
        qr_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        model.sk_number = req.final_sk_number
        model.sk_issued_date = date.today()
        model.qr_code_hash = qr_hash
        model.signed_pdf_url = f"/api/pkkpr/{pkkpr_id}/download-sk"
        model.status = PKKPRStatus.DISETUJUI.value
        self.db.commit()

        self._log_audit(
            pkkpr_id,
            "TTE_KADIS_APPROVED",
            kadis_user_id,
            f"Kepala Dinas menandatangani SK PKKPR resmi nomor {req.final_sk_number} via TTE BSrE. Status: DISETUJUI."
        )
        return self.get_detail(pkkpr_id)

    def list_submissions(
        self,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[PKKPRListItemResponse]:
        """Mengambil daftar antrean permohonan PKKPR."""
        rows = self.repo.list_submissions(user_id=user_id, role=role, status=status)
        results = []
        for model, admin_name, tech_name in rows:
            results.append(PKKPRListItemResponse(
                id=model.id,
                submission_no=model.submission_no,
                applicant_name=model.applicant_name,
                category=model.category,
                status=model.status,
                proposed_land_area_m2=model.proposed_land_area_m2,
                location_village=model.location_village,
                location_district=model.location_district,
                created_at=model.created_at,
                elapsed_days=model.elapsed_days,
                sla_start_date=model.sla_start_date,
                sk_number=model.sk_number,
                admin_lock_name=admin_name,
                technical_lock_name=tech_name
            ))
        return results

    def get_detail(self, pkkpr_id: str) -> PKKPRDetailResponse:
        """Mengambil detail lengkap permohonan PKKPR."""
        model = self.repo.get_by_id(pkkpr_id)
        if not model:
            raise ValueError(f"Permohonan PKKPR {pkkpr_id} tidak ditemukan.")

        geom_dict = self.repo.get_geojson_geometry(pkkpr_id)

        admin_name = model.admin_lock.full_name if model.admin_lock else None
        tech_name = model.technical_lock.full_name if model.technical_lock else None

        file_responses = [
            PKKPRFileResponse(
                id=f.id,
                file_type=f.file_type,
                file_name=f.file_name,
                file_path=f.file_path,
                file_size=f.file_size,
                mime_type=f.mime_type,
                uploaded_at=f.uploaded_at
            ) for f in model.files
        ]

        fpr_responses = [
            FPRReviewResponse(
                id=r.id,
                meeting_date=r.meeting_date,
                official_report_no=r.official_report_no,
                recommendation=r.recommendation,
                ptp_bpn_number=r.ptp_bpn_number,
                ptp_bpn_date=r.ptp_bpn_date,
                ptp_notes=r.ptp_notes,
                zoning_compliance_notes=r.zoning_compliance_notes,
                infrastructure_notes=r.infrastructure_notes,
                environmental_notes=r.environmental_notes,
                minutes_pdf_url=r.minutes_pdf_url,
                created_at=r.created_at
            ) for r in model.fpr_reviews
        ]

        sk_draft_resp = None
        if model.sk_draft:
            sk_draft_resp = PKKPRDraftSKResponse(
                id=model.sk_draft.id,
                draft_sk_number=model.sk_draft.draft_sk_number,
                considerations=model.sk_draft.considerations,
                legal_bases=model.sk_draft.legal_bases,
                dictum_clauses=model.sk_draft.dictum_clauses,
                obligations=model.sk_draft.obligations,
                kabid_notes=model.sk_draft.kabid_notes,
                kabid_paraf_hash=model.sk_draft.kabid_paraf_hash,
                created_at=model.sk_draft.created_at
            )

        return PKKPRDetailResponse(
            id=model.id,
            submission_no=model.submission_no,
            user_id=model.user_id,
            applicant_type=model.applicant_type,
            applicant_name=model.applicant_name,
            applicant_nik=model.applicant_nik,
            applicant_nib=model.applicant_nib,
            applicant_npwp=model.applicant_npwp,
            applicant_phone=model.applicant_phone,
            applicant_email=model.applicant_email,
            category=model.category,
            status=model.status,
            activity_description=model.activity_description,
            kbli_code=model.kbli_code,
            location_address=model.location_address,
            location_village=model.location_village,
            location_district=model.location_district,
            location_city=model.location_city,
            land_ownership_status=model.land_ownership_status,
            certificate_number=model.certificate_number,
            certificate_owner=model.certificate_owner,
            proposed_land_area_m2=model.proposed_land_area_m2,
            approved_land_area_m2=model.approved_land_area_m2,
            approved_kdb_max=model.approved_kdb_max,
            approved_klb_max=model.approved_klb_max,
            approved_kdh_min=model.approved_kdh_min,
            approved_gsb_min=model.approved_gsb_min,
            approved_max_floors=model.approved_max_floors,
            spatial_zone_code=model.spatial_zone_code,
            spatial_zone_name=model.spatial_zone_name,
            geometry=geom_dict,
            admin_lock_id=model.admin_lock_id,
            admin_lock_name=admin_name,
            technical_lock_id=model.technical_lock_id,
            technical_lock_name=tech_name,
            sk_number=model.sk_number,
            sk_issued_date=model.sk_issued_date,
            signed_pdf_url=model.signed_pdf_url,
            qr_code_hash=model.qr_code_hash,
            files=file_responses,
            fpr_reviews=fpr_responses,
            sk_draft=sk_draft_resp,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
