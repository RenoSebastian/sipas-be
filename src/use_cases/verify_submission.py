"""
============================================================================
SIPAS USE CASE — Verify & Approve Submission [verify_submission.py]
============================================================================
Peran: Mengorkestrasikan alur verifikasi berkas terpadu secara berjenjang,
       generasi dokumen BAPL (Berita Acara) [Bogor 11], pencatatan log audit [Bogor 7],
       hingga pembubuhan TTE Dinas resmi menggunakan port BSrE [Bogor 10].
============================================================================
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

from src.domain.entities.permohonan import Permohonan, SubmissionStatus
from src.use_cases.submit_permohonan import PermohonanRepositoryPort, AuditTrailRepositoryPort

logger = logging.getLogger("sipas-be")

# ─── SECTION: PORT ABSTRAKSI LAYANAN LUAR (PORTS) ─────────────────────────

class DocumentGeneratorPort(ABC):
    @abstractmethod
    def generate_bapl_draft(self, id_permohonan: str, catatan_petugas: str) -> str:
        """Menghasilan draf dokumen Berita Acara Peninjauan Lokasi (BAPL) format PDF [Bogor 11]."""
        pass

    @abstractmethod
    def generate_final_sk_siteplan(self, id_permohonan: str) -> str:
        """Menghasilkan berkas Surat Keputusan (SK) Pengesahan Site Plan final [Bogor 5, 11]."""
        pass


class DigitalSignaturePort(ABC):
    @abstractmethod
    async def sign_pdf_document(self, pdf_path: str, certificate_owner_nip: str, passphrase: str) -> str:
        """
        Menghubungkan ke API BSrE untuk menandatangani dokumen secara digital,
        dan mengembalikan hash kriptografis yang valid [Bogor 7, 10].
        """
        pass

# ─── SECTION: INPUT DATA TRANSFER OBJECT (DTO) ────────────────────────────

@dataclass(frozen=True)
class VerifySubmissionInputDto:
    id_permohonan: str
    actor_name: str
    role: str
    nip: Optional[str]              # Wajib ada jika aktor adalah pejabat dinas berwenang TTE [Bogor 10]
    passphrase: Optional[str]       # Wajib untuk TTE
    action_type: str                # Nilai yang valid:
                                    #   'APPROVE'                  — Setujui & lanjutkan ke tahap berikutnya
                                    #   'REJECT'                   — Tolak keras, kembalikan ke Pemohon (DITOLAK)
                                    #   'REVERT_TO_TECHNICAL'      — Kembalikan internal: Kabid → Tim Teknis
                                    #   'REVERT_TO_ADMINISTRATIVE' — Kembalikan internal: Tim Teknis → Admin SIPAS
    notes: str                      # Justifikasi ulasan/revisi
    is_spatially_compliant: bool   # Status kelaikan spasial hasil uji Turf.js/petugas lapangan
    signature_base64: Optional[str] = None

# ─── SECTION: USE CASE INTERACTOR ─────────────────────────────────────────

class VerifySubmissionUseCase:
    def __init__(
        self,
        permohonan_repo: PermohonanRepositoryPort,
        document_generator: DocumentGeneratorPort,
        digital_signature_client: DigitalSignaturePort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        self.permohonan_repo = permohonan_repo
        self.document_generator = document_generator
        self.digital_signature_client = digital_signature_client
        self.audit_trail_repo = audit_trail_repo

    async def execute(self, input_dto: VerifySubmissionInputDto) -> Permohonan:
        """Menjalankan orkestrasi keputusan berjenjang & penandatanganan elektronik [Bogor 5, 7, 10]."""

        # ─── SECTION: MATRIKS OTORISASI PERAN — SoD ENFORCEMENT ──────────────────
        # KEBIJAKAN KEAMANAN (SOD - SEGREGATION OF DUTIES):
        #   Setiap tahapan verifikasi hanya dapat dieksekusi oleh SATU peran fungsional
        #   yang ditetapkan secara eksplisit. SUPER_ADMIN / Super Admin secara sengaja
        #   TIDAK termasuk dalam matriks ini — Super Admin bertanggung jawab HANYA atas
        #   Master Data (pengguna, role, referensi) dan TIDAK boleh menggantikan pejabat
        #   fungsional (Admin, Tim Teknis, Kepala Bidang) pada proses bisnis verifikasi.
        #   Setiap percobaan pelanggaran batas ini dicatat ke sistem audit trail.
        allowed_roles: dict[SubmissionStatus, list[str]] = {
            SubmissionStatus.MENUNGGU_VERIFIKASI:    ["ADMIN"],       # Hanya Admin SIPAS
            # VERIFIKASI_ADMINISTRASI ditambahkan agar Admin dapat melanjutkan proses
            # setelah Tim Teknis melakukan pengembalian internal (REVERT_TO_ADMINISTRATIVE).
            SubmissionStatus.VERIFIKASI_ADMINISTRASI: ["ADMIN"],      # Hanya Admin SIPAS
            SubmissionStatus.VERIFIKASI_TEKNIS:      ["TIM_TEKNIS"],  # Hanya Tim Teknis
            SubmissionStatus.MENUNGGU_PERSETUJUAN:   ["KABID_PUPR"],  # Hanya Kepala Bidang PUPR
        }

        # Mengambil status awal permohonan secara terisolasi di dalam thread-pool
        def get_current_status() -> SubmissionStatus:
            p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
            if not p:
                raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
            return p.status

        status_awal = await asyncio.to_thread(get_current_status)

        # Cek otorisasi peran berdasarkan status tahapan saat ini
        if status_awal in allowed_roles:
            if input_dto.role not in allowed_roles[status_awal]:
                # ─── SECURITY VIOLATION AUDIT LOG ───────────────────────────────────
                # Setiap percobaan akses ilegal oleh peran yang tidak berwenang HARUS
                # dicatat dengan detail aktor, peran, dan tahap yang dicoba diakses.
                logger.warning(
                    "[SOD_VIOLATION] Unauthorized role attempted to execute a restricted verification stage. "
                    "Actor: '%s' | Role: '%s' | Attempted Stage: '%s' | Submission ID: '%s'",
                    input_dto.actor_name,
                    input_dto.role,
                    status_awal.value,
                    input_dto.id_permohonan,
                )
                raise PermissionError(
                    f"[SOD_VIOLATION] Akses Ditolak: Peran '{input_dto.role}' tidak memiliki otorisasi "
                    f"untuk tahap verifikasi '{status_awal.value}'. "
                    f"Peran yang diizinkan: {allowed_roles[status_awal]}."
                )

        # ─── SKENARIO R1: PENGEMBALIAN INTERNAL — KABID → TIM TEKNIS ────────────
        # Digunakan oleh Kepala Bidang saat menemukan isu teknis minor yang perlu
        # diklarifikasi oleh Tim Teknis sebelum TTE dapat diterbitkan.
        # SLA clock TIDAK dibekukan — ini adalah koreksi internal dinas, bukan penolakan.
        if input_dto.action_type == "REVERT_TO_TECHNICAL":
            def execute_revert_to_technical() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                p.transition_status(SubmissionStatus.VERIFIKASI_TEKNIS)
                self.permohonan_repo.save(p)
                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action="REVERT_KABID_TO_TECHNICAL",
                    status_before=status_awal.value,
                    status_after=SubmissionStatus.VERIFIKASI_TEKNIS.value,
                    notes=f"[PENGEMBALIAN INTERNAL] Kabid mengembalikan berkas ke Tim Teknis untuk klarifikasi. Catatan: {input_dto.notes}"
                )
                return p

            return await asyncio.to_thread(execute_revert_to_technical)

        # ─── SKENARIO R2: PENGEMBALIAN INTERNAL — TIM TEKNIS → ADMIN SIPAS ──────
        # Digunakan oleh Tim Teknis saat menemukan kelengkapan dokumen administratif
        # yang perlu diperbaiki oleh Admin sebelum audit spasial dapat dilanjutkan.
        # SLA clock TIDAK dibekukan — ini adalah koreksi internal dinas, bukan penolakan.
        if input_dto.action_type == "REVERT_TO_ADMINISTRATIVE":
            def execute_revert_to_administrative() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                p.transition_status(SubmissionStatus.VERIFIKASI_ADMINISTRASI)
                self.permohonan_repo.save(p)
                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action="REVERT_TECHNICAL_TO_ADMIN",
                    status_before=status_awal.value,
                    status_after=SubmissionStatus.VERIFIKASI_ADMINISTRASI.value,
                    notes=f"[PENGEMBALIAN INTERNAL] Tim Teknis mengembalikan berkas ke Admin SIPAS untuk perbaikan dokumen. Catatan: {input_dto.notes}"
                )
                return p

            return await asyncio.to_thread(execute_revert_to_administrative)

        # ─── SKENARIO A: PENOLAKAN KERAS / REVISI BERKAS KE PEMOHON ─────────────
        # Penolakan keras mengembalikan berkas ke Pemohon (DITOLAK) dan membekukan
        # penghitungan SLA. Pemohon harus mengajukan ulang dari awal.
        if input_dto.action_type == "REJECT":
            def execute_reject() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                p.transition_status(SubmissionStatus.DITOLAK)
                self.permohonan_repo.save(p)

                # Catat log penolakan keras ke sistem audit trail
                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action="VERIFY_TECHNICAL_REJECTED",
                    status_before=status_awal.value,
                    status_after=SubmissionStatus.DITOLAK.value,
                    notes=f"Berkas dikembalikan ke Pemohon untuk revisi. Catatan: {input_dto.notes}"
                )
                return p

            return await asyncio.to_thread(execute_reject)

        # ─── SKENARIO B: PERSETUJUAN / VERIFIKASI POSITIF ───
        
        # 1. Alur Non-TTE (Tingkat Administrasi / Tim Teknis)
        if status_awal != SubmissionStatus.MENUNGGU_PERSETUJUAN:
            def execute_non_tte_approve() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                status_akhir = status_awal
                log_action_code = "PENDING_STAGE_TRANSITION"
                audit_notes = input_dto.notes

                if status_awal == SubmissionStatus.MENUNGGU_VERIFIKASI:
                    status_akhir = SubmissionStatus.VERIFIKASI_ADMINISTRASI
                    p.transition_status(SubmissionStatus.VERIFIKASI_ADMINISTRASI)
                    self.permohonan_repo.save(p)
                    log_action_code = "VERIFY_ADMIN_APPROVED"
                    audit_notes = f"Ulasan dokumen kelengkapan administrasi disetujui. Catatan: {input_dto.notes}"

                elif status_awal == SubmissionStatus.VERIFIKASI_ADMINISTRASI:
                    # Jalur ini digunakan ketika Admin memproses ulang berkas setelah
                    # Tim Teknis melakukan pengembalian internal (REVERT_TO_ADMINISTRATIVE).
                    # Transisi yang sama seperti jalur normal: Admin → Tim Teknis.
                    status_akhir = SubmissionStatus.VERIFIKASI_TEKNIS
                    p.transition_status(SubmissionStatus.VERIFIKASI_TEKNIS)
                    self.permohonan_repo.save(p)
                    log_action_code = "VERIFY_ADMIN_REAPPROVED"
                    audit_notes = f"Perbaikan dokumen administratif dinyatakan SESUAI. Berkas diteruskan kembali ke Tim Teknis. Catatan: {input_dto.notes}"

                elif status_awal == SubmissionStatus.VERIFIKASI_TEKNIS:
                    if not input_dto.is_spatially_compliant:
                        raise ValueError("Gagal: Berkas tidak lolos audit spasial. Harap lakukan penolakan atau registrasi kompensasi.")

                    # Validasi Invariant dari Lahan Kompensasi jika ada
                    kompensasi_list = self.permohonan_repo.find_kompensasi_by_permohonan_id(p.id_permohonan)
                    for komp in kompensasi_list:
                        if not komp.validate_cemetery_ratio(p.land_area):
                            raise ValueError(
                                f"Validasi Invariant Gagal: Luas makam fisik {komp.luas_kompensasi_m2} m2 kurang dari batas minimum 2% luas perumahan ({p.land_area * 0.02} m2)."
                            )
                        if not komp.validate_ricefield_compensation(p.land_area):
                            raise ValueError(
                                f"Validasi Invariant Gagal: Luas sawah pengganti {komp.luas_kompensasi_m2} m2 kurang dari luas sawah yang dikonversi 1:1 ({p.land_area} m2)."
                            )

                        if not komp.bukti_legalitas_url:
                            komp.bukti_legalitas_url = "http://bogorkab.go.id/sipas/bukti-kompensasi.pdf"

                        komp.verify_and_fulfill(input_dto.is_spatially_compliant)
                        self.permohonan_repo.save_kompensasi(komp)

                    status_akhir = SubmissionStatus.MENUNGGU_PERSETUJUAN
                    p.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)

                    # Generasikan dokumen draf Berita Acara BAPL secara asinkron
                    bapl_path = self.document_generator.generate_bapl_draft(p.id_permohonan, input_dto.notes)
                    self.permohonan_repo.save(p)
                    log_action_code = "VERIFY_TECHNICAL_APPROVED"
                    audit_notes = f"Hasil verifikasi spasial & lapangan dinyatakan LAYAK. Berita Acara BAPL diterbitkan: {bapl_path}."

                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action=log_action_code,
                    status_before=status_awal.value,
                    status_after=status_akhir.value,
                    notes=audit_notes
                )
                return p

            return await asyncio.to_thread(execute_non_tte_approve)

        # 2. Alur TTE Otoritas Akhir (Kepala Bidang)
        else:
            if not input_dto.nip:
                raise ValueError("Ilegal: Kredensial NIP Pejabat wajib dilampirkan untuk proses pembubuhan TTE.")
            if not input_dto.passphrase:
                raise ValueError("Ilegal: Passphrase PIN TTE Pejabat wajib dilampirkan untuk proses pembubuhan TTE.")

            # Generasikan dokumen Surat Keputusan (SK) Pengesahan Site Plan final secara non-blocking di worker thread
            sk_path = await asyncio.to_thread(self.document_generator.generate_final_sk_siteplan, input_dto.id_permohonan)

            # A. State Locking: Transisi berkas ke status 'Proses TTE' dan commit ke DB agar tidak double-click/race condition
            def lock_status_to_proses_tte() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                p.transition_status(SubmissionStatus.PROSES_TTE)
                self.permohonan_repo.save(p, commit=True)
                return p

            await asyncio.to_thread(lock_status_to_proses_tte)

            # B. Call external API BSrE untuk menandatangani dokumen
            try:
                crypto_hash = await self.digital_signature_client.sign_pdf_document(
                    pdf_path=sk_path,
                    certificate_owner_nip=input_dto.nip,
                    passphrase=input_dto.passphrase
                )
            except Exception as e:
                # C. Revert Transaction: Jika penandatanganan gagal, kembalikan status ke MENUNGGU_PERSETUJUAN secara atomik
                logger.error(f"[TTE_TRANSACTION_FAILURE] BSrE signature failed: {str(e)}. Reverting status back to MENUNGGU_PERSETUJUAN.")
                def revert_status_to_menunggu_persetujuan() -> None:
                    self.permohonan_repo.rollback()
                    p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                    if not p:
                        raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                    p.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)
                    self.permohonan_repo.save(p, commit=True)
                
                await asyncio.to_thread(revert_status_to_menunggu_persetujuan)
                raise e

            # D. Commit Final: Pembubuhan sukses, selesaikan transisi ke DISETUJUI secara transaksional
            def commit_final_success() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                if not p:
                    raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")
                signed_url = f"/api/v1/submissions/{p.id_permohonan}/download"
                p.attach_signature(crypto_hash, signed_url)
                p.kabid_signature = input_dto.signature_base64
                
                self.permohonan_repo.save(p, commit=False)
                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action="APPROVE_KABID_TTE",
                    status_before=SubmissionStatus.PROSES_TTE.value,
                    status_after=SubmissionStatus.DISETUJUI.value,
                    notes=f"Izin Site Plan disahkan secara hukum menggunakan TTE Dinas resmi. Kode Hash: {crypto_hash}.",
                    digital_signature_hash=crypto_hash,
                    commit=False
                )
                self.permohonan_repo.commit()
                return p

            return await asyncio.to_thread(commit_final_success)