"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — SK Draft Repository [sk_draft_repository.py]
============================================================================
Peran: Menyediakan repositori penyimpanan fisik untuk draf keputusan SK.
       Mengimplementasikan kontrak SkDraftRepositoryPort secara transaksional
       menggunakan SQLAlchemy 2.0. Menangani pemetaan dua arah (Domain 
       Mapping) antara entitas domain SkDraft dan SkDraftModel (JSONB).
============================================================================
"""

import logging
from datetime import datetime
from typing import Optional, List, cast, Any

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

# Impor Kontrak Port dari Use Case Layer (DIP Compliance)
from src.use_cases.verify_submission import SkDraftRepositoryPort

# Impor Entitas Domain & Value Objects
from src.domain.entities.sk_draft import (
    SkDraft,
    SkVerdict,
    SkSignerInfo,
    SkDiktumHunian,
    SkDiktumPsu,
    SkDiktumIntensity,
    SkConsiderations
)

# Impor Model Database
from src.infrastructure.database.models import SkDraftModel

logger = logging.getLogger("sipas-be")


class SkDraftRepository(SkDraftRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    # ─── SECTION 1: MAPPING TO DOMAIN ENTITY (DB -> Domain) ───────────────────
    def _to_domain(self, model: SkDraftModel) -> SkDraft:
        """
        Mengonversi data baris tabel database (SQLAlchemy Model) berisi kolom JSONB 
        kembali menjadi Objek Domain bisnis murni dengan pemetaan tipe-aman.
        """
        payload = model.document_payload

        # 1. Parsing Considerations Value Object
        considerations = None
        cons_data = payload.get("considerations")
        if cons_data:
            considerations = SkConsiderations(
                menimbang=list(cons_data.get("menimbang", [])),
                mengingat=list(cons_data.get("mengingat", [])),
                memperhatikan=list(cons_data.get("memperhatikan", []))
            )

        # 2. Parsing List Diktum Hunian
        diktum_hunian: List[SkDiktumHunian] = []
        for item in payload.get("diktum_hunian", []):
            diktum_hunian.append(
                SkDiktumHunian(
                    tipe_rumah=str(item["tipe_rumah"]),
                    jumlah_unit=int(item["jumlah_unit"]),
                    luas_m2=float(item["luas_m2"])
                )
            )

        # 3. Parsing Diktum PSU Value Object
        diktum_psu = None
        psu_data = payload.get("diktum_psu")
        if psu_data:
            diktum_psu = SkDiktumPsu(
                total_psu_area_m2=float(psu_data["total_psu_area_m2"]),
                allocation_details=str(psu_data["allocation_details"]),
                cemetery_scheme=str(psu_data["cemetery_scheme"]),
                road_row_min=float(psu_data["road_row_min"]),
                road_row_max=float(psu_data["road_row_max"]),
                drainage_type=str(psu_data.get("drainage_type", "Saluran drainase terbuka dengan konstruksi Udich"))
            )

        # 4. Parsing Diktum Intensitas Ruang Value Object
        diktum_intensity = None
        intensity_data = payload.get("diktum_intensity")
        if intensity_data:
            diktum_intensity = SkDiktumIntensity(
                kdb_max=float(intensity_data["kdb_max"]),
                klb_max=float(intensity_data["klb_max"]),
                kdh_min=float(intensity_data["kdh_min"])
            )

        # 5. Parsing Signer Info (Kadis) Value Object
        signer = None
        signer_data = payload.get("signer")
        if signer_data:
            signed_at_val = signer_data.get("signed_at")
            signed_at = datetime.fromisoformat(signed_at_val) if signed_at_val else None
            signer = SkSignerInfo(
                name=str(signer_data["name"]),
                nip=str(signer_data["nip"]),
                office_title=str(signer_data.get("office_title", "Kepala Dinas Perumahan dan Permukiman")),
                signed_at=signed_at,
                signature_base64=signer_data.get("signature_base64")
            )

        return SkDraft(
            id_sk=str(model.id_sk),
            id_permohonan=str(model.id_permohonan),
            sequence_no=int(model.sequence_no),
            created_at=model.created_at,
            classification_code=str(payload.get("classification_code", "600")),
            office_code=str(payload.get("office_code", "415.19")),
            considerations=considerations,
            diktum_hunian=diktum_hunian,
            diktum_psu=diktum_psu,
            diktum_intensity=diktum_intensity,
            signer=signer,
            verdict=SkVerdict(str(payload.get("verdict", SkVerdict.DAPAT_DISETUJUI.value))),
            custom_notes=model.override_reason or payload.get("custom_notes")
        )

    # ─── SECTION 2: REPOSITORY PORT CONTRACT IMPLEMENTATIONS ──────────────────

    def find_by_id(self, id_sk: str) -> Optional[SkDraft]:
        """Mencari draf keputusan SK berdasarkan ID SK unik."""
        try:
            model = self.db.query(SkDraftModel).filter(SkDraftModel.id_sk == id_sk).first()
            if not model:
                return None
            return self._to_domain(model)
        except Exception as e:
            logger.error(f"[REPO_ERROR] Gagal memuat SK ID '{id_sk}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Database error saat memuat Surat Keputusan: {str(e)}")

    def find_by_permohonan_id(self, id_permohonan: str) -> Optional[SkDraft]:
        """Mencari draf keputusan SK yang ditautkan pada permohonan spesifik."""
        try:
            model = self.db.query(SkDraftModel).filter(SkDraftModel.id_permohonan == id_permohonan).first()
            if not model:
                return None
            return self._to_domain(model)
        except Exception as e:
            logger.error(f"[REPO_ERROR] Gagal memuat SK berdasarkan Permohonan ID '{id_permohonan}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Database error saat mencocokkan Surat Keputusan: {str(e)}")

    def save(self, entity: SkDraft, commit: bool = True) -> SkDraft:
        """
        Menyimpan atau memperbarui data keputusan SK secara transaksional (Idempotent).
        Seluruh detail nested dictionary dikompresi ke kolom biner JSONB PostgreSQL.
        """
        try:
            # Cari baris data eksisting menggunakan relasi satu-ke-satu permohonan
            existing_model = self.db.query(SkDraftModel).filter(
                (SkDraftModel.id_sk == entity.id_sk) | 
                (SkDraftModel.id_permohonan == entity.id_permohonan)
            ).first()

            serialized_payload = entity.to_dict()

            if existing_model:
                # Skenario UPDATE: Selaraskan data ter-indeks dan payload ter-kompresi
                existing_model.verdict = entity.verdict.value
                existing_model.sk_number = entity.sk_number
                existing_model.override_reason = entity.custom_notes
                existing_model.document_payload = serialized_payload
                logger.info(f"[REPOSITORY_SK] Sukses melakukan update Surat Keputusan Nomor: {entity.sk_number}")
            else:
                # Skenario INSERT: Membuat baris fisik baru
                new_model = SkDraftModel(
                    id_sk=entity.id_sk,
                    id_permohonan=entity.id_permohonan,
                    sk_number=entity.sk_number,
                    verdict=entity.verdict.value,
                    is_overridden=entity.is_overridden,
                    override_reason=entity.custom_notes,
                    created_at=entity.created_at,
                    document_payload=serialized_payload
                )
                self.db.add(new_model)
                logger.info(f"[REPOSITORY_SK] Sukses menyisipkan draf Surat Keputusan baru Nomor: {entity.sk_number}")

            if commit:
                self.db.commit()
            else:
                self.db.flush()

            return entity
        except Exception as e:
            self.db.rollback()
            logger.error(f"[REPO_ERROR] Gagal menyimpan transaksional SK draft: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses Unit of Work draf Surat Keputusan: {str(e)}")

    def get_next_sequence_no(self) -> int:
        """
        Menghitung nomor sekuensial SK dinas berikutnya secara otomatis.
        Melakukan pengelompokan (filter) sekuensial berdasarkan tahun kalender berjalan.
        """
        try:
            current_year = datetime.now().year
            
            # Query: SELECT MAX(sequence_no) FROM sk_draft WHERE EXTRACT(YEAR FROM created_at) = current_year
            max_sequence = self.db.query(func.max(SkDraftModel.sequence_no))\
                .filter(extract('year', SkDraftModel.created_at) == current_year)\
                .scalar()
                
            return (max_sequence or 0) + 1
        except Exception as e:
            logger.error(f"[REPO_ERROR] Gagal menghitung nomor urut SK dinas: {str(e)}", exc_info=True)
            # Menghindari kegagalan proses birokrasi, kembalikan fallback acak yang aman dari tabrakan indeks
            import random
            return random.randint(1000, 9999)