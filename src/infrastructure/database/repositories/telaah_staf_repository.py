# --- FILE: src/infrastructure/database/repositories/telaah_staf_repository.py ---
"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Telaah Staf Repository [telaah_staf_repository.py]
============================================================================
Peran: Mengimplementasikan operasi I/O database untuk menyimpan payload JSONB
       ke tabel master telaah_staf secara transaksional menggunakan SQLAlchemy 2.0.
       Melakukan pemetaan bolak-balik (Mapping) antara objek Domain dan DB Model.
============================================================================
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

# Impor Entitas Domain Murni & Value Objects
from src.domain.entities.telaah_staf import (
    TelaahStaf,
    TelaahStafVerdict,
    VerifierInfo,
    AdminChecklistItem,
    TechnicalMatrixItem
)

# Impor Model Fisik Database (SQLAlchemy 2.0 Mapping)
# Catatan: Pastikan TelaahStafModel telah dideklarasikan di models.py Anda
from src.infrastructure.database.models import Base

logger = logging.getLogger("sipas-be")

# ─── SECTION: PORT ABSTRAKSI (INTERFACE) ──────────────────────────────────
# Didefinisikan di sini agar mematuhi Dependency Inversion Principle (DIP)

class TelaahStafRepositoryPort(ABC):
    """Abstraksi Kontrak Repositori Telaah Staf di tingkat Domain/Use Case."""
    
    @abstractmethod
    def find_by_id(self, id_telaah: str) -> Optional[TelaahStaf]:
        pass

    @abstractmethod
    def find_by_permohonan_id(self, id_permohonan: str) -> Optional[TelaahStaf]:
        pass

    @abstractmethod
    def save(self, entity: TelaahStaf, commit: bool = True) -> TelaahStaf:
        pass

    @abstractmethod
    def delete(self, id_telaah: str, commit: bool = True) -> bool:
        pass


# ─── SECTION: REPOSITORI ADAPTER IMPLEMENTASI (POSTGRESQL) ──────────────────

