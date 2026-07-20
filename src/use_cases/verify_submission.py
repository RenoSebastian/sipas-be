"""
============================================================================
SIPAS USE CASE — Verify & Approve Submission [verify_submission.py] (REVISED v10.3)
============================================================================
Peran: Mengorkestrasikan ulasan penilaian berjenjang (Admin -> Tim Teknis ->
       Kabid -> Kadis) sesuai dengan matriks status birokrasi baru.
       Menerima input dimensi fisik absolut (m²) terverifikasi untuk memicu 
       proses perhitungan rasio dan galat spasial otomatis oleh objek Domain.
       Mendukung penguncian draf keputusan SK (SkDraft) saat disetujui Kabid,
       penandatanganan visual TTE Coret Kepala Dinas pada draf keputusan,
       serta perlindungan atomisitas transaksi basis data.

Pembaruan v10.3: Penyesuaian logika validasi pra-syarat verifikasi teknis
                terhadap Ground Inspection (multi-photo) dan Aerial Inspection
                (single drone video) secara terpisah di tingkat Use Case.
============================================================================
"""

import logging
import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Any, cast
from dataclasses import dataclass
from datetime import date, datetime 
from pydantic import SecretStr 

# Impor Entitas Domain sebagai Single Source of Truth
from src.domain.entities.permohonan import Permohonan, SubmissionStatus, KKPRVerdict
from src.domain.entities.telaah_staf import TelaahStaf, TelaahStafVerdict, VerifierInfo, AdminChecklistItem, TechnicalMatrixItem

# Impor Entitas Baru Draf SK & Value Objects Pendukung
from src.domain.entities.sk_draft import (
    SkDraft,
    SkVerdict,
    SkSignerInfo,
    SkDiktumHunian,
    SkDiktumPsu,
    SkDiktumIntensity,
    SkConsiderations
)

# Impor Abstraksi Repositori & Log Audit
from src.use_cases.submit_permohonan import PermohonanRepositoryPort, AuditTrailRepositoryPort
from src.use_cases.ports.document_generator_port import DocumentGeneratorPort
from src.infrastructure.database.repositories.telaah_staf_repository import TelaahStafRepositoryPort

logger = logging.getLogger("sipas-be")


def normalize_kkpr_verdict_string(val: str) -> str:
    """Normalisasi string keputusan KKPR dari frontend ke format uppercase Enum database."""
    val_clean = val.strip().upper()
    if "REVISI" in val_clean or "PERBAIKAN" in val_clean:
        return "PERLU_PERBAIKAN"
    if "DITOLAK" in val_clean or "TIDAK_SESUAI" in val_clean:
        return "TIDAK_SESUAI"
    return val_clean.replace(" ", "_")

# ─── SECTION 1: PORT ABSTRAKSI LAYANAN LUAR (PORTS) ─────────────────────────

class DigitalSignaturePort(ABC):
    @abstractmethod
    async def sign_pdf_document(self, pdf_path: str, certificate_owner_nip: str, passphrase: str) -> str:
        """Menghubungkan ke API BSrE untuk menandatangani dokumen secara digital."""
        pass


class SkDraftRepositoryPort(ABC):
    """Abstraksi Kontrak Repositori untuk Entitas Domain SkDraft."""
    @abstractmethod
    def find_by_id(self, id_sk: str) -> Optional[SkDraft]:
        pass

    @abstractmethod
    def find_by_permohonan_id(self, id_permohonan: str) -> Optional[SkDraft]:
        pass

    @abstractmethod
    def save(self, entity: SkDraft, commit: bool = True) -> SkDraft:
        pass

    @abstractmethod
    def get_next_sequence_no(self) -> int:
        """Mendapatkan nomor antrean / sekuensial SK dinas berikutnya."""
        pass


class ExtendedPermohonanRepositoryPort(PermohonanRepositoryPort):
    @abstractmethod
    def save_evaluasi_items(self, id_permohonan: str, items: List[Any]) -> None:
        """Penyimpanan detail checklist evaluasi administrasi/teknis (idempotent)."""
        pass

    @abstractmethod
    def get_evaluasi_items(self, id_permohonan: str) -> List[Any]:
        """Mendapatkan seluruh detail checklist evaluasi (administrasi & teknis)."""
        pass

    @abstractmethod
    def find_user_by_id(self, user_id: int) -> Optional[Any]:
        """Mencari data pengguna secara decoupling tanpa membocorkan session database."""
        pass

    @abstractmethod
    def find_spatial_overlaps(self, id_permohonan: str) -> List[Any]:
        """Menemukan data permohonan lain yang tumpang tindih secara geografis."""
        pass

    @abstractmethod
    def expire_all(self) -> None:
        pass

    @abstractmethod
    def check_ancestry_loop(self, child_id: str, target_parent_id: str) -> bool:
        """Memeriksa silsilah melingkar (circular ancestry dependency)."""
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass


# ─── SECTION 2: DATA TRANSFER OBJECTS (DTOs) ─────────────────────────────

@dataclass(frozen=True)
class EvaluasiChecklistItemDto:
    aspek_code: str
    aspek_label: str
    status_kelayakan: str          # "Sesuai" | "Sesuai Bersyarat" | "Tidak Sesuai"
    catatan_verifikator: Optional[str] = None
    attachment_url: Optional[str] = None
    verified_by_id: Optional[int] = None  # Penjejak ID pembuat evaluasi
    verified_at: Optional[datetime] = None


@dataclass(frozen=True)
class VerifySubmissionInputDto:
    id_permohonan: str
    actor_name: str
    role: str
    nip: Optional[str]              # Wajib dilampirkan jika aktor memproses TTE Kadis
    passphrase: Optional[str]       # Wajib dilampirkan untuk TTE BSrE Kadis
    action_type: str                # 'APPROVE' | 'REJECT' | 'REVERT_TO_TECHNICAL' | 'REVERT_TO_ADMINISTRATIVE' | 'OVERRIDE_VERDICT' | 'SAVE_TECHNICAL_MATRIX'
    notes: str                      # Catatan justifikasi
    is_spatially_compliant: bool = True
    signature_base64: Optional[str] = None

    # Parameter Komparasi Teknis Tambahan (Diinput oleh Tim Teknis / Kabid)
    kkpr_verdict: Optional[str] = None  # "Sesuai", "Sesuai Bersyarat", "Perlu Perbaikan / Revisi", "Tidak Sesuai / Ditolak"
    
    # REVISED v10.2: INPUT DIMENSI FISIK ABSOLUT (m²)
    verified_land_area: Optional[float] = None
    verified_building_area: Optional[float] = None
    verified_total_floor_area: Optional[float] = None
    verified_rth_area: Optional[float] = None
    verified_gsb: Optional[float] = None
    
    checklist_items: Optional[List[EvaluasiChecklistItemDto]] = None


# ─── PURE FABRICATION: DATA TRANSFER OBJECT UNTUK SILISILAH ──
@dataclass(frozen=True)
class LinkParentSubmissionInputDto:
    id_permohonan: str
    actor_name: str
    role: str
    baseline_source: str            # "DIGITAL" | "LEGACY"
    parent_id_permohonan: Optional[str] = None
    replaced_sk_number: Optional[str] = None
    replaced_sk_date: Optional[date] = None
    replaced_sk_doc_url: Optional[str] = None
    notes: str = ""


# ─── SECTION 3: USE CASE INTERACTOR CLASSES ────────────────────────────────

