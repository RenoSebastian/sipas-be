import logging
from typing import List, Dict, Any
from src.use_cases.ports.integration_ports import BpnValidationPort, OssSyncPort, SimtaruSyncPort

logger = logging.getLogger("sipas-be")

class MockBpnAdapter(BpnValidationPort):
    def validate_land_boundary(self, polygon_coords: List[Any]) -> bool:
        logger.info(f"[MOCK_BPN] Validating land boundary coordinates: {polygon_coords}")
        return True

class MockOssAdapter(OssSyncPort):
    def sync_licensing_status(self, submission_id: str, status: str) -> bool:
        logger.info(f"[MOCK_OSS] Syncing licensing status for submission {submission_id} as: {status}")
        return True

class MockSimtaruAdapter(SimtaruSyncPort):
    def check_zoning_compliance(self, polygon_coords: List[Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK_SIMTARU] Checking zoning compliance for coordinate bounds.")
        return {
            "compliant": True,
            "zoning_type": "PERUMAHAN",
            "notes": "Sesuai dengan Rencana Tata Ruang Wilayah (RTRW)."
        }