class TelaahStafRepository(TelaahStafRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    # ─── MAPPING HELPER 1: FROM DATABASE MODEL TO DOMAIN ENTITY ───────────────
    def _to_domain(self, model: Any) -> TelaahStaf:
        """
        Mengonversi baris tabel database (SQLAlchemy Model) berisi kolom JSONB
        kembali menjadi Objek Domain bisnis murni.
        """
        payload: Dict[str, Any] = model.document_payload

        # 1. Parsing Verifier Info
        verifier_data = payload["verifier"]
        verifier = VerifierInfo(
            name=str(verifier_data["name"]),
            nip=str(verifier_data["nip"]),
            timestamp=datetime.fromisoformat(verifier_data["timestamp"]),
            signature_base64=verifier_data.get("signature_base64")
        )

        # 2. Parsing Endorser Info (Jika ada)
        endorser = None
        if payload.get("endorser"):
            endorser_data = payload["endorser"]
            endorser = VerifierInfo(
                name=str(endorser_data["name"]),
                nip=str(endorser_data["nip"]),
                timestamp=datetime.fromisoformat(endorser_data["timestamp"])
            )

        # 3. Parsing Checklist Administrasi
        admin_checklist: List[AdminChecklistItem] = []
        for item in payload.get("administrative_checklist", []):
            admin_checklist.append(
                AdminChecklistItem(
                    doc_key=str(item["doc_key"]),
                    doc_label=str(item["doc_label"]),
                    file_name=str(item["file_name"]),
                    status=str(item["status"]),
                    notes=item.get("notes")
                )
            )

        # 4. Parsing 13 Matriks Teknis
        technical_matrix: List[TechnicalMatrixItem] = []
        for item in payload.get("technical_matrix", []):
            technical_matrix.append(
                TechnicalMatrixItem(
                    code=str(item["code"]),
                    label=str(item["label"]),
                    unit=str(item["unit"]),
                    proposed_val=str(item["proposed_val"]),
                    bylaw_val=str(item["bylaw_val"]),
                    verified_val=str(item["verified_val"]),
                    status=str(item["status"]),
                    notes=item.get("notes")
                )
            )

        # 5. Konstruksi dan kembalikan Objek Domain utama
        return TelaahStaf(
            id_telaah=str(model.id_telaah),
            id_permohonan=str(model.id_permohonan),
            verdict=TelaahStafVerdict(str(model.verdict)),
            verifier=verifier,
            administrative_checklist=admin_checklist,
            technical_matrix=technical_matrix,
            created_at=model.created_at,
            endorser=endorser,
            is_overridden=bool(model.is_overridden),
            override_reason=model.override_reason,
            admin_verifier_name=payload.get("admin_verifier_name"),
            admin_verifier_nip=payload.get("admin_verifier_nip"),
            admin_verified_at=payload.get("admin_verified_at")
        )

    # ─── MAPPING HELPER 2: FROM DOMAIN ENTITY TO DATABASE MODEL ───────────────
    def _to_payload(self, entity: TelaahStaf) -> Dict[str, Any]:
        """
        Menserialisasikan data Domain menjadi struktur dict nested JSON
        untuk disimpan di kolom biner JSONB PostgreSQL.
        """
        return {
            "id_telaah": entity.id_telaah,
            "id_permohonan": entity.id_permohonan,
            "verdict": entity.verdict.value,
            "created_at": entity.created_at.isoformat(),
            "verifier": {
                "name": entity.verifier.name,
                "nip": entity.verifier.nip,
                "timestamp": entity.verifier.timestamp.isoformat(),
                "signature_base64": getattr(entity.verifier, "signature_base64", None)
            },
            "endorser": {
                "name": entity.endorser.name,
                "nip": entity.endorser.nip,
                "timestamp": entity.endorser.timestamp.isoformat()
            } if entity.endorser else None,
            "administrative_checklist": [
                {
                    "doc_key": item.doc_key,
                    "doc_label": item.doc_label,
                    "file_name": item.file_name,
                    "status": item.status,
                    "notes": item.notes
                } for item in entity.administrative_checklist
            ],
            "technical_matrix": [
                {
                    "code": item.code,
                    "label": item.label,
                    "unit": item.unit,
                    "proposed_val": item.proposed_val,
                    "bylaw_val": item.bylaw_val,
                    "verified_val": item.verified_val,
                    "status": item.status,
                    "notes": item.notes
                } for item in entity.technical_matrix
            ],
            "is_overridden": entity.is_overridden,
            "override_reason": entity.override_reason,
            "admin_verifier_name": entity.admin_verifier_name,
            "admin_verifier_nip": entity.admin_verifier_nip,
            "admin_verified_at": entity.admin_verified_at
        }

    # ─── REPOSITORY ACTIONS ───────────────────────────────────────────────────

    def find_by_id(self, id_telaah: str) -> Optional[TelaahStaf]:
        """Menemukan draf dokumen Telaah Staf berdasarkan ID Dokumen."""
        from src.infrastructure.database.models import TelaahStafModel
        
        try:
            model = self.db.query(TelaahStafModel).filter(
                TelaahStafModel.id_telaah == id_telaah
            ).first()
            if not model:
                return None
            return self._to_domain(model)
        except Exception as e:
            logger.error(f"[REPOSITORI_ERR] Gagal mengambil data ID '{id_telaah}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal mengambil dokumen dari basis data: {str(e)}")

    def find_by_permohonan_id(self, id_permohonan: str) -> Optional[TelaahStaf]:
        """Menemukan dokumen Telaah Staf terasosiasi dengan ID permohonan."""
        from src.infrastructure.database.models import TelaahStafModel
        
        try:
            model = self.db.query(TelaahStafModel).filter(
                TelaahStafModel.id_permohonan == id_permohonan
            ).first()
            if not model:
                return None
            return self._to_domain(model)
        except Exception as e:
            logger.error(f"[REPOSITORI_ERR] Gagal mengambil permohonan ID '{id_permohonan}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal mengambil dokumen dari basis data: {str(e)}")

    def save(self, entity: TelaahStaf, commit: bool = True) -> TelaahStaf:
        """Menyimpan (Insert) atau Memperbarui (Update) data transaksional."""
        from src.infrastructure.database.models import TelaahStafModel
        
        try:
            # 1. Cari apakah baris data lama sudah terdaftar di database
            existing_model = self.db.query(TelaahStafModel).filter(
                TelaahStafModel.id_telaah == entity.id_telaah
            ).first()

            serialized_payload = self._to_payload(entity)

            if existing_model:
                # Skenario UPDATE: Sinkronkan perubahan kolom ter-indeks & payload JSONB
                existing_model.verdict = entity.verdict.value
                existing_model.is_overridden = entity.is_overridden
                existing_model.override_reason = entity.override_reason
                existing_model.document_payload = serialized_payload
                logger.info(f"[REPOSITORI] Berhasil memperbarui dokumen Telaah Staf ID: {entity.id_telaah}")
            else:
                # Skenario INSERT: Membuat baris fisik baru
                new_model = TelaahStafModel(
                    id_telaah=entity.id_telaah,
                    id_permohonan=entity.id_permohonan,
                    verdict=entity.verdict.value,
                    is_overridden=entity.is_overridden,
                    override_reason=entity.override_reason,
                    created_at=entity.created_at,
                    document_payload=serialized_payload
                )
                self.db.add(new_model)
                logger.info(f"[REPOSITORI] Berhasil menyisipkan baris Telaah Staf baru: {entity.id_telaah}")

            # 2. Transaksi Unit-of-Work
            if commit:
                self.db.commit()
            else:
                self.db.flush()

            return entity
        except Exception as e:
            self.db.rollback()
            logger.error(f"[REPOSITORI_ERR] Gagal melakukan penyimpanan transaksional: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses transaksi penyimpanan database: {str(e)}")

    def delete(self, id_telaah: str, commit: bool = True) -> bool:
        """Menghapus data dokumen dari tabel database secara permanen."""
        from src.infrastructure.database.models import TelaahStafModel
        
        try:
            model = self.db.query(TelaahStafModel).filter(
                TelaahStafModel.id_telaah == id_telaah
            ).first()
            if not model:
                return False

            self.db.delete(model)
            if commit:
                self.db.commit()
            else:
                self.db.flush()

            logger.info(f"[REPOSITORI] Berhasil menghapus permanen dokumen ID: {id_telaah}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"[REPOSITORI_ERR] Gagal menghapus baris data ID '{id_telaah}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal memproses penghapusan database: {str(e)}")