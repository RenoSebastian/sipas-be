"""
============================================================================
SIPAS HTTP SCHEMAS — PKKPR Pydantic DTOs [pkkpr_schemas.py]
============================================================================
Peran: Mendefinisikan kontrak data request & response HTTP ter-validasi
       untuk modul PKKPR, sinkron 1:1 dengan antarmuka frontend TypeScript.
============================================================================
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import date, datetime


class GeoJSONPolygonGeometry(BaseModel):
    """Skema geometri GeoJSON Polygon atau MultiPolygon."""
    type: str = Field(..., examples=["Polygon", "MultiPolygon"])
    coordinates: List[Any]


# ─── REQUEST SCHEMAS ──────────────────────────────────────────────────────────

class PKKPRFileItemRequest(BaseModel):
    """Skema metadata berkas lampiran yang diunggah."""
    file_type: str = Field(..., description="KTP, NIB_AKTA, BUKTI_HAK_TANAH, PROPOSAL_TEKNIS, dll.")
    file_name: str
    file_path: str
    file_size: int
    mime_type: str


class SubmitPKKPRRequest(BaseModel):
    """Payload pengajuan permohonan PKKPR baru oleh pemohon."""
    applicant_type: str = Field(default="BADAN_USAHA", examples=["BADAN_USAHA", "PERORANGAN"])
    applicant_name: str = Field(..., min_length=2, max_length=255)
    applicant_nik: Optional[str] = Field(default=None, max_length=16)
    applicant_nib: Optional[str] = Field(default=None, max_length=50)
    applicant_npwp: Optional[str] = Field(default=None, max_length=50)
    applicant_phone: Optional[str] = Field(default=None, max_length=50)
    applicant_email: Optional[str] = Field(default=None, max_length=255)

    category: str = Field(default="BERUSAHA_PENILAIAN", examples=["BERUSAHA_PENILAIAN", "NON_BERUSAHA"])
    activity_description: str = Field(..., min_length=5)
    kbli_code: Optional[str] = Field(default=None, max_length=10)

    location_address: str = Field(..., min_length=5)
    location_village: str = Field(..., min_length=2, max_length=100)
    location_district: str = Field(..., min_length=2, max_length=100)
    location_city: str = Field(default="Kabupaten Bogor", max_length=100)

    land_ownership_status: Optional[str] = Field(default="SHM", max_length=50)
    certificate_number: Optional[str] = Field(default=None, max_length=100)
    certificate_owner: Optional[str] = Field(default=None, max_length=255)

    proposed_land_area_m2: float = Field(..., gt=0, description="Luas bidang tanah dalam m²")
    geometry: GeoJSONPolygonGeometry
    files: Optional[List[PKKPRFileItemRequest]] = Field(default_factory=list)



class VerifyPKKPRAdminRequest(BaseModel):
    """Payload verifikasi kelengkapan formal oleh admin."""
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    notes: Optional[str] = None


class EvaluatePKKPRSpatialRequest(BaseModel):
    """Payload hasil kajian analisis spasial dinas oleh Tim Teknis."""
    approved_land_area_m2: float = Field(..., gt=0)
    approved_kdb_max: float = Field(..., ge=0, le=100, description="KDB Maksimal (%)")
    approved_klb_max: float = Field(..., ge=0, description="KLB Maksimal")
    approved_kdh_min: float = Field(..., ge=0, le=100, description="KDH Minimal (%)")
    approved_gsb_min: float = Field(..., ge=0, description="GSB Minimal (meter)")
    approved_max_floors: Optional[int] = Field(default=None, ge=1)
    spatial_zone_code: str = Field(..., examples=["R-2", "K-1"])
    spatial_zone_name: str = Field(..., examples=["Zona Perumahan Kepadatan Sedang"])
    technical_notes: Optional[str] = None


class RecordFPRReviewRequest(BaseModel):
    """Payload notula dan rekomendasi sidang komite Forum Penataan Ruang."""
    meeting_date: date
    official_report_no: str = Field(..., min_length=3, max_length=100)
    recommendation: str = Field(..., pattern="^(DISETUJUI_SELURUHNYA|DISETUJUI_SEBAGIAN|DITOLAK)$")
    
    ptp_bpn_number: Optional[str] = None
    ptp_bpn_date: Optional[date] = None
    ptp_notes: Optional[str] = None

    zoning_compliance_notes: str = Field(..., min_length=5)
    infrastructure_notes: Optional[str] = None
    environmental_notes: Optional[str] = None
    minutes_pdf_url: Optional[str] = None


class DraftPKKPRSKRequest(BaseModel):
    """Payload perumusan draf naskah SK penetapan oleh Kabid."""
    draft_sk_number: str = Field(..., min_length=3, max_length=100)
    considerations: Optional[List[str]] = Field(default_factory=list)
    legal_bases: Optional[List[str]] = Field(default_factory=list)
    dictum_clauses: Optional[Dict[str, Any]] = Field(default_factory=dict)
    obligations: Optional[List[str]] = Field(default_factory=list)
    kabid_notes: Optional[str] = None
    kabid_paraf_hash: Optional[str] = None


class SignPKKPRKadisRequest(BaseModel):
    """Payload otorisasi dan penerbitan TTE resmi oleh Kepala Dinas."""
    final_sk_number: str = Field(..., min_length=3, max_length=100)
    passphrase_pin: str = Field(..., min_length=4, max_length=50)


# ─── RESPONSE SCHEMAS ─────────────────────────────────────────────────────────

class PKKPRFileResponse(BaseModel):
    id: int
    file_type: str
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    uploaded_at: datetime


class PKKPRUploadFileResponse(BaseModel):
    file_name: str
    file_path: str
    file_url: str
    file_size: int
    mime_type: str
    file_type: str


class FPRReviewResponse(BaseModel):
    id: int
    meeting_date: date
    official_report_no: str
    recommendation: str
    ptp_bpn_number: Optional[str] = None
    ptp_bpn_date: Optional[date] = None
    ptp_notes: Optional[str] = None
    zoning_compliance_notes: str
    infrastructure_notes: Optional[str] = None
    environmental_notes: Optional[str] = None
    minutes_pdf_url: Optional[str] = None
    created_at: datetime


class PKKPRDraftSKResponse(BaseModel):
    id: int
    draft_sk_number: str
    considerations: Optional[List[str]] = None
    legal_bases: Optional[List[str]] = None
    dictum_clauses: Optional[Dict[str, Any]] = None
    obligations: Optional[List[str]] = None
    kabid_notes: Optional[str] = None
    kabid_paraf_hash: Optional[str] = None
    created_at: datetime


class PKKPRListItemResponse(BaseModel):
    """Ringkasan entitas PKKPR untuk tampilan tabel antrean."""
    id: str
    submission_no: str
    applicant_name: str
    category: str
    status: str
    proposed_land_area_m2: float
    location_village: str
    location_district: str
    created_at: datetime
    elapsed_days: int
    sla_start_date: Optional[date] = None
    sk_number: Optional[str] = None
    admin_lock_name: Optional[str] = None
    technical_lock_name: Optional[str] = None


class PKKPRDetailResponse(BaseModel):
    """Detail lengkap permohonan PKKPR termasuk relasi berkas, FPR, dan geometri."""
    id: str
    submission_no: str
    user_id: int
    applicant_type: str
    applicant_name: str
    applicant_nik: Optional[str] = None
    applicant_nib: Optional[str] = None
    applicant_npwp: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_email: Optional[str] = None

    category: str
    status: str
    activity_description: str
    kbli_code: Optional[str] = None

    location_address: str
    location_village: str
    location_district: str
    location_city: str

    land_ownership_status: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_owner: Optional[str] = None

    proposed_land_area_m2: float
    approved_land_area_m2: Optional[float] = None

    # Parameter Ruang
    approved_kdb_max: Optional[float] = None
    approved_klb_max: Optional[float] = None
    approved_kdh_min: Optional[float] = None
    approved_gsb_min: Optional[float] = None
    approved_max_floors: Optional[int] = None
    spatial_zone_code: Optional[str] = None
    spatial_zone_name: Optional[str] = None

    # Geometri GeoJSON
    geometry: Optional[Dict[str, Any]] = None

    # Status Kunci Petugas
    admin_lock_id: Optional[int] = None
    admin_lock_name: Optional[str] = None
    technical_lock_id: Optional[int] = None
    technical_lock_name: Optional[str] = None

    # Dokumen Akhir
    sk_number: Optional[str] = None
    sk_issued_date: Optional[date] = None
    signed_pdf_url: Optional[str] = None
    qr_code_hash: Optional[str] = None

    files: List[PKKPRFileResponse] = []
    fpr_reviews: List[FPRReviewResponse] = []
    sk_draft: Optional[PKKPRDraftSKResponse] = None

    created_at: datetime
    updated_at: datetime


# ─── SCHEMAS FOR PHASED SITE PLAN QUOTA TRACKING (Perbup Bogor No. 4/2025) ────

class PKKPRSitePlanItemResponse(BaseModel):
    id_permohonan: str
    submission_no: str
    housing_name: Optional[str] = None
    developer_name: Optional[str] = None
    land_area: float
    status: str
    submission_date: Optional[str] = None
    sk_number: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None


class PKKPREnvelopeResponse(BaseModel):
    approved_kdb_max: Optional[float] = None
    approved_klb_max: Optional[float] = None
    approved_kdh_min: Optional[float] = None
    approved_gsb_min: Optional[float] = None
    approved_max_floors: Optional[int] = None
    spatial_zone_code: Optional[str] = None
    spatial_zone_name: Optional[str] = None


class PKKPRQuotaSummaryResponse(BaseModel):
    pkkpr_id: str
    submission_no: str
    applicant_name: str
    status: str
    sk_number: Optional[str] = None
    sk_issued_date: Optional[str] = None
    total_approved_area_m2: float
    used_area_m2: float
    remaining_area_m2: float
    utilization_percent: float
    siteplans_count: int
    siteplans: List[PKKPRSitePlanItemResponse] = []
    pkkpr_geometry: Optional[Dict[str, Any]] = None
    envelope: Optional[PKKPREnvelopeResponse] = None


class ValidatePhasedSitePlanRequest(BaseModel):
    pkkpr_id: str
    new_area_m2: float
    siteplan_geometry: Optional[Dict[str, Any]] = None
    exclude_permohonan_id: Optional[str] = None


class ValidatePhasedSitePlanResponse(BaseModel):
    is_valid: bool
    error: Optional[str] = None
    details: Dict[str, Any] = {}


# ─── SCHEMAS FOR PUBLIC VERIFICATION & TRACKING (QR SCANNER PORTAL) ──────────

class PKKPRPublicVerificationResponse(BaseModel):
    is_valid: bool
    status: str
    id: str
    submission_no: str
    sk_number: Optional[str] = None
    sk_issued_date: Optional[str] = None
    applicant_name: str
    applicant_type: str
    applicant_nib: Optional[str] = None
    activity_description: str
    kbli_code: Optional[str] = None
    location_address: Optional[str] = None
    location_village: Optional[str] = None
    location_district: Optional[str] = None
    location_city: str = "Kabupaten Bogor"
    land_ownership_status: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_owner: Optional[str] = None
    proposed_land_area_m2: float
    approved_land_area_m2: Optional[float] = None
    spatial_zone_code: Optional[str] = None
    spatial_zone_name: Optional[str] = None
    approved_kdb_max: Optional[float] = None
    approved_klb_max: Optional[float] = None
    approved_kdh_min: Optional[float] = None
    approved_gsb_min: Optional[float] = None
    approved_max_floors: Optional[int] = None
    qr_code_hash: Optional[str] = None
    hash_matched: bool = True
    signer_name: str = "IR. H. KEPALA DINAS, M.Si."
    signer_nip: str = "19740512 199803 1 002"
    signer_title: str = "Kepala Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu Kabupaten Bogor"
    certification_authority: str = "Balai Sertifikasi Elektronik (BSrE) - BSSN"
    verified_at: str
    pdf_download_url: str


class PKKPRPublicTrackingStep(BaseModel):
    step_number: int
    name: str
    actor: str
    status: str  # "COMPLETED", "IN_PROGRESS", "PENDING"
    timestamp: Optional[str] = None
    note: Optional[str] = None


class PKKPRPublicTrackingResponse(BaseModel):
    id: str
    submission_no: str
    status: str
    applicant_name: str
    activity_description: str
    location: str
    submitted_at: str
    estimated_completion_days: int = 12
    receipt_pdf_url: str
    steps: List[PKKPRPublicTrackingStep] = []

