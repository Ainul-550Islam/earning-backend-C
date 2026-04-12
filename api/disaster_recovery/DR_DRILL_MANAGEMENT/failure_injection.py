"""Failure Injection — Programmatic failure injection for testing."""
import logging
logger = logging.getLogger(__name__)

class FailureInjector:
    def __init__(self, target: str, dry_run: bool = True):
        self.target = target
        self.dry_run = dry_run

    def inject(self, failure_type: str, config: dict = None) -> dict:
        logger.warning(f"FAILURE INJECTION: {failure_type} on {self.target} (dry_run={self.dry_run})")
        injectors = {
            "db_connection_drop": self._drop_db_connections,
            "service_crash": self._crash_service,
            "disk_full": self._fill_disk,
            "network_split": self._network_split,
        }
        fn = injectors.get(failure_type)
        if not fn:
            return {"error": f"Unknown failure type: {failure_type}"}
        return fn(config or {})

    def _drop_db_connections(self, config: dict) -> dict:
        return {"injected": "db_connection_drop", "dry_run": self.dry_run}

    def _crash_service(self, config: dict) -> dict:
        return {"injected": "service_crash", "target": self.target, "dry_run": self.dry_run}

    def _fill_disk(self, config: dict) -> dict:
        return {"injected": "disk_full", "dry_run": self.dry_run}

    def _network_split(self, config: dict) -> dict:
        return {"injected": "network_split", "dry_run": self.dry_run}
