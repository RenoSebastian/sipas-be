"""
============================================================================
SIPAS DOMAIN ENTITY — PKKPR Module [pkkpr.py]
============================================================================
Peran: Entitas domain bisnis murni (Pure Python) yang merepresentasikan
       permohonan Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang (PKKPR),
       menegakkan aturan transisi status (State Machine), penugasan sidang FPR,
       penguncian berkas petugas, serta formulasi batas parameter ruang.
============================================================================
"""

from datetime import date, datetime
from typing import List, Optional, Any, Dict
from src.domain.value_objects.pkkpr_status import (
    PKKPRStatus,
    PKKPRCategory,
    FPRRecommendation,
    PKKPRFileType,
    SpatialEnvelope
)


class PKKPRFile:
    """Entitas lampiran berkas persyaratan PKKPR."""
    def __init__(
        self,
        id: Optional[int],
        pkkpr_id: str,
        file_type: PKKPRFileType,
        file_name: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        uploaded_at: Optional[datetime] = None
    ):
        self.id = id
        self.pkkpr_id = pkkpr_id
        self.file_type = file_type
        self.file_name = file_name
        self.file_path = file_path
        self.file_size = file_size
        self.mime_type = mime_type
        self.uploaded_at = uploaded_at or datetime.now()


class FPRReview:
    """Entitas hasil sidang notula Forum Penataan Ruang (FPR)."""
    def __init__(
        self,
        id: Optional[int],
        pkkpr_id: str,
        meeting_date: date,
        official_report_no: str,
        recommendation: FPRRecommendation,
        zoning_compliance_notes: str,
        created_by_id: int,
        ptp_bpn_number: Optional[str] = None,
        ptp_bpn_date: Optional[date] = None,
        ptp_notes: Optional[str] = None,
        infrastructure_notes: Optional[str] = None,
        environmental_notes: Optional[str] = None,
        minutes_pdf_url: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.pkkpr_id = pkkpr_id
        self.meeting_date = meeting_date
        self.official_report_no = official_report_no
        self.recommendation = recommendation
        self.zoning_compliance_notes = zoning_compliance_notes
        self.created_by_id = created_by_id
        self.ptp_bpn_number = ptp_bpn_number
        self.ptp_bpn_date = ptp_bpn_date
        self.ptp_notes = ptp_notes
        self.infrastructure_notes = infrastructure_notes
        self.environmental_notes = environmental_notes
        self.minutes_pdf_url = minutes_pdf_url
        self.created_at = created_at or datetime.now()


class PKKPRDraftSK:
    """Entitas draf Surat Keputusan penetapan PKKPR sebelum TTE Kadis."""
    def __init__(
        self,
        id: Optional[int],
        pkkpr_id: str,
        draft_sk_number: str,
        prepared_by_id: int,
        considerations: Optional[List[str]] = None,
        legal_bases: Optional[List[str]] = None,
        dictum_clauses: Optional[Dict[str, Any]] = None,
        obligations: Optional[List[str]] = None,
        kabid_notes: Optional[str] = None,
        kabid_paraf_hash: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.pkkpr_id = pkkpr_id
        self.draft_sk_number = draft_sk_number
        self.prepared_by_id = prepared_by_id
        self.considerations = considerations or []
        self.legal_bases = legal_bases or []
        self.dictum_clauses = dictum_clauses or {}
        self.obligations = obligations or []
        self.kabid_notes = kabid_notes
        self.kabid_paraf_hash = kabid_paraf_hash
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()


class PermohonanPKKPR:
    """
    Entitas Bisnis Utama PKKPR.
    Mengatur seluruh siklus hidup kesesuaian ruang dari pengajuan hingga SK terbit.
    """
    def __init__(
        self,
        id: str,
        submission_no: str,
        user_id: int,
        applicant_name: str,
        activity_description: str,
        location_address: str,
        location_village: str,
        location_district: str,
        proposed_land_area_m2: float,
        geom_geojson: Any,
        category: PKKPRCategory = PKKPRCategory.BERUSAHA_PENILAIAN,
        status: PKKPRStatus = PKKPRStatus.DRAFT,
        applicant_type: str = "BADAN_USAHA",
        applicant_nik: Optional[str] = None,
        applicant_nib: Optional[str] = None,
        applicant_npwp: Optional[str] = None,
        applicant_phone: Optional[str] = None,
        applicant_email: Optional[str] = None,
        kbli_code: Optional[str] = None,
        location_city: str = "Kabupaten Bogor",
        land_ownership_status: Optional[str] = "SHM",
        certificate_number: Optional[str] = None,
        certificate_owner: Optional[str] = None,
        approved_land_area_m2: Optional[float] = None,
        envelope: Optional[SpatialEnvelope] = None,
        admin_lock_id: Optional[int] = None,
        technical_lock_id: Optional[int] = None,
        sla_start_date: Optional[date] = None,
        elapsed_days: int = 0,
        buffer_sla: int = 0,
        sk_number: Optional[str] = None,
        sk_issued_date: Optional[date] = None,
        signed_pdf_url: Optional[str] = None,
        qr_code_hash: Optional[str] = None,
        files: Optional[List[PKKPRFile]] = None,
        fpr_reviews: Optional[List[FPRReview]] = None,
        sk_draft: Optional[PKKPRDraftSK] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.submission_no = submission_no
        self.user_id = user_id
        self.applicant_name = applicant_name
        self.activity_description = activity_description
        self.location_address = location_address
        self.location_village = location_village
        self.location_district = location_district
        self.location_city = location_city
        self.proposed_land_area_m2 = proposed_land_area_m2
        self.geom_geojson = geom_geojson
        self.category = category
        self.status = status
        self.applicant_type = applicant_type
        self.applicant_nik = applicant_nik
        self.applicant_nib = applicant_nib
        self.applicant_npwp = applicant_npwp
        self.applicant_phone = applicant_phone
        self.applicant_email = applicant_email
        self.kbli_code = kbli_code
        self.land_ownership_status = land_ownership_status
        self.certificate_number = certificate_number
        self.certificate_owner = certificate_owner
        self.approved_land_area_m2 = approved_land_area_m2
        self.envelope = envelope or SpatialEnvelope()
        self.admin_lock_id = admin_lock_id
        self.technical_lock_id = technical_lock_id
        self.sla_start_date = sla_start_date
        self.elapsed_days = elapsed_days
        self.buffer_sla = buffer_sla
        self.sk_number = sk_number
        self.sk_issued_date = sk_issued_date
        self.signed_pdf_url = signed_pdf_url
        self.qr_code_hash = qr_code_hash
        self.files = files or []
        self.fpr_reviews = fpr_reviews or []
        self.sk_draft = sk_draft
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    # ─── STATE MACHINE TRANSITIONS (BUSINESS INVARIANTS) ───────────────────

    def submit_application(self) -> None:
        """Pemohon mengajukan berkas secara resmi (mengaktifkan SLA)."""
        if self.status != PKKPRStatus.DRAFT:
            raise ValueError(f"Hanya berkas berstatus DRAFT yang dapat diajukan (status saat ini: {self.status.value}).")
        if self.proposed_land_area_m2 <= 0:
            raise ValueError("Luas lahan yang dimohonkan harus bernilai positif.")
        if not self.geom_geojson:
            raise ValueError("Poligon batas lahan wajib ditentukan.")
        
        self.status = PKKPRStatus.PENGAJUAN_BERKAS
        self.sla_start_date = date.today()
        self.updated_at = datetime.now()

    def claim_admin(self, user_id: int) -> None:
        """Admin mengunci berkas untuk memulai verifikasi formal."""
        if self.status not in (PKKPRStatus.PENGAJUAN_BERKAS, PKKPRStatus.VERIFIKASI_ADMINISTRASI):
            raise ValueError(f"Berkas tidak berada pada tahap verifikasi administrasi (status: {self.status.value}).")
        if self.admin_lock_id and self.admin_lock_id != user_id:
            raise ValueError(f"Berkas sedang dikunci dan diperiksa oleh admin lain (User ID: {self.admin_lock_id}).")
        
        self.admin_lock_id = user_id
        self.status = PKKPRStatus.VERIFIKASI_ADMINISTRASI
        self.updated_at = datetime.now()

    def release_admin(self, user_id: int) -> None:
        """Admin melepas kunci berkas."""
        if self.admin_lock_id != user_id:
            raise ValueError("Hanya petugas yang mengunci yang dapat melepaskan kunci.")
        self.admin_lock_id = None
        self.updated_at = datetime.now()

    def approve_admin_verification(self) -> None:
        """Admin meloloskan kelengkapan formal, meneruskan ke Tim Teknis."""
        if self.status != PKKPRStatus.VERIFIKASI_ADMINISTRASI:
            raise ValueError("Berkas harus dalam status VERIFIKASI_ADMINISTRASI untuk disetujui.")
        self.status = PKKPRStatus.KAJIAN_TEKNIS_SPASIAL
        self.admin_lock_id = None
        self.updated_at = datetime.now()

    def claim_technical(self, user_id: int) -> None:
        """Tim Teknis mengunci berkas untuk telaah spasial."""
        if self.status not in (PKKPRStatus.KAJIAN_TEKNIS_SPASIAL, PKKPRStatus.SIDANG_FPR):
            raise ValueError("Berkas belum berada pada tahap kajian teknis spasial dinas.")
        if self.technical_lock_id and self.technical_lock_id != user_id:
            raise ValueError(f"Berkas sedang dikunci oleh tim teknis lain (User ID: {self.technical_lock_id}).")
        
        self.technical_lock_id = user_id
        self.updated_at = datetime.now()

    def release_technical(self, user_id: int) -> None:
        """Tim Teknis melepas kunci berkas."""
        if self.technical_lock_id != user_id:
            raise ValueError("Hanya petugas teknis terkait yang dapat melepaskan kunci.")
        self.technical_lock_id = None
        self.updated_at = datetime.now()

    def set_spatial_assessment(
        self,
        envelope: SpatialEnvelope,
        approved_area: float
    ) -> None:
        """Tim Teknis menetapkan hasil analisis pola ruang dan luas disetujui."""
        if self.status != PKKPRStatus.KAJIAN_TEKNIS_SPASIAL:
            raise ValueError("Kajian spasial hanya dapat dimasukkan saat status KAJIAN_TEKNIS_SPASIAL.")
        if approved_area > self.proposed_land_area_m2:
            raise ValueError("Luas yang disetujui tidak boleh melebihi luas yang dimohonkan.")
        
        self.envelope = envelope
        self.approved_land_area_m2 = approved_area
        self.status = PKKPRStatus.SIDANG_FPR
        self.updated_at = datetime.now()

    def finalize_fpr_review(self, review: FPRReview) -> None:
        """Menyimpan hasil sidang komite Forum Penataan Ruang (FPR)."""
        if self.status != PKKPRStatus.SIDANG_FPR:
            raise ValueError("Rekomendasi sidang FPR hanya dapat dicatat saat status SIDANG_FPR.")
        
        self.fpr_reviews.append(review)
        if review.recommendation in (FPRRecommendation.DISETUJUI_SELURUHNYA, FPRRecommendation.DISETUJUI_SEBAGIAN):
            self.status = PKKPRStatus.MENUNGGU_REKOMENDASI_KABID
        else:
            self.status = PKKPRStatus.DITOLAK
        
        self.technical_lock_id = None
        self.updated_at = datetime.now()

    def formulate_sk_draft(self, draft: PKKPRDraftSK) -> None:
        """Kabid merumuskan dan memaraf draf naskah SK penetapan."""
        if self.status != PKKPRStatus.MENUNGGU_REKOMENDASI_KABID:
            raise ValueError("Perumusan draf SK hanya dapat dilakukan saat MENUNGGU_REKOMENDASI_KABID.")
        
        self.sk_draft = draft
        self.status = PKKPRStatus.MENUNGGU_TTE_KADIS
        self.updated_at = datetime.now()

    def sign_kadis_tte(
        self,
        final_sk_number: str,
        signed_pdf_url: str,
        qr_hash: str
    ) -> None:
        """Kepala Dinas mengesahkan SK resmi dengan TTE BSrE."""
        if self.status != PKKPRStatus.MENUNGGU_TTE_KADIS:
            raise ValueError("Otorisasi TTE Kadis hanya dapat dilakukan saat status MENUNGGU_TTE_KADIS.")
        
        self.sk_number = final_sk_number
        self.sk_issued_date = date.today()
        self.signed_pdf_url = signed_pdf_url
        self.qr_code_hash = qr_hash
        self.status = PKKPRStatus.DISETUJUI
        self.updated_at = datetime.now()

    def reject(self, reason: str) -> None:
        """Dinas menolak berkas permohonan."""
        self.status = PKKPRStatus.DITOLAK
        self.admin_lock_id = None
        self.technical_lock_id = None
        self.updated_at = datetime.now()
