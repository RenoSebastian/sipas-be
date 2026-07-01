from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BpnValidationPort(ABC):
    @abstractmethod
    def validate_land_boundary(self, polygon_coords: List[Any]) -> bool:
        """Validate land boundary and certificate numbers via ATR/BPN."""
        pass

class OssSyncPort(ABC):
    @abstractmethod
    def sync_licensing_status(self, submission_id: str, status: str) -> bool:
        """Synchronize licensing status and update OSS RBA National system."""
        pass

class SimtaruSyncPort(ABC):
    @abstractmethod
    def check_zoning_compliance(self, polygon_coords: List[Any]) -> Dict[str, Any]:
        """Verify layout and coordinates compliance with Simtaru zoning database."""
        pass