class VerifySubmissionUseCase:
    def __init__(
        self,
        permohonan_repo: ExtendedPermohonanRepositoryPort,
        telaah_staf_repo: TelaahStafRepositoryPort,
        sk_draft_repo: SkDraftRepositoryPort,
        document_generator: DocumentGeneratorPort,
        digital_signature_client: DigitalSignaturePort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        self.permohonan_repo = permohonan_repo
        self.telaah_staf_repo = telaah_staf_repo
        self.sk_draft_repo = sk_draft_repo
        self.document_generator = document_generator
        self.digital_signature_client = digital_signature_client
        self.audit_trail_repo = audit_trail_repo

    def _build_fallback_telaah_staf(
        self,
        permohonan: Permohonan,
        actor_name: str,
        actor_nip: Optional[str],
        signature_base64: Optional[str]
    ) -> TelaahStaf:
        """Membuat draf Telaah Staf minimal saat dokumen review belum ada."""
        eval_items = self.permohonan_repo.get_evaluasi_items(permohonan.id_permohonan)

        admin_items: List[AdminChecklistItem] = []
        tech_items: List[TechnicalMatrixItem] = []

        for item in eval_items:
            status_val = getattr(item, "status_kelayakan", None)
            if status_val is not None and hasattr(status_val, "value"):
                status_val = status_val.value
            raw_status = (status_val or "Pending").upper().replace(" ", "_")

            if getattr(item, "aspek_code", "").startswith(("REQ_", "M")):
                tech_status = raw_status if raw_status in ["SESUAI", "SESUAI_BERSYARAT", "TIDAK_SESUAI"] else "TIDAK_SESUAI"
                tech_items.append(
                    TechnicalMatrixItem(
                        code=getattr(item, "aspek_code", "M3_KDB"),
                        label=getattr(item, "aspek_label", "Parameter Teknis"),
                        unit="",
                        proposed_val="-",
                        bylaw_val="-",
                        verified_val="-",
                        status=tech_status,
                        notes=getattr(item, "catatan_verifikator", None)
                    )
                )
            else:
                admin_status = "SESUAI" if raw_status == "SESUAI" else "TIDAK_SESUAI"
                admin_items.append(
                    AdminChecklistItem(
                        doc_key=getattr(item, "aspek_code", "legalDoc"),
                        doc_label=getattr(item, "aspek_label", "Dokumen Formal"),
                        file_name="Lampiran Dokumen",
                        status=admin_status,
                        notes=getattr(item, "catatan_verifikator", None)
                    )
                )

        if not admin_items:
            admin_items.append(
                AdminChecklistItem(
                    doc_key="legalDoc",
                    doc_label="Sertifikat Tanah BPN",
                    file_name="Sertifikat",
                    status="SESUAI"
                )
            )

        if not tech_items:
            tech_items.append(
                TechnicalMatrixItem(
                    code="M3_KDB",
                    label="Koefisien Dasar Bangunan (KDB)",
                    unit="%",
                    proposed_val=str(permohonan.tech_kdb or 55.0),
                    bylaw_val=str(permohonan.bylaw_max_kdb or 60.0),
                    verified_val=str(permohonan.verified_kdb_percentage or 55.0), # Menggunakan auto-calculated verified percentage
                    status="SESUAI"
                )
            )

        return TelaahStaf(
            id_telaah=f"tel-{uuid.uuid4().hex[:12]}",
            id_permohonan=permohonan.id_permohonan,
            verdict=TelaahStafVerdict.SESUAI,
            verifier=VerifierInfo(
                name=actor_name,
                nip=actor_nip or "19800523",
                timestamp=datetime.now(),
                signature_base64=signature_base64
            ),
            administrative_checklist=admin_items,
            technical_matrix=tech_items,
            admin_verifier_name=actor_name,
            admin_verifier_nip=actor_nip,
            admin_verified_at=datetime.now().strftime("%d-%m-%Y %H:%M")
        )

    async def execute(self, input_dto: VerifySubmissionInputDto) -> Permohonan:
        """Mengorkestrasikan penilaian berjenjang 5-peran secara transaksional."""

        # 1. Pengecekan Eksistensi Berkas Permohonan
        def get_current_permohonan() -> Permohonan:
            p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
            if not p:
                raise ValueError(f"Ilegal: Permohonan dengan ID '{input_dto.id_permohonan}' tidak ditemukan.")
            return p

        permohonan = await asyncio.to_thread(get_current_permohonan)
        status_awal = permohonan.status

        # ─── SECTION 4: MATRIKS OTORISASI PERAN — SoD ENFORCEMENT ──────────────────
        allowed_roles: dict[SubmissionStatus, list[str]] = {
            SubmissionStatus.MENUNGGU_VERIFIKASI:     ["ADMIN"],
            SubmissionStatus.VERIFIKASI_ADMINISTRASI: ["ADMIN"],
            SubmissionStatus.VERIFIKASI_TEKNIS:       ["TIM_TEKNIS"],
            SubmissionStatus.MENUNGGU_REKOMENDASI:    ["KABID_PUPR"],
            SubmissionStatus.MENUNGGU_PERSETUJUAN:    ["KADIS"],
            SubmissionStatus.PROSES_TTE:              ["KADIS"],
        }

        if status_awal in allowed_roles:
            if input_dto.role not in allowed_roles[status_awal]:
                logger.warning(
                    "[SECURITY_ALERT] Unauthorized role attempt. Actor: '%s' | Role: '%s' | Target Stage: '%s'",
                    input_dto.actor_name, input_dto.role, status_awal.value
                )
                raise PermissionError(
                    f"Akses Ditolak: Peran '{input_dto.role}' tidak memiliki otorisasi "
                    f"pada tahap verifikasi '{status_awal.value}'."
                )

        # ─── SECTION 5: PENANGANAN ALUR PROSES BERDASARKAN STATUS TERKINI ─────────

        # ======================================================================
        # TAHAP A: REVIEW OLEH ADMIN (MENUNGGU_VERIFIKASI / VERIFIKASI_ADMINISTRASI)
        # ======================================================================
        if status_awal in [SubmissionStatus.MENUNGGU_VERIFIKASI, SubmissionStatus.VERIFIKASI_ADMINISTRASI]:
            def execute_admin_review() -> Permohonan:
                if input_dto.action_type == "REJECT":
                    permohonan.transition_status(SubmissionStatus.DITOLAK)
                    self.permohonan_repo.save(permohonan)
                    
                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="VERIFY_ADMIN_REJECTED",
                        status_before=status_awal.value, status_after=SubmissionStatus.DITOLAK.value,
                        notes=f"Verifikasi Administrasi Gagal. Berkas dikembalikan ke pemohon: {input_dto.notes}"
                    )
                else:
                    permohonan.transition_status(SubmissionStatus.VERIFIKASI_TEKNIS)
                    self.permohonan_repo.save(permohonan, commit=False)
                    
                    if input_dto.checklist_items:
                        self.permohonan_repo.save_evaluasi_items(permohonan.id_permohonan, input_dto.checklist_items)
                        
                    self.permohonan_repo.commit()
                    
                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="VERIFY_ADMIN_APPROVED",
                        status_before=status_awal.value, status_after=SubmissionStatus.VERIFIKASI_TEKNIS.value,
                        notes="Verifikasi administrasi formal lengkap. Berkas diteruskan ke Tim Teknis."
                    )
                return permohonan

            return await asyncio.to_thread(execute_admin_review)

        # ======================================================================
        # TAHAP B: REVIEW OLEH TIM TEKNIS (VERIFIKASI_TEKNIS) -> GENERATE TELAAH
        # ======================================================================
        elif status_awal == SubmissionStatus.VERIFIKASI_TEKNIS:
            def execute_technical_review() -> Permohonan:
                # Skenario R1: Pengembalian ke Administrasi oleh Tim Teknis
                if input_dto.action_type == "REVERT_TO_ADMINISTRATIVE":
                    permohonan.transition_status(SubmissionStatus.VERIFIKASI_ADMINISTRASI)
                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()
                    
                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="REVERT_TECHNICAL_TO_ADMINISTRATIVE",
                        status_before=status_awal.value, status_after=SubmissionStatus.VERIFIKASI_ADMINISTRASI.value,
                        notes=f"Berkas dikembalikan ke Verifikasi Administrasi oleh Tim Teknis. Catatan: {input_dto.notes}"
                    )
                    return permohonan

                # Skenario 1: Tim Teknis menyimpan draf penilaian matriks spasial & cetak PDF
                if input_dto.action_type == "SAVE_TECHNICAL_MATRIX" or not input_dto.signature_base64:
                    # REVISED v10.2: Menyimpan data fisik mentah terverifikasi ke model Permohonan
                    if input_dto.verified_land_area is not None: 
                        permohonan.verified_land_area = input_dto.verified_land_area
                    if input_dto.verified_building_area is not None: 
                        permohonan.verified_building_area = input_dto.verified_building_area
                    if input_dto.verified_total_floor_area is not None: 
                        permohonan.verified_total_floor_area = input_dto.verified_total_floor_area
                    if input_dto.verified_rth_area is not None: 
                        permohonan.verified_rth_area = input_dto.verified_rth_area
                    if input_dto.verified_gsb is not None: 
                        permohonan.verified_gsb = input_dto.verified_gsb

                    # Penyelarasan rasio fallback ke kolom historis demi backward-compatibility
                    permohonan.verified_kdb = permohonan.verified_kdb_percentage
                    permohonan.verified_klb = permohonan.verified_klb_ratio
                    permohonan.verified_kdh = permohonan.verified_kdh_percentage

                    if input_dto.kkpr_verdict:
                        normalized_verdict = normalize_kkpr_verdict_string(input_dto.kkpr_verdict)
                        permohonan.kkpr_verdict = KKPRVerdict(normalized_verdict)
                    
                    if not permohonan.kkpr_verdict:
                        raise ValueError("Gagal: Rekomendasi KKPR Verdict teknis wajib ditentukan oleh Tim Teknis.")

                    permohonan.kkpr_verified_at = datetime.now()
                    permohonan.kkpr_verifier_name = input_dto.actor_name

                    # 2. Persist detail checklist evaluasi manual teknis
                    if input_dto.checklist_items:
                        self.permohonan_repo.save_evaluasi_items(permohonan.id_permohonan, input_dto.checklist_items)
                        # Sync TPU verification status and compensations based on checklist items
                        if permohonan.tpu_detail:
                            for item in input_dto.checklist_items:
                                if item.aspek_code in ["tech_cemetery", "tpu_cemetery", "tech_cemetery_area"]:
                                    status_val = item.status_kelayakan
                                    raw_status = "APPROVED" if status_val in ["Sesuai", "SESUAI"] else ("REJECTED" if status_val in ["Tidak Sesuai", "TIDAK_SESUAI"] else "PENDING")
                                    permohonan.tpu_detail.status_verifikasi = raw_status
                                    permohonan.tpu_detail.catatan_verifikasi = item.catatan_verifikator
                                    permohonan.tpu_detail.diverifikasi_oleh = input_dto.actor_name
                                    permohonan.tpu_detail.diverifikasi_pada = datetime.now()
                        
                        db_compensations = self.permohonan_repo.find_kompensasi_by_permohonan_id(permohonan.id_permohonan)
                        if db_compensations:
                            for item in input_dto.checklist_items:
                                if item.aspek_code.startswith("comp-") or item.aspek_code.startswith("comp_"):
                                    from src.domain.entities.kompensasi import FulfillmentStatus
                                    for comp in db_compensations:
                                        if comp.id_kompensasi == item.aspek_code or item.aspek_code.endswith(comp.id_kompensasi):
                                            status_val = item.status_kelayakan
                                            raw_status = FulfillmentStatus.TERPENUHI if status_val in ["Sesuai", "SESUAI"] else FulfillmentStatus.BELUM_TERPENUHI
                                            comp.status_pemenuhan = raw_status
                                            self.permohonan_repo.save_kompensasi(comp)

                    # 3. Kunci Snapshot Penilaian ke Entitas Domain murni 'TelaahStaf'
                    admin_items: List[AdminChecklistItem] = []
                    tech_items: List[TechnicalMatrixItem] = []

                    # Ambil semua data evaluasi checklist dari database
                    all_eval_items = self.permohonan_repo.get_evaluasi_items(permohonan.id_permohonan)
                    
                    # Gabungkan dengan input_dto.checklist_items yang baru dikirim
                    eval_map = {item.aspek_code: item for item in all_eval_items}
                    if input_dto.checklist_items:
                        for item in input_dto.checklist_items:
                            eval_map[item.aspek_code] = item

                    # Cari verifikator administrasi (Admin) yang bertugas
                    admin_verifier_name = "Rian Hidayat"
                    admin_verifier_nip = "199208152018032001"
                    admin_verified_at_str = "-"
                    
                    for item in all_eval_items:
                        is_technical = item.aspek_code.startswith("REQ_") or item.aspek_code.startswith("M")
                        if not is_technical and item.verified_by_id:
                            admin_user = self.permohonan_repo.find_user_by_id(item.verified_by_id)
                            if admin_user:
                                admin_verifier_name = getattr(admin_user, "full_name", admin_verifier_name)
                                admin_verifier_nip = getattr(admin_user, "nip", admin_verifier_nip)
                            if item.verified_at:
                                admin_verified_at_str = item.verified_at.strftime("%d-%m-%Y %H:%M")
                            break

                    for code, item in eval_map.items():
                        status_val = getattr(item, "status_kelayakan", None)
                        if status_val is not None and hasattr(status_val, "value"):
                            status_val = status_val.value
                        raw_status = (status_val or "Pending").upper().replace(" ", "_")
                        is_technical = code.startswith("REQ_") or code.startswith("M")
                        
                        if not is_technical:  # Dokumen formal non-matriks
                            admin_status = "SESUAI" if raw_status == "SESUAI" else "TIDAK_SESUAI"
                            admin_items.append(
                                AdminChecklistItem(
                                    doc_key=code, 
                                    doc_label=getattr(item, "aspek_label", None) or getattr(item, "doc_label", "Dokumen"),
                                    file_name="Lampiran Dokumen", 
                                    status=admin_status,
                                    notes=getattr(item, "catatan_verifikator", None) or getattr(item, "notes", None)
                                )
                            )
                        else:  # Parameter matriks teknis spasial
                            tech_status = raw_status if raw_status in ["SESUAI", "SESUAI_BERSYARAT", "TIDAK_SESUAI"] else "TIDAK_SESUAI"
                            tech_items.append(
                                TechnicalMatrixItem(
                                    code=code, 
                                    label=getattr(item, "aspek_label", None) or getattr(item, "label", "Parameter"), 
                                    unit="",
                                    proposed_val="-", 
                                    bylaw_val="-", 
                                    verified_val="-",
                                    status=tech_status, 
                                    notes=getattr(item, "catatan_verifikator", None) or getattr(item, "notes", None)
                                )
                            )

                    if not admin_items:
                        admin_items.append(AdminChecklistItem(doc_key="legalDoc", doc_label="Sertifikat Tanah BPN", file_name="Sertifikat", status="SESUAI"))
                    if not tech_items:
                        tech_items.append(TechnicalMatrixItem(code="M3_KDB", label="Koefisien Dasar Bangunan (KDB)", unit="%", proposed_val="55.0", bylaw_val="60.0", verified_val=str(permohonan.verified_kdb_percentage or 55.0), status="SESUAI"))

                    verdict_map = {
                        KKPRVerdict.SESUAI: TelaahStafVerdict.SESUAI,
                        KKPRVerdict.SESUAI_BERSYARAT: TelaahStafVerdict.SESUAI_BERSYARAT,
                        KKPRVerdict.PERLU_PERBAIKAN: TelaahStafVerdict.PERLU_PERBAIKAN,
                        KKPRVerdict.TIDAK_SESUAI: TelaahStafVerdict.TIDAK_SESUAI
                    }

                    current_kkpr_verdict = permohonan.kkpr_verdict
                    if current_kkpr_verdict is None:
                        raise ValueError("Gagal: Rekomendasi KKPR Verdict teknis wajib ditentukan oleh Tim Teknis.")
                    
                    assert current_kkpr_verdict is not None
                    staf_verdict = verdict_map[current_kkpr_verdict]

                    existing_telaah = self.telaah_staf_repo.find_by_permohonan_id(permohonan.id_permohonan)
                    id_telaah = existing_telaah.id_telaah if existing_telaah else f"tel-{uuid.uuid4().hex[:12]}"

                    telaah_staf = TelaahStaf(
                        id_telaah=id_telaah,
                        id_permohonan=permohonan.id_permohonan,
                        verdict=staf_verdict,
                        verifier=VerifierInfo(
                            name=input_dto.actor_name, 
                            nip=input_dto.nip or "19800523", 
                            timestamp=datetime.now(),
                            signature_base64=input_dto.signature_base64
                        ),
                        administrative_checklist=admin_items,
                        technical_matrix=tech_items,
                        admin_verifier_name=admin_verifier_name,
                        admin_verifier_nip=admin_verifier_nip,
                        admin_verified_at=admin_verified_at_str
                    )

                    self.telaah_staf_repo.save(telaah_staf, commit=False)

                    try:
                        self.document_generator.generate_telaah_staf_pdf(
                            telaah_staf=telaah_staf,
                            permohonan=permohonan
                        )
                    except Exception as doc_err:
                        logger.error(f"[USE_CASE_WARNING] PDF rendering gagal tetapi database dipertahankan aman: {str(doc_err)}")

                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()

                    # Merakit detail penandaan galat m² secara fisik untuk dicatat pada notes audit log
                    audit_notes_list = []
                    if permohonan.land_area_error_sqm is not None:
                        audit_notes_list.append(f"Galat Luas Lahan: {permohonan.land_area_error_sqm:+.2f} m² ({permohonan.land_area_error_percent:+.2f}%)")
                    if permohonan.building_area_error_sqm is not None:
                        audit_notes_list.append(f"Galat Luas Tapak: {permohonan.building_area_error_sqm:+.2f} m² ({permohonan.building_area_error_percent:+.2f}%)")
                    audit_notes_str = "; ".join(audit_notes_list) if audit_notes_list else "Tidak ada selisih."

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="SAVE_TECHNICAL_MATRIX",
                        status_before=status_awal.value, status_after=status_awal.value,
                        notes=f"Draf matriks penilaian disimpan. Dokumen Telaah Staf '{id_telaah}' berhasil diterbitkan. [{audit_notes_str}]"
                    )
                    return permohonan

                # Skenario 2: Tim Teknis menandatangani berkas (Kirim ke Kabid)
                else:
                    telaah_staf = self.telaah_staf_repo.find_by_permohonan_id(permohonan.id_permohonan)
                    if not telaah_staf:
                        raise ValueError("Gagal: Draf dokumen Telaah Staf belum dibuat. Harap simpan penilaian matriks terlebih dahulu.")

                    # ─── PEMBARUAN v10.3: LOGIKA VALIDASI PRA-SYARAT VERIFIKASI TEKNIS LEVEL USE CASE ───
                    # Skenario kategori wajib yang memiliki dampak tata ruang masif
                    if permohonan.submission_category in ["PERUMAHAN", "INDUSTRI", "NON_PERUMAHAN"]:
                        if not permohonan.inspection_logs or len(permohonan.inspection_logs) == 0:
                            raise ValueError(
                                f"Gagal: Minimal harus terdapat 1 data log kunjungan lapangan darat (Ground Inspection) "
                                f"sebelum berkas '{permohonan.submission_no}' dapat dikirim ke Kepala Bidang."
                            )
                        # Video drone udara wajib mutlak untuk perumahan & industri
                        if permohonan.submission_category in ["PERUMAHAN", "INDUSTRI"] and not permohonan.aerial_inspection:
                            raise ValueError(
                                f"Gagal: Rekaman video udara (Aerial Drone Inspection) wajib diunggah untuk kategori "
                                f"'{permohonan.submission_category}' sebelum draf Telaah Staf dapat dikirim ke Kepala Bidang."
                            )

                    updated_verifier = VerifierInfo(
                        name=input_dto.actor_name,
                        nip=input_dto.nip or telaah_staf.verifier.nip or "19800523",
                        timestamp=datetime.now(),
                        signature_base64=input_dto.signature_base64
                    )
                    
                    updated_telaah_staf = TelaahStaf(
                        id_telaah=telaah_staf.id_telaah,
                        id_permohonan=telaah_staf.id_permohonan,
                        verdict=telaah_staf.verdict,
                        verifier=updated_verifier,
                        administrative_checklist=telaah_staf.administrative_checklist,
                        technical_matrix=telaah_staf.technical_matrix,
                        created_at=telaah_staf.created_at,
                        endorser=telaah_staf.endorser,
                        is_overridden=telaah_staf.is_overridden,
                        override_reason=telaah_staf.override_reason,
                        admin_verifier_name=telaah_staf.admin_verifier_name,
                        admin_verifier_nip=telaah_staf.admin_verifier_nip,
                        admin_verified_at=telaah_staf.admin_verified_at
                    )
                    
                    self.telaah_staf_repo.save(updated_telaah_staf, commit=False)

                    try:
                        self.document_generator.generate_telaah_staf_pdf(
                            telaah_staf=updated_telaah_staf,
                            permohonan=permohonan,
                            generated_by=input_dto.actor_name
                        )
                    except Exception as doc_err:
                        logger.error(f"[USE_CASE_WARNING] PDF rendering final gagal: {str(doc_err)}")

                    permohonan.transition_status(SubmissionStatus.MENUNGGU_REKOMENDASI)
                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="GENERATE_TELAAH_STAF",
                        status_before=status_awal.value, status_after=SubmissionStatus.MENUNGGU_REKOMENDASI.value,
                        notes=f"Lembar Telaah Staf disetujui & ditandatangani oleh Tim Teknis. Berkas diteruskan ke Kabid. Catatan: {input_dto.notes}"
                    )
                    return permohonan

            return await asyncio.to_thread(execute_technical_review)

        # ======================================================================
        # TAHAP C: ULASAN & HAK VETO KEPALA BIDANG (MENUNGGU_REKOMENDASI)
        # ======================================================================
        elif status_awal == SubmissionStatus.MENUNGGU_REKOMENDASI:
            def execute_kabid_review() -> Permohonan:
                telaah_staf = self.telaah_staf_repo.find_by_permohonan_id(permohonan.id_permohonan)
                if not telaah_staf:
                    logger.warning(
                        "[VERIFY_FALLBACK] Dokumen Telaah Staf tidak ditemukan untuk permohonan %s; membuat draft minimal untuk melanjutkan alur Kabid.",
                        permohonan.id_permohonan
                    )
                    telaah_staf = self._build_fallback_telaah_staf(
                        permohonan=permohonan,
                        actor_name=input_dto.actor_name,
                        actor_nip=input_dto.nip,
                        signature_base64=input_dto.signature_base64
                    )
                    self.telaah_staf_repo.save(telaah_staf, commit=False)

                # Skenario R1: Pengembalian Internal Kabid -> Tim Teknis
                if input_dto.action_type == "REVERT_TO_TECHNICAL":
                    permohonan.transition_status(SubmissionStatus.VERIFIKASI_TEKNIS)
                    self.permohonan_repo.save(permohonan)
                    
                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="REVERT_KABID_TO_TECHNICAL",
                        status_before=status_awal.value, status_after=SubmissionStatus.VERIFIKASI_TEKNIS.value,
                        notes=f"[PENGEMBALIAN INTERNAL] Kabid mengembalikan draf Telaah Staf ke Tim Teknis. Catatan: {input_dto.notes}"
                    )
                    return permohonan

                # Skenario B: Kabid setuju (APPROVE) / merekomendasikan penolakan (REJECT) -> Diteruskan ke meja Kadis dengan draf SK
                elif input_dto.action_type in ["APPROVE", "REJECT"]:
                    telaah_staf.endorse_by_kabid(input_dto.actor_name, input_dto.nip or "19840212")
                    self.telaah_staf_repo.save(telaah_staf, commit=False)

                    # Tentukan status akhir yang diusulkan oleh Kabid
                    if input_dto.action_type == "REJECT":
                        sk_verdict = SkVerdict.DITOLAK
                    else:
                        verdict_map = {
                            TelaahStafVerdict.SESUAI: SkVerdict.DAPAT_DISETUJUI,
                            TelaahStafVerdict.SESUAI_BERSYARAT: SkVerdict.DISETUJUI_BERSYARAT,
                            TelaahStafVerdict.PERLU_PERBAIKAN: SkVerdict.PERLU_REVISI,
                            TelaahStafVerdict.TIDAK_SESUAI: SkVerdict.DITOLAK
                        }
                        sk_verdict = verdict_map.get(telaah_staf.verdict, SkVerdict.DAPAT_DISETUJUI)

                    # 1. Menentukan Nomor Urut SK (Sequence No) dari repositori
                    sequence_no = self.sk_draft_repo.get_next_sequence_no()
                    id_sk = f"sk-{uuid.uuid4().hex[:12]}"

                    # 2. Merakit Value Objects Konsiderans (Jombang Style)
                    konsiderans = SkConsiderations(
                        menimbang=[
                            "Bahwa untuk memberikan kepastian hukum pembangunan fisik dan penyediaan perumahan "
                            "yang layak, sehat, aman, dan selaras dengan lingkungan, perlu diterbitkan keputusan "
                            "persetujuan rencana tapak (site plan)." if sk_verdict in [SkVerdict.DAPAT_DISETUJUI, SkVerdict.DISETUJUI_BERSYARAT] else
                            "Bahwa berdasarkan hasil telaah administratif dan teknis lapangan, permohonan pengesahan rencana tapak "
                            "tersebut dinilai belum memenuhi keselarasan tata ruang (RDTR) atau kriteria teknis.",
                            "Bahwa keputusan ini merupakan hasil pemeriksaan berkas dan peninjauan lapangan yang sah."
                        ],
                        mengingat=[
                            "Undang-Undang Nomor 1 Tahun 2011 tentang Perumahan dan Kawasan Permukiman.",
                            "Undang-Undang Nomor 26 Tahun 2007 tentang Penataan Ruang.",
                            "Peraturan Daerah Kabupaten Jombang / Kabupaten Bogor tentang Rencana Detail Tata Ruang (RDTR).",
                            "Peraturan Bupati tentang Penyelenggaraan Pelayanan Pengesahan Rencana Tapak Digital."
                        ],
                        memperhatikan=[
                            f"Surat Permohonan dari Developer tanggal {permohonan.submission_date.strftime('%d-%m-%Y') if permohonan.submission_date else '-'}.",
                            f"Persetujuan Pernyataan Kesanggupan Pengelolaan Lingkungan Hidup (SPPL) Nomor: {permohonan.spatial_kkpr_number or '-'}.",
                            f"Dokumen hasil evaluasi teknis dan Lembar Telaah Staf Nomor: TS-{permohonan.submission_no}."
                        ]
                    )

                    # 3. Merakit Value Objects Diktum Teknis dari Verified Metrics
                    diktum_hunian_list = [
                        SkDiktumHunian(
                            tipe_rumah="Kaveling Hunian Utama",
                            jumlah_unit=permohonan.tech_lot_count if permohonan.tech_lot_count is not None else 0,
                            luas_m2=float(permohonan.tech_total_floor_area) if permohonan.tech_total_floor_area is not None else 0.0
                        )
                    ]

                    # Ekstrak data ROW Jalan Utama & Lokal (Mencegah Parse Error)
                    def extract_numeric_row(row_str: Optional[str], default_val: float) -> float:
                        if not row_str:
                            return default_val
                        try:
                            clean_str = "".join([c for c in row_str if c.isdigit() or c == "."])
                            return float(clean_str) if clean_str else default_val
                        except Exception:
                            return default_val

                    road_min = extract_numeric_row(permohonan.tech_road_row_local, 6.0)
                    road_max = extract_numeric_row(permohonan.tech_road_row_main, 10.0)

                    diktum_psu = SkDiktumPsu(
                        total_psu_area_m2=permohonan.verified_rth_area if permohonan.verified_rth_area is not None else 0.0,
                        allocation_details="Jaringan Jalan, Ruang Terbuka Hijau (Taman), Fasos, dan Sarana Umum",
                        cemetery_scheme=f"Penyediaan lahan makam TPU fisik seluas {permohonan.tech_cemetery_area if permohonan.tech_cemetery_area is not None else 0.0} m²",
                        road_row_min=road_min,
                        road_row_max=road_max
                    )

                    diktum_intensity = SkDiktumIntensity(
                        kdb_max=permohonan.verified_kdb_percentage if permohonan.verified_kdb_percentage is not None else (permohonan.bylaw_max_kdb or 60.0),
                        klb_max=permohonan.verified_klb_ratio if permohonan.verified_klb_ratio is not None else (permohonan.bylaw_max_klb or 3.5),
                        kdh_min=permohonan.verified_kdh_percentage if permohonan.verified_kdh_percentage is not None else (permohonan.bylaw_min_kdh or 10.0)
                    )

                    # 4. Instansiasi dan Simpan Domain Entity SkDraft ke Repositori secara Atomic
                    sk_draft = SkDraft(
                        id_sk=id_sk,
                        id_permohonan=permohonan.id_permohonan,
                        sequence_no=sequence_no,
                        considerations=konsiderans,
                        diktum_hunian=diktum_hunian_list,
                        diktum_psu=diktum_psu,
                        diktum_intensity=diktum_intensity,
                        verdict=sk_verdict,
                        custom_notes=input_dto.notes
                    )
                    self.sk_draft_repo.save(sk_draft, commit=False)

                    # Menyematkan Nomor SK ter-generate ke model Permohonan
                    permohonan.sk_number = sk_draft.sk_number

                    # 5. Memanggil DocumentGenerator untuk mengompilasi PDF Draf SK
                    try:
                        self.document_generator.generate_draft_sk_siteplan(
                            permohonan,
                            sk_draft,
                            notes_by_kabid=input_dto.notes,
                            generated_by=input_dto.actor_name
                        )
                    except Exception as doc_err:
                        logger.error(f"[SK_RENDER_WARNING] Draf SK gagal dicetak: {str(doc_err)}")

                    permohonan.kabid_signature = input_dto.signature_base64
                    permohonan.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)
                    
                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="KABID_ENDORSE_APPROVE" if input_dto.action_type == "APPROVE" else "KABID_ENDORSE_REJECT",
                        status_before=status_awal.value, status_after=SubmissionStatus.MENUNGGU_PERSETUJUAN.value,
                        notes=(
                            f"Telaah Staf ditelaah & diparaf Kabid (Rekomendasi: {sk_verdict.value}). Draf SK Nomor '{sk_draft.sk_number}' "
                            f"berhasil digenerasi dan diteruskan ke Kepala Dinas."
                        )
                    )
                    return permohonan

                # Skenario C: KABID OVERRIDE VETO -> Tolak usulan revisi Tim Teknis
                elif input_dto.action_type == "OVERRIDE_VERDICT":
                    if not input_dto.kkpr_verdict:
                        raise ValueError("Gagal: Kabid wajib menentukan verdict pengganti saat melakukan override teknis.")

                    verdict_map = {
                        KKPRVerdict.SESUAI: TelaahStafVerdict.SESUAI,
                        KKPRVerdict.SESUAI_BERSYARAT: TelaahStafVerdict.SESUAI_BERSYARAT,
                        KKPRVerdict.PERLU_PERBAIKAN: TelaahStafVerdict.PERLU_PERBAIKAN,
                        KKPRVerdict.TIDAK_SESUAI: TelaahStafVerdict.TIDAK_SESUAI
                    }
                    normalized_verdict = normalize_kkpr_verdict_string(input_dto.kkpr_verdict)
                    override_verdict = verdict_map[KKPRVerdict(normalized_verdict)]
                    
                    telaah_staf.override_by_kabid(
                        kabid_name=input_dto.actor_name, kabid_nip=input_dto.nip or "19840212",
                        new_verdict=override_verdict, reason=input_dto.notes
                    )
                    self.telaah_staf_repo.save(telaah_staf, commit=False)

                    permohonan.kkpr_verdict = KKPRVerdict(normalized_verdict)
                    permohonan.kabid_signature = input_dto.signature_base64

                    # Override juga memicu pembuatan SkDraft
                    sequence_no = self.sk_draft_repo.get_next_sequence_no()
                    id_sk = f"sk-{uuid.uuid4().hex[:12]}"

                    konsiderans = SkConsiderations(
                        menimbang=[
                            "Bahwa Kepala Bidang menggunakan hak diskresi untuk menyetujui rencana tapak.",
                            f"Justifikasi Diskresi: {input_dto.notes}"
                        ],
                        mengingat=[
                            "Undang-Undang Nomor 1 Tahun 2011 tentang Perumahan dan Kawasan Permukiman.",
                            "Peraturan Daerah Kabupaten Jombang / Kabupaten Bogor tentang Rencana Detail Tata Ruang (RDTR)."
                        ],
                        memperhatikan=[
                            f"Lembar Telaah Staf Khusus Veto Nomor: TS-{permohonan.submission_no}."
                        ]
                    )

                    diktum_hunian_list = [
                        SkDiktumHunian(
                            tipe_rumah="Kaveling Hunian (Override)",
                            jumlah_unit=permohonan.tech_lot_count if permohonan.tech_lot_count is not None else 0,
                            luas_m2=float(permohonan.tech_total_floor_area) if permohonan.tech_total_floor_area is not None else 0.0
                        )
                    ]

                    diktum_psu = SkDiktumPsu(
                        total_psu_area_m2=permohonan.verified_rth_area if permohonan.verified_rth_area is not None else 0.0,
                        allocation_details="Sesuai Lampiran Gambar Override",
                        cemetery_scheme="Sesuai Aturan Kerjasama Makam",
                        road_row_min=6.0,
                        road_row_max=10.0
                    )

                    diktum_intensity = SkDiktumIntensity(
                        kdb_max=permohonan.verified_kdb_percentage if permohonan.verified_kdb_percentage is not None else 60.0,
                        klb_max=permohonan.verified_klb_ratio if permohonan.verified_klb_ratio is not None else 3.5,
                        kdh_min=permohonan.verified_kdh_percentage if permohonan.verified_kdh_percentage is not None else 10.0
                    )

                    sk_verdict_map = {
                        TelaahStafVerdict.SESUAI: SkVerdict.DAPAT_DISETUJUI,
                        TelaahStafVerdict.SESUAI_BERSYARAT: SkVerdict.DISETUJUI_BERSYARAT,
                        TelaahStafVerdict.PERLU_PERBAIKAN: SkVerdict.PERLU_REVISI,
                        TelaahStafVerdict.TIDAK_SESUAI: SkVerdict.DITOLAK
                    }
                    sk_verdict = sk_verdict_map[override_verdict]

                    sk_draft = SkDraft(
                        id_sk=id_sk,
                        id_permohonan=permohonan.id_permohonan,
                        sequence_no=sequence_no,
                        considerations=konsiderans,
                        diktum_hunian=diktum_hunian_list,
                        diktum_psu=diktum_psu,
                        diktum_intensity=diktum_intensity,
                        verdict=sk_verdict,
                        custom_notes=f"[VETO OVERRIDE] {input_dto.notes}"
                    )
                    self.sk_draft_repo.save(sk_draft, commit=False)

                    permohonan.sk_number = sk_draft.sk_number

                    try:
                        self.document_generator.generate_telaah_staf_pdf(
                            telaah_staf=telaah_staf,
                            permohonan=permohonan,
                            generated_by=input_dto.actor_name
                        )
                        self.document_generator.generate_draft_sk_siteplan(
                            permohonan,
                            sk_draft,
                            notes_by_kabid=f"[VETO OVERRIDE] {input_dto.notes}",
                            generated_by=input_dto.actor_name
                        )
                    except Exception as doc_err:
                        logger.error(f"[VETO_PDF_WARNING] Gagal memperbarui berkas PDF veto: {str(doc_err)}")

                    permohonan.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)
                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="KABID_OVERRIDE_VETO",
                        status_before=status_awal.value, status_after=SubmissionStatus.MENUNGGU_PERSETUJUAN.value,
                        notes=(
                            f"[VETO HAK KHUSUS] Kabid menolak usulan teknis, merilis SK Nomor '{sk_draft.sk_number}' "
                            f"dengan keputusan akhir '{input_dto.kkpr_verdict}'."
                        )
                    )
                    return permohonan

                # Skenario D: KABID REVISI -> Langsung kembalikan ke Pemohon tanpa SK formal (Surat Pemberitahuan)
                elif input_dto.action_type == "REVERT_TO_PEMOHON":
                    if not input_dto.notes:
                        raise ValueError("Catatan alasan revisi wajib diisi agar pemohon dapat memperbaiki berkas.")

                    permohonan.transition_status(SubmissionStatus.DITOLAK)
                    self.permohonan_repo.save(permohonan, commit=False)
                    self.permohonan_repo.commit()

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="KABID_REVISI_KE_PEMOHON",
                        status_before=status_awal.value, status_after=SubmissionStatus.DITOLAK.value,
                        notes=(
                            f"[SURAT PEMBERITAHUAN REVISI] Kabid mengembalikan berkas ke Pemohon tanpa SK formal. "
                            f"Alasan: {input_dto.notes}"
                        )
                    )
                    return permohonan

                else:
                    raise ValueError(f"Ilegal: Aksi '{input_dto.action_type}' tidak diizinkan pada tahap rekomendasi Kabid.")

            return await asyncio.to_thread(execute_kabid_review)

        # ======================================================================
        # TAHAP D: KEPUTUSAN FINAL & TTE KEPALA DINAS (MENUNGGU_PERSETUJUAN)
        # ======================================================================
        else:
            # Skenario R2: Pengembalian Internal Kadis -> Kabid
            if input_dto.action_type == "REVERT_TO_TECHNICAL":
                def execute_kadis_revert() -> Permohonan:
                    permohonan.transition_status(SubmissionStatus.MENUNGGU_REKOMENDASI)
                    self.permohonan_repo.save(permohonan)

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="REVERT_KADIS_TO_KABID",
                        status_before=status_awal.value, status_after=SubmissionStatus.MENUNGGU_REKOMENDASI.value,
                        notes=f"[PENGEMBALIAN INTERNAL] Kadis mengembalikan draf SK ke Kabid untuk diperbaiki. Catatan: {input_dto.notes}"
                    )
                    return permohonan

                return await asyncio.to_thread(execute_kadis_revert)

            # Skenario A: Kadis menolak keras berkas (REJECT) -> Terminal Ditolak
            elif input_dto.action_type == "REJECT":
                def execute_kadis_reject() -> Permohonan:
                    permohonan.transition_status(SubmissionStatus.DITOLAK)
                    self.permohonan_repo.save(permohonan)

                    self.audit_trail_repo.log_action(
                        submission_id=permohonan.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action="VERIFY_KADIS_REJECTED",
                        status_before=status_awal.value, status_after=SubmissionStatus.DITOLAK.value,
                        notes=f"Penolakan Final Kepala Dinas. Berkas dikembalikan ke pemohon: {input_dto.notes}"
                    )
                    return permohonan

                return await asyncio.to_thread(execute_kadis_reject)

            # Skenario B: Kadis APPROVE & TTE SK FINAL (Tanda Tangan Coret Visual)
            elif input_dto.action_type == "APPROVE":
                if not input_dto.nip:
                    raise ValueError("Gagal: Kredensial NIP resmi Kepala Dinas (KADIS) wajib dilampirkan.")
                if not input_dto.signature_base64:
                    raise ValueError("Gagal: Coretan visual tanda tangan Kepala Dinas wajib dilampirkan.")

                # Penegasan Tipe untuk Menjamin Type Safety pada Pylance Static Analyzer (MyPy Guard)
                kadis_nip_clean: str = input_dto.nip
                kadis_sig_clean: str = input_dto.signature_base64

                # ─── PENYEMATAN VISUAL TTE KADIS PADA SK_DRAFT ───
                def fetch_and_sign_sk_draft() -> SkDraft:
                    sk_draft_obj = self.sk_draft_repo.find_by_permohonan_id(permohonan.id_permohonan)
                    if not sk_draft_obj:
                        raise ValueError("Gagal: Objek draf keputusan (SkDraft) tidak ditemukan untuk permohonan ini.")
                    
                    # Sematkan visual tanda tangan ke dalam entitas domain SkDraft
                    sk_draft_obj.apply_drawn_signature(
                        kadis_name=input_dto.actor_name,
                        kadis_nip=kadis_nip_clean,
                        signature_base64=kadis_sig_clean
                    )
                    self.sk_draft_repo.save(sk_draft_obj, commit=False)
                    return sk_draft_obj

                # Ambil draf keputusan terhitung
                sk_draft = await asyncio.to_thread(fetch_and_sign_sk_draft)

                # Generasikan dokumen biner PDF SK final bertanda tangan Kadis
                sk_path = await asyncio.to_thread(
                    self.document_generator.generate_final_sk_siteplan, 
                    permohonan, 
                    sk_draft,
                    input_dto.actor_name
                )

                # State Locking: Transisi berkas ke status 'Proses TTE' untuk mencegah race condition tombol
                def lock_status_to_proses_tte() -> Permohonan:
                    p = self.permohonan_repo.find_by_id(permohonan.id_permohonan)
                    if not p: 
                        raise ValueError("Permohonan hilang secara tidak sengaja.")
                    p.transition_status(SubmissionStatus.PROSES_TTE)
                    self.permohonan_repo.save(p, commit=True)
                    return p

                await asyncio.to_thread(lock_status_to_proses_tte)

                # Mengirim draf ke BSrE Client / mensimulasikan hash kriptografis unik
                try:
                    crypto_hash = await self.digital_signature_client.sign_pdf_document(
                        pdf_path=sk_path,
                        certificate_owner_nip=kadis_nip_clean,
                        passphrase=input_dto.passphrase if input_dto.passphrase else "bypass_passphrase"
                    )
                except Exception as e:
                    logger.error(f"[TTE_TRANSACTION_FAILURE] TTE BSrE gagal diproses: {str(e)}. Rollback status...")
                    def rollback_tte_failure() -> None:
                        self.permohonan_repo.rollback()
                        self.permohonan_repo.expire_all()
                        p = self.permohonan_repo.find_by_id(permohonan.id_permohonan)
                        if p:
                            p.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)
                            self.permohonan_repo.save(p, commit=True)

                    await asyncio.to_thread(rollback_tte_failure)
                    raise RuntimeError(f"Proses TTE gagal disahkan: {str(e)}")

                # Commit Final: TTE Sukses, sahkan izin secara hukum transaksional
                def commit_final_success() -> Permohonan:
                    p = self.permohonan_repo.find_by_id(permohonan.id_permohonan)
                    if not p: 
                        raise ValueError("Permohonan hilang pasca-TTE.")

                    is_approved = sk_draft.verdict in [SkVerdict.DAPAT_DISETUJUI, SkVerdict.DISETUJUI_BERSYARAT]
                    signed_url = f"/api/v1/submissions/{p.id_permohonan}/download"
                    p.attach_signature(crypto_hash, signed_url, is_approved=is_approved)
                    p.kadis_signature = kadis_sig_clean           # Coretan TTE Kadis
                    p.sk_number = sk_draft.sk_number               # Rekam Nomor SK ke tabel Permohonan

                    # Nonaktifkan SK lama yang digantikan (semua parent digital)
                    for parent_lin in p.parents_lineage:
                        if parent_lin.baseline_source == "DIGITAL" and parent_lin.parent_id:
                            parent_p = self.permohonan_repo.find_by_id(parent_lin.parent_id)
                            if parent_p and parent_p.status != SubmissionStatus.TIDAK_BERLAKU:
                                parent_p.status = SubmissionStatus.TIDAK_BERLAKU
                                self.permohonan_repo.save(parent_p, commit=False)
                                
                                # Log audit trail untuk parent yang dinonaktifkan
                                self.audit_trail_repo.log_action(
                                    submission_id=parent_p.id_permohonan,
                                    actor_name=input_dto.actor_name,
                                    role=input_dto.role,
                                    action="SUPERSEDED_BY_NEW_SK",
                                    status_before=SubmissionStatus.DISETUJUI.value,
                                    status_after=SubmissionStatus.TIDAK_BERLAKU.value,
                                    notes=(
                                        f"SK ini resmi dicabut/dinyatakan tidak berlaku karena telah "
                                        f"dilebur/dipecah ke dalam SK baru Nomor: {sk_draft.sk_number} "
                                        f"(ID Permohonan Pengganti: {p.id_permohonan})."
                                    ),
                                    commit=False
                                )

                    # Nonaktifkan semua SK lama lainnya yang tumpang tindih secara spasial
                    try:
                        overlaps = self.permohonan_repo.find_spatial_overlaps(p.id_permohonan)
                        for item in overlaps:
                            if item.get("status") == "Disetujui":
                                overlapping_p = self.permohonan_repo.find_by_id(item["id_permohonan"])
                                if overlapping_p:
                                    overlapping_p.status = SubmissionStatus.TIDAK_BERLAKU
                                    self.permohonan_repo.save(overlapping_p, commit=False)
                    except Exception as e:
                        logger.error(f"[AUTO_DEACTIVATE_OVERLAPS_ERROR] Gagal menonaktifkan overlap otomatis: {str(e)}")

                    self.permohonan_repo.save(p, commit=False)
                    
                    final_status_val = SubmissionStatus.DISETUJUI.value if is_approved else SubmissionStatus.DITOLAK.value
                    action_name = "APPROVE_KADIS_TTE" if is_approved else "REJECT_KADIS_TTE"
                    notes_text = (
                        f"SK Site Plan resmi disahkan & diterbitkan oleh Kepala Dinas dengan Nomor: {sk_draft.sk_number}. Kode Hash TTE: {crypto_hash}."
                        if is_approved else
                        f"SK Penolakan/Revisi Rencana Tapak resmi disahkan oleh Kepala Dinas dengan Nomor: {sk_draft.sk_number}. Kode Hash TTE: {crypto_hash}."
                    )
                    self.audit_trail_repo.log_action(
                        submission_id=p.id_permohonan, actor_name=input_dto.actor_name,
                        role=input_dto.role, action=action_name,
                        status_before=SubmissionStatus.PROSES_TTE.value, status_after=final_status_val,
                        notes=notes_text,
                        digital_signature_hash=crypto_hash, commit=False
                    )
                    self.permohonan_repo.commit()
                    logger.info(f"[USE_CASE] Sukses menyelesaikan TTE birokrasi permohonan ID: {p.id_permohonan}")
                    return p

                return await asyncio.to_thread(commit_final_success)

            else:
                raise ValueError(f"Ilegal: Aksi '{input_dto.action_type}' tidak diizinkan pada meja Kepala Dinas.")

    def _to_payload(self, entity: Any) -> dict:
        return entity.to_dict() if hasattr(entity, "to_dict") else {}


# ─── SECTION 6: PURE FABRICATION - LINK PARENT USE CASE ──────────────────────

class LinkParentSubmissionUseCase:
    """
    Kelas Pure Fabrication untuk mengisolasi tanggung jawab pengaitan silsilah permohonan
    sebelumnya (parent-child) secara transaksional, lengkap dengan penegakan SoD 
    dan mitigasi silsilah melingkar (circular ancestry).
    """
    def __init__(
        self,
        permohonan_repo: ExtendedPermohonanRepositoryPort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        self.permohonan_repo = permohonan_repo
        self.audit_trail_repo = audit_trail_repo

    def _detect_circular_ancestry(self, child_id: str, target_parent_id: str) -> bool:
        """Mendeteksi circular dependency di level logika silsilah."""
        return self.permohonan_repo.check_ancestry_loop(child_id, target_parent_id)

    async def execute(self, input_dto: LinkParentSubmissionInputDto) -> Permohonan:
        """Mengeksekusi pengaitan silsilah secara transaksional."""
        
        if input_dto.role != "ADMIN":
            logger.warning(
                "[SECURITY_ALERT] Non-ADMIN user '%s' (Role: %s) attempted to link parent lineage for submission: %s",
                input_dto.actor_name, input_dto.role, input_dto.id_permohonan
            )
            raise PermissionError(
                f"Akses Ditolak: Peran '{input_dto.role}' tidak memiliki otorisasi."
            )

        def get_current_permohonan() -> Permohonan:
            p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
            if not p:
                raise ValueError(f"Ilegal: Permohonan dengan ID '{input_dto.id_permohonan}' tidak ditemukan.")
            return p

        permohonan = await asyncio.to_thread(get_current_permohonan)

        parent_record = None
        from src.domain.entities.permohonan import SilsilahPermohonan
        
        if input_dto.baseline_source == "DIGITAL":
            if not input_dto.parent_id_permohonan:
                raise ValueError("Gagal: Parameter 'parent_id_permohonan' wajib disertakan untuk rujukan tipe 'DIGITAL'.")

            if self._detect_circular_ancestry(input_dto.id_permohonan, input_dto.parent_id_permohonan):
                logger.error(
                    "[LINEAGE_ERROR] Hubungan silsilah melingkar terdeteksi! Current ID: %s | Target Parent ID: %s",
                    input_dto.id_permohonan, input_dto.parent_id_permohonan
                )
                raise ValueError(
                    "Pemberitahuan Sistem: Hubungan silsilah melingkar terdeteksi. Pengaitan ditolak."
                )

            for parent_lin in permohonan.parents_lineage:
                if parent_lin.baseline_source == "DIGITAL" and parent_lin.parent_id == input_dto.parent_id_permohonan:
                    raise ValueError(f"Pemberitahuan Sistem: SK rujukan ID '{input_dto.parent_id_permohonan}' sudah ditautkan.")

            def get_parent_permohonan() -> Permohonan:
                target_parent_id: str = cast(str, input_dto.parent_id_permohonan)
                parent_p = self.permohonan_repo.find_by_id(target_parent_id)
                if not parent_p:
                    raise ValueError(f"Gagal: Permohonan rujukan tidak ditemukan.")
                return parent_p

            parent_record = await asyncio.to_thread(get_parent_permohonan)

            permohonan.parents_lineage.append(
                SilsilahPermohonan(
                    id_silsilah=None,
                    child_id=permohonan.id_permohonan,
                    baseline_source="DIGITAL",
                    parent_id=parent_record.id_permohonan,
                    legacy_sk_number=parent_record.sk_number or "-",
                    legacy_sk_date=parent_record.submission_date,
                    legacy_sk_doc_url=parent_record.signed_pdf_url
                )
            )

        elif input_dto.baseline_source == "LEGACY":
            if not input_dto.replaced_sk_number:
                raise ValueError("Gagal: Parameter 'replaced_sk_number' wajib disertakan untuk rujukan tipe 'LEGACY'.")
            if not input_dto.replaced_sk_date:
                raise ValueError("Gagal: Parameter 'replaced_sk_date' wajib disertakan untuk rujukan tipe 'LEGACY'.")
            if not input_dto.replaced_sk_doc_url:
                raise ValueError("Gagal: Parameter 'replaced_sk_doc_url' wajib disertakan untuk rujukan tipe 'LEGACY'.")

            for parent_lin in permohonan.parents_lineage:
                if parent_lin.baseline_source == "LEGACY" and parent_lin.legacy_sk_number == input_dto.replaced_sk_number:
                    raise ValueError(f"Pemberitahuan Sistem: SK rujukan nomor '{input_dto.replaced_sk_number}' sudah ditautkan.")

            permohonan.parents_lineage.append(
                SilsilahPermohonan(
                    id_silsilah=None,
                    child_id=permohonan.id_permohonan,
                    baseline_source="LEGACY",
                    legacy_sk_number=input_dto.replaced_sk_number,
                    legacy_sk_date=input_dto.replaced_sk_date,
                    legacy_sk_doc_url=input_dto.replaced_sk_doc_url
                )
            )

        else:
            raise ValueError(f"Gagal: Jenis baseline_source '{input_dto.baseline_source}' tidak valid.")

        permohonan.submission_type = "REVISI"

        def persist_linkage() -> None:
            self.permohonan_repo.save(permohonan, commit=False)
            self.audit_trail_repo.log_action(
                submission_id=permohonan.id_permohonan,
                actor_name=input_dto.actor_name,
                role=input_dto.role,
                action="LINK_PARENT_LINEAGE",
                status_before=permohonan.status.value,
                status_after=permohonan.status.value,
                notes=(
                    f"Admin mengaitkan silsilah permohonan dengan SK rujukan tipe '{input_dto.baseline_source}'. "
                    f"Nomor SK Rujukan: {input_dto.replaced_sk_number or (parent_record.sk_number if 'parent_record' in locals() and parent_record else None) or '-'}. Catatan Admin: {input_dto.notes}"
                ),
                commit=False
            )
            self.permohonan_repo.commit()

        await asyncio.to_thread(persist_linkage)
        logger.info(f"[USE_CASE] Sukses mengaitkan silsilah permohonan ID '{permohonan.id_permohonan}' secara hukum transaksional.")
        return permohonan