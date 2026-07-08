"""
============================================================================
SIPAS USE CASE — Server-Side Spatial Audit [audit_spatial.py]
============================================================================
Peran: Mengorkestrasikan analisis tumpang-tindih (overlay) spasial antara 
       poligon batas permohonan dengan rona lingkungan Kabupaten Bogor 
       menggunakan PostGIS secara aman dan asinkron di backend.
============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import logging

from src.domain.entities.permohonan import Permohonan, SubmissionStatus
from src.domain.exceptions import SpatialValidationError
from src.use_cases.submit_permohonan import PermohonanRepositoryPort, AuditTrailRepositoryPort

logger = logging.getLogger("sipas-be")

# ─── SECTION 1: PORTS (DEPENDENCY INVERSION BOUNDARIES) ───────────────────

class SpatialAuditPort(ABC):
    """
    Port Abstraksi untuk melakukan komputasi spasial relasional tingkat rendah di database.
    Melindungi Use Case dari detail implementasi SQL/PostGIS (Protected Variations).
    """
    @abstractmethod
    def audit_geometry_against_layers(
        self, 
        id_permohonan: str, 
        category: str
    ) -> List[Dict[str, Any]]:
        """
        Melakukan kueri spasial irisan (intersection) poligon permohonan dengan 
        layer sungai, sawah, SUTET, rel kereta, danau, dan peta lereng Bappeda.
        Returns:
            List dictionary berisi detail clash spasial per layer rona tanah.
        """
        pass


class ExtendedAuditTrailRepositoryPort(AuditTrailRepositoryPort):
    """
    Ekstensi Port Audit Trail jika membutuhkan log khusus hasil komputasi spasial.
    """
    pass


# ─── SECTION 2: INPUT & OUTPUT DATA TRANSFER OBJECTS (DTOs) ──────────────

@dataclass(frozen=True)
class SpatialClashDetailDto:
    layer_id: str
    layer_name: str
    clash_area_sqm: float
    description: str
    severity: str  # 'danger' | 'warning' | 'info'
    zoning_note: Optional[str] = None


@dataclass(frozen=True)
class SpatialAuditResultDto:
    is_clashing: bool
    clash_area_sqm: float
    zoning_score: int
    verdict: str  # 'LAYAK' | 'PERLU_REVISI' | 'TIDAK_LAYAK'
    details: List[SpatialClashDetailDto]


# ─── SECTION 3: USE CASE INTERACTOR IMPLEMENTATION ────────────────────────

class AuditSpatialUseCase:
    def __init__(
        self,
        permohonan_repo: PermohonanRepositoryPort,
        spatial_audit_port: SpatialAuditPort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        """Suntikkan dependensi eksternal melalui port (Dependency Injection)."""
        self.permohonan_repo = permohonan_repo
        self.spatial_audit_port = spatial_audit_port
        self.audit_trail_repo = audit_trail_repo

    def execute(self, id_permohonan: str) -> SpatialAuditResultDto:
        """
        Eksekusi algoritma pemrosesan spasial dan kalkulasi kelaikan tata ruang.
        """
        logger.info(f"[USE_CASE] Memulai audit spasial server-side untuk ID: {id_permohonan}")

        # 1. Ambil entitas permohonan dari database
        permohonan = self.permohonan_repo.find_by_id(id_permohonan)
        if not permohonan:
            raise ValueError(f"Ilegal: Permohonan ID '{id_permohonan}' tidak ditemukan.")

        # 2. Guard: Pastikan permohonan telah memiliki geometri terkalibrasi [Jakarta 5]
        # (geom tidak boleh kosong atau koordinat poligon minimal harus 3 titik)
        if not permohonan.polygon or len(permohonan.polygon) < 3:
            logger.error(f"[SPATIAL_AUDIT_ERROR] Permohonan {id_permohonan} belum memiliki geometri spasial.")
            raise SpatialValidationError(
                message="Gagal melakukan audit spasial.",
                detail="Geometri batas luar lahan (polygon) kosong atau tidak valid. Harap jalankan kalibrasi CAD terlebih dahulu."
            )

        # 3. Ambil kategori permohonan (Default: PERUMAHAN)
        category = permohonan.submission_category if permohonan.submission_category else "PERUMAHAN"

        try:
            # 4. Delegasikan komputasi spasial mentah ke database melalui port (Information Expert)
            raw_clash_results = self.spatial_audit_port.audit_geometry_against_layers(
                id_permohonan=id_permohonan,
                category=category
            )
            
            # 5. Olah hasil kueri spasial mentah menjadi struktur DTO yang aman
            clash_details: List[SpatialClashDetailDto] = []
            total_danger_warning_area = 0.0
            has_danger = False
            has_warning = False

            for res in raw_clash_results:
                severity = res.get("severity", "info")
                clash_area = float(res.get("clash_area_sqm", 0.0))

                if severity == "danger":
                    has_danger = True
                    total_danger_warning_area += clash_area
                elif severity == "warning":
                    has_warning = True
                    total_danger_warning_area += clash_area

                clash_details.append(
                    SpatialClashDetailDto(
                        layer_id=res["layer_id"],
                        layer_name=res["layer_name"],
                        clash_area_sqm=clash_area,
                        description=res["description"],
                        severity=severity,
                        zoning_note=res.get("zoning_note")
                    )
                )

            # 6. Hitung skor kepatuhan spasial (Zoning Score)
            zoning_score = self._calculate_compliance_score(clash_details, permohonan.land_area or 1.0)

            # 7. Tentukan kesimpulan akhir kelaikan (Verdict)
            if has_danger:
                verdict = "TIDAK_LAYAK"
            elif has_warning:
                verdict = "PERLU_REVISI"
            else:
                verdict = "LAYAK"

            # 8. Mutasikan status permohonan jika terdeteksi pelanggaran fatal otomatis
            if verdict == "TIDAK_LAYAK" and permohonan.status != SubmissionStatus.DITOLAK:
                permohonan.transition_status(SubmissionStatus.DITOLAK)
                self.permohonan_repo.save(permohonan, commit=True)
                
                # Catat penolakan otomatis ke log audit
                self.audit_trail_repo.log_action(
                    submission_id=permohonan.id_permohonan,
                    actor_name="System Spatial Engine",
                    role="System",
                    action="VERIFY_TECHNICAL_REJECTED",
                    status_before=SubmissionStatus.VERIFIKASI_TEKNIS.value,
                    status_after=SubmissionStatus.DITOLAK.value,
                    notes=f"[AUTO-REJECT] Berkas ditolak otomatis karena menabrak zona lindung mutlak seluas {total_danger_warning_area:.1f} m²."
                )

            logger.info(f"[USE_CASE] Sukses memproses audit spasial. Skor: {zoning_score}/100 | Verdict: {verdict}")
            
            return SpatialAuditResultDto(
                is_clashing=(has_danger or has_warning),
                clash_area_sqm=round(total_danger_warning_area, 2),
                zoning_score=zoning_score,
                verdict=verdict,
                details=clash_details
            )

        except Exception as e:
            logger.error(f"[USE_CASE_CRASH] Kegagalan fatal saat menjalankan use case audit spasial: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses kalkulasi spasial di server: {str(e)}")

    def _calculate_compliance_score(self, details: List[SpatialClashDetailDto], total_area: float) -> int:
        """
        Rumus internal kalkulator penalti skor kepatuhan spasial (Information Expert).
        """
        if not details:
            return 100

        penalty = 0.0
        for detail in details:
            ratio = detail.clash_area_sqm / total_area if total_area > 0 else 0.0
            
            # Bobot pengurangan nilai berdasarkan tingkat keparahan benturan
            if detail.severity == "danger":
                penalty += (ratio * 60.0) + 20.0
            elif detail.severity == "warning":
                penalty += (ratio * 25.0) + 5.0

        # Batasi agar skor berada di rentang 0 - 100
        final_score = 100.0 - min(penalty, 100.0)
        return max(0, round(final_score))