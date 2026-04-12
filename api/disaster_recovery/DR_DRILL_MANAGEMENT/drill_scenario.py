"""Drill Scenario — Defines pre-built DR drill scenarios."""
import logging
logger = logging.getLogger(__name__)

SCENARIOS = {
    "database_failover": {
        "name": "Database Primary Failover",
        "description": "Simulate primary DB failure and verify replica promotion",
        "steps": ["Stop primary DB", "Verify replica detected failure", "Promote replica",
                  "Update connection strings", "Verify app connectivity", "Measure RTO"],
        "target_rto_seconds": 300,
        "target_rpo_seconds": 60,
    },
    "region_failover": {
        "name": "Full Region Failover",
        "description": "Simulate complete AWS region outage",
        "steps": ["Simulate region unavailability", "Activate DR region", "Restore all services",
                  "Verify data integrity", "Update DNS", "Measure recovery time"],
        "target_rto_seconds": 3600,
        "target_rpo_seconds": 900,
    },
    "backup_restore": {
        "name": "Backup Restore Validation",
        "description": "Verify backup can be successfully restored",
        "steps": ["Select latest backup", "Restore to test environment",
                  "Verify data integrity", "Measure restore time"],
        "target_rto_seconds": 1800,
        "target_rpo_seconds": 300,
    },
    "data_corruption": {
        "name": "Data Corruption Recovery",
        "description": "Simulate and recover from data corruption",
        "steps": ["Introduce test corruption", "Detect via monitoring", "PITR restore",
                  "Verify data correctness"],
        "target_rto_seconds": 1800,
        "target_rpo_seconds": 300,
    },
}

class DrillScenario:
    def get(self, scenario_key: str) -> dict:
        return SCENARIOS.get(scenario_key, {})

    def list_all(self) -> list:
        return [{"key": k, **v} for k, v in SCENARIOS.items()]
