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
    action_type: str                # 'APPROVE' (Setujui) atau 'REJECT' (Tolak)
    notes: str                      # Justifikasi ulasan/revisi
    is_spatially_compliant: bool   # Status kelaikan spasial hasil uji Turf.js/petugas lapangan

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
        
        # 1. Matriks Otorisasi Peran (Security Guard)
        allowed_roles = {
            SubmissionStatus.MENUNGGU_VERIFIKASI: ["ADMIN", "SUPER_ADMIN", "Super Admin"],
            SubmissionStatus.VERIFIKASI_TEKNIS: ["TIM_TEKNIS", "SUPER_ADMIN", "Super Admin"],
            SubmissionStatus.MENUNGGU_PERSETUJUAN: ["KABID_PUPR", "SUPER_ADMIN", "Super Admin"]
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
                raise PermissionError(f"Akses Ditolak: Peran {input_dto.role} tidak memiliki otorisasi untuk tahap verifikasi ini.")

        # ─── SKENARIO A: PENOLAKAN / REVISI BERKAS ───
        if input_dto.action_type == "REJECT":
            def execute_reject() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                p.transition_status(SubmissionStatus.DITOLAK)
                self.permohonan_repo.save(p)
                
                # Catat log kegagalan verifikasi ke sistem audit trail
                self.audit_trail_repo.log_action(
                    submission_id=p.id_permohonan,
                    actor_name=input_dto.actor_name,
                    role=input_dto.role,
                    action="VERIFY_TECHNICAL_REJECTED",
                    status_before=status_awal.value,
                    status_after=SubmissionStatus.DITOLAK.value,
                    notes=f"Berkas dikembalikan untuk revisi. Catatan: {input_dto.notes}"
                )
                return p

            return await asyncio.to_thread(execute_reject)

        # ─── SKENARIO B: PERSETUJUAN / VERIFIKASI POSITIF ───
        
        # 1. Alur Non-TTE (Tingkat Administrasi / Tim Teknis)
        if status_awal != SubmissionStatus.MENUNGGU_PERSETUJUAN:
            def execute_non_tte_approve() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                status_akhir = status_awal
                log_action_code = "FORCE_BYPASS_WARNING"
                audit_notes = input_dto.notes

                if status_awal == SubmissionStatus.MENUNGGU_VERIFIKASI:
                    status_akhir = SubmissionStatus.VERIFIKASI_ADMINISTRASI
                    p.transition_status(SubmissionStatus.VERIFIKASI_ADMINISTRASI)
                    self.permohonan_repo.save(p)
                    log_action_code = "VERIFY_ADMIN_APPROVED"
                    audit_notes = f"Ulasan dokumen kelengkapan administrasi disetujui. Catatan: {input_dto.notes}"

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
                    self.permohonan_repo.db.rollback()
                    p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                    p.transition_status(SubmissionStatus.MENUNGGU_PERSETUJUAN)
                    self.permohonan_repo.save(p, commit=True)
                
                await asyncio.to_thread(revert_status_to_menunggu_persetujuan)
                raise e

            # D. Commit Final: Pembubuhan sukses, selesaikan transisi ke DISETUJUI secara transaksional
            def commit_final_success() -> Permohonan:
                p = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
                signed_url = f"/api/v1/submissions/{p.id_permohonan}/download"
                p.attach_signature(crypto_hash, signed_url)
                
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
                self.permohonan_repo.db.commit()
                return p

            return await asyncio.to_thread(commit_final_success)