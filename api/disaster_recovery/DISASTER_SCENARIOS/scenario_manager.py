"""Scenario Manager — Routes disaster events to appropriate handlers."""
import logging
from ..enums import DisasterType
logger = logging.getLogger(__name__)

class ScenarioManager:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._handlers = {}
        self._register_defaults()

    def _register_defaults(self):
        from .natural_disaster_handler import NaturalDisasterHandler
        from .cyber_attack_handler import CyberAttackHandler
        from .hardware_failure_handler import HardwareFailureHandler
        from .software_failure_handler import SoftwareFailureHandler
        from .network_outage_handler import NetworkOutageHandler
        from .power_outage_handler import PowerOutageHandler
        from .data_corruption_handler import DataCorruptionHandler
        from .accidental_deletion_handler import AccidentalDeletionHandler
        from .security_breach_handler import SecurityBreachHandler
        from .region_outage_handler import RegionOutageHandler
        from .cascade_failure_handler import CascadeFailureHandler
        self._handlers = {
            DisasterType.NATURAL_DISASTER: NaturalDisasterHandler(self.config),
            DisasterType.CYBER_ATTACK: CyberAttackHandler(self.config),
            DisasterType.HARDWARE_FAILURE: HardwareFailureHandler(self.config),
            DisasterType.SOFTWARE_FAILURE: SoftwareFailureHandler(self.config),
            DisasterType.NETWORK_OUTAGE: NetworkOutageHandler(self.config),
            DisasterType.POWER_OUTAGE: PowerOutageHandler(self.config),
            DisasterType.DATA_CORRUPTION: DataCorruptionHandler(self.config),
            DisasterType.ACCIDENTAL_DELETION: AccidentalDeletionHandler(self.config),
            DisasterType.SECURITY_BREACH: SecurityBreachHandler(self.config),
            DisasterType.REGION_OUTAGE: RegionOutageHandler(self.config),
            DisasterType.CASCADE_FAILURE: CascadeFailureHandler(self.config),
        }

    def handle(self, disaster_type: DisasterType, context: dict) -> dict:
        handler = self._handlers.get(disaster_type)
        if not handler:
            logger.error(f"No handler for disaster type: {disaster_type}")
            return {"error": f"No handler for {disaster_type}"}
        logger.critical(f"DISASTER SCENARIO ACTIVATED: {disaster_type}")
        return handler.handle(context)
