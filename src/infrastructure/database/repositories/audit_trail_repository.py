"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Audit Trail Repository [audit_trail_repository.py]
============================================================================
Peran: Mengimplementasikan AuditTrailRepositoryPort untuk mencatat riwayat
       mutasi berkas dan ulasan kepatuhan tata ruang dinas.
============================================================================
"""

from typing import Optional
from sqlalchemy.orm import Session
from src.use_cases.submit_permohonan import AuditTrailRepositoryPort
from src.infrastructure.database.models import AuditTrailModel

class AuditTrailRepository(AuditTrailRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        submission_id: str,
        actor_name: str,
        role: str,
        action: str,
        status_before: str,
        status_after: str,
        notes: str,
        digital_signature_hash: Optional[str] = None,
        commit: bool = True
    ) -> None:
        """Penyisipan baris log audit transaksional."""
        new_log = AuditTrailModel(
            submission_id=submission_id,
            actor_name=actor_name,
            role=role,
            action=action,
            status_before=status_before,
            status_after=status_after,
            notes=notes,
            digital_signature_hash=digital_signature_hash
        )
        self.db.add(new_log)
        if commit:
            self.db.commit()
        else:
            self.db.flush()