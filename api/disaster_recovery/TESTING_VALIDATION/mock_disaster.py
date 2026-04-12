"""
Mock Disaster — Simulates disaster scenarios in a safe test environment.
"""
import pytest
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

logger = logging.getLogger(__name__)


class MockDisasterSimulator:
    """
    Simulates various disaster scenarios safely without impacting real systems.
    Used for testing disaster response procedures and runbooks.
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.events_fired = []

    def simulate_database_failure(self, database: str) -> dict:
        """Simulate a primary database failure."""
        event = {
            "scenario": "database_failure",
            "database": database,
            "simulated_at": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
        }
        self.events_fired.append(event)
        logger.warning(f"[MOCK DISASTER] Database failure: {database}")
        return {**event, "success": True,
                "expected_response": "Trigger failover to replica within RTO"}

    def simulate_network_partition(self, segment: str) -> dict:
        """Simulate network partition between segments."""
        event = {
            "scenario": "network_partition",
            "segment": segment,
            "simulated_at": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
        }
        self.events_fired.append(event)
        return {**event, "success": True}

    def simulate_disk_failure(self, volume: str) -> dict:
        """Simulate disk/volume failure."""
        event = {
            "scenario": "disk_failure",
            "volume": volume,
            "simulated_at": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
        }
        self.events_fired.append(event)
        return {**event, "success": True}

    def simulate_region_outage(self, region: str) -> dict:
        """Simulate a full cloud region outage."""
        event = {
            "scenario": "region_outage",
            "region": region,
            "simulated_at": datetime.utcnow().isoformat(),
            "affected_services": ["database", "api", "cache", "storage"],
            "dry_run": self.dry_run,
        }
        self.events_fired.append(event)
        logger.critical(f"[MOCK DISASTER] Region outage: {region}")
        return {**event, "success": True}

    def get_event_log(self) -> list:
        return self.events_fired

    def reset(self):
        self.events_fired = []


class TestMockDisasterScenarios:
    """Tests using mock disaster simulator."""

    def setup_method(self):
        self.simulator = MockDisasterSimulator(dry_run=True)

    def test_database_failure_simulation(self):
        result = self.simulator.simulate_database_failure("primary-db")
        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["scenario"] == "database_failure"
        assert len(self.simulator.get_event_log()) == 1

    def test_region_outage_simulation(self):
        result = self.simulator.simulate_region_outage("us-east-1")
        assert result["success"] is True
        assert "affected_services" in result
        assert len(result["affected_services"]) > 0

    def test_multiple_events_logged(self):
        self.simulator.simulate_database_failure("db1")
        self.simulator.simulate_network_partition("zone-a")
        self.simulator.simulate_disk_failure("vol-123")
        assert len(self.simulator.get_event_log()) == 3

    def test_reset_clears_log(self):
        self.simulator.simulate_database_failure("db1")
        self.simulator.reset()
        assert len(self.simulator.get_event_log()) == 0

    def test_scenario_handler_integration(self):
        from ..DISASTER_SCENARIOS.scenario_manager import ScenarioManager
        from ..enums import DisasterType
        mgr = ScenarioManager({})
        result = mgr.handle(
            DisasterType.DATA_CORRUPTION,
            {"database": "test_db", "drill_mode": True}
        )
        assert "steps" in result
        assert len(result["steps"]) > 0
        assert result["disaster_type"] == "data_corruption"
