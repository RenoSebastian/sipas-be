"""
============================================================================
SIPAS HTTP ROUTER — PKKPR Module [pkkpr.py]
============================================================================
Peran: Endpoint API RESTful untuk siklus hidup Persetujuan Kesesuaian Kegiatan
       Pemanfaatan Ruang (PKKPR) dan bridging validasi spasial ke Site Plan.
============================================================================
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import UserModel
from src.infrastructure.security.auth import get_current_user, requires_roles, UserRole
from src.use_cases.pkkpr.pkkpr_service import PKKPRService
from src.infrastructure.http.schemas.pkkpr_schemas import (
    SubmitPKKPRRequest,
    VerifyPKKPRAdminRequest,
    EvaluatePKKPRSpatialRequest,
    RecordFPRReviewRequest,
    DraftPKKPRSKRequest,
    SignPKKPRKadisRequest,
    PKKPRListItemResponse,
    PKKPRDetailResponse,
    PKKPRQuotaSummaryResponse,
    ValidatePhasedSitePlanRequest,
    ValidatePhasedSitePlanResponse
)

router = APIRouter(prefix="/api/pkkpr", tags=["PKKPR (Pemanfaatan Ruang)"])


class ValidateSitePlanContainmentRequest(BaseModel):
    pkkpr_id: str
    siteplan_geometry: Dict[str, Any]


class ValidateSitePlanContainmentResponse(BaseModel):
    is_covered: bool
    area_outside_m2: float
    message: str


# ─── 1. PENGAJUAN PERMOHONAN BARU (PEMOHON) ───────────────────────────────────

@router.post("/submit", response_model=PKKPRDetailResponse, status_code=status.HTTP_201_CREATED)
def submit_pkkpr(
    req: SubmitPKKPRRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.PEMOHON, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Pemohon mengajukan berkas permohonan PKKPR baru secara daring."""
    service = PKKPRService(db)
    try:
        return service.submit_new_pkkpr(user_id=current_user.id, req=req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 2. DAFTAR ANTREAN BERKAS ──────────────────────────────────────────────────

@router.get("/list", response_model=List[PKKPRListItemResponse])
def list_pkkpr(
    status_filter: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mengambil daftar antrean permohonan sesuai hak akses peran pengguna."""
    service = PKKPRService(db)
    return service.list_submissions(
        user_id=current_user.id,
        role=current_user.role,
        status=status_filter
    )


# ─── 3. DAFTAR SK PKKPR SAH MILIK PEMOHON (UNTUK MODUL SITE PLAN) ─────────────

@router.get("/my-approved-sk", response_model=List[PKKPRListItemResponse])
def list_my_approved_sk(
    current_user: UserModel = Depends(requires_roles([UserRole.PEMOHON, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Mengambil daftar SK PKKPR yang telah berstatus DISETUJUI milik pemohon aktif.
    Digunakan sebagai pilihan dropdown saat pemohon mengajukan pengesahan Site Plan.
    """
    service = PKKPRService(db)
    return service.list_submissions(
        user_id=current_user.id if current_user.role == "PEMOHON" else None,
        role="PEMOHON",
        status="DISETUJUI"
    )


# ─── 4. DETAIL LENGKAP PERMOHONAN ─────────────────────────────────────────────

@router.get("/{pkkpr_id}", response_model=PKKPRDetailResponse)
def get_pkkpr_detail(
    pkkpr_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mengambil rincian berkas permohonan PKKPR termasuk notula FPR dan geometri GeoJSON."""
    service = PKKPRService(db)
    try:
        return service.get_detail(pkkpr_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── 5. PENGUNCIAN & VERIFIKASI FORMAL (ADMIN) ─────────────────────────────────

@router.post("/{pkkpr_id}/claim-admin", response_model=PKKPRDetailResponse)
def claim_admin(
    pkkpr_id: str,
    current_user: UserModel = Depends(requires_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin mengunci berkas verifikasi administrasi agar tidak tumpang tindih."""
    service = PKKPRService(db)
    try:
        return service.claim_admin_lock(pkkpr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{pkkpr_id}/release-admin", response_model=PKKPRDetailResponse)
def release_admin(
    pkkpr_id: str,
    current_user: UserModel = Depends(requires_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin melepaskan kunci berkas administrasi."""
    service = PKKPRService(db)
    try:
        return service.release_admin_lock(pkkpr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{pkkpr_id}/verify-admin", response_model=PKKPRDetailResponse)
def verify_admin(
    pkkpr_id: str,
    req: VerifyPKKPRAdminRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Admin memverifikasi kelengkapan formal dokumen (Approve / Reject)."""
    service = PKKPRService(db)
    try:
        return service.verify_admin_document(pkkpr_id, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 6. KAJIAN SPASIAL (TIM TEKNIS PUPR) ──────────────────────────────────────

@router.post("/{pkkpr_id}/claim-technical", response_model=PKKPRDetailResponse)
def claim_technical(
    pkkpr_id: str,
    current_user: UserModel = Depends(requires_roles([UserRole.TIM_TEKNIS])),
    db: Session = Depends(get_db)
):
    """Tim Teknis mengunci berkas untuk analisis spasial GIS."""
    service = PKKPRService(db)
    try:
        return service.claim_technical_lock(pkkpr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{pkkpr_id}/release-technical", response_model=PKKPRDetailResponse)
def release_technical(
    pkkpr_id: str,
    current_user: UserModel = Depends(requires_roles([UserRole.TIM_TEKNIS])),
    db: Session = Depends(get_db)
):
    """Tim Teknis melepaskan kunci berkas spasial."""
    service = PKKPRService(db)
    try:
        return service.release_technical_lock(pkkpr_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{pkkpr_id}/evaluate-spatial", response_model=PKKPRDetailResponse)
def evaluate_spatial(
    pkkpr_id: str,
    req: EvaluatePKKPRSpatialRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.TIM_TEKNIS])),
    db: Session = Depends(get_db)
):
    """Tim Teknis memasukkan parameter hasil analisis spasial dinas."""
    service = PKKPRService(db)
    try:
        return service.evaluate_spatial(pkkpr_id, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 7. SIDANG FORUM PENATAAN RUANG (FPR) ─────────────────────────────────────

@router.post("/{pkkpr_id}/record-fpr", response_model=PKKPRDetailResponse)
def record_fpr(
    pkkpr_id: str,
    req: RecordFPRReviewRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.TIM_TEKNIS, UserRole.ADMIN, UserRole.KABID_PUPR])),
    db: Session = Depends(get_db)
):
    """Mencatat notula dan rekomendasi sidang komite Forum Penataan Ruang (FPR)."""
    service = PKKPRService(db)
    try:
        return service.record_fpr_review(pkkpr_id, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 8. PERUMUSAN DRAF SK (KABID PENATAAN RUANG) ──────────────────────────────

@router.post("/{pkkpr_id}/draft-sk", response_model=PKKPRDetailResponse)
def draft_sk(
    pkkpr_id: str,
    req: DraftPKKPRSKRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.KABID_PUPR])),
    db: Session = Depends(get_db)
):
    """Kabid memaraf draf naskah Surat Keputusan penetapan PKKPR."""
    service = PKKPRService(db)
    try:
        return service.draft_sk(pkkpr_id, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 9. OTORISASI & TTE (KEPALA DINAS DPMPTSP) ────────────────────────────────

@router.post("/{pkkpr_id}/sign-tte", response_model=PKKPRDetailResponse)
def sign_tte(
    pkkpr_id: str,
    req: SignPKKPRKadisRequest,
    current_user: UserModel = Depends(requires_roles([UserRole.KADIS])),
    db: Session = Depends(get_db)
):
    """Kepala Dinas menerbitkan dan menandatangani SK resmi dengan TTE BSrE."""
    service = PKKPRService(db)
    try:
        return service.sign_kadis_tte(pkkpr_id, current_user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── 10. SPATIAL CONTAINMENT CHECKER (BRIDGE TO SITE PLAN) ─────────────────────

@router.post("/validate-siteplan-containment", response_model=ValidateSitePlanContainmentResponse)
def validate_containment(
    req: ValidateSitePlanContainmentRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memvalidasi apakah denah poligon Site Plan berada 100% di dalam batas izin SK PKKPR.
    Digunakan oleh wizard pengajuan Site Plan saat memeriksa gambar CAD hasil georeferensi.
    """
    service = PKKPRService(db)
    is_covered, outside_area = service.repo.validate_siteplan_inside_pkkpr(
        req.pkkpr_id,
        req.siteplan_geometry
    )
    if is_covered:
        message = "Validasi spasial sukses: Seluruh denah Site Plan berada di dalam batas izin SK PKKPR."
    else:
        message = f"Peringatan Spasial: Denah Site Plan melanggar batas izin seluas {outside_area:.2f} m²."

    return ValidateSitePlanContainmentResponse(
        is_covered=is_covered,
        area_outside_m2=outside_area,
        message=message
    )


# ─── 11. KUOTA SITE PLAN BERTAHAP (Perbup Bogor No. 4/2025 Pasal 3) ───────────

@router.get("/{pkkpr_id}/quota-summary", response_model=PKKPRQuotaSummaryResponse)
def get_pkkpr_quota_summary(
    pkkpr_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mengambil data pemanfaatan kuota lahan permohonan Site Plan bertahap
    berdasarkan SK PKKPR yang telah terbit.
    """
    service = PKKPRService(db)
    summary = service.repo.get_quota_summary(pkkpr_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Permohonan PKKPR dengan ID '{pkkpr_id}' tidak ditemukan."
        )
    return summary


@router.post("/{pkkpr_id}/validate-phased-siteplan", response_model=ValidatePhasedSitePlanResponse)
def validate_phased_siteplan(
    pkkpr_id: str,
    req: ValidatePhasedSitePlanRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validasi pre-flight pengajuan Site Plan bertahap:
    - Memeriksa kuota luas kumulatif terhadap SK PKKPR.
    - Memeriksa batas spasial berada di dalam PKKPR (toleransi buffer 10 cm).
    - Memeriksa agar tidak tumpang tindih dengan Site Plan tahap sebelumnya.
    """
    service = PKKPRService(db)
    result = service.repo.validate_phased_siteplan(
        pkkpr_id=pkkpr_id,
        new_siteplan_geom=req.siteplan_geometry,
        new_area_m2=req.new_area_m2,
        exclude_permohonan_id=req.exclude_permohonan_id
    )
    return ValidatePhasedSitePlanResponse(
        is_valid=result["is_valid"],
        error=result.get("error"),
        details=result.get("details", {})
    )

