"""
Incident Model — SQLAlchemy model for disaster and outage incident reports.
Full lifecycle: open → investigating → identified → monitoring → resolved → closed.
Includes RTO/RPO metrics, root cause analysis, and post-mortem data.
"""
from ..sa_models import IncidentReport, RTO_RPO_Metric

__all__ = ["IncidentReport", "RTO_RPO_Metric"]

INCIDENT_EXAMPLE = {
    "id": "INC-2024-001",
    "title": "Production database primary failure — automatic failover initiated",
    "severity": "sev1",
    "status": "resolved",
    "disaster_type": "hardware_failure",
    "affected_systems": ["production_db", "api_server", "web_app"],
    "started_at": "2024-01-15T03:22:00Z",
    "detected_at": "2024-01-15T03:22:11Z",
    "resolved_at": "2024-01-15T03:24:55Z",
    "duration_minutes": 2.92,
    "root_cause": "NVMe SSD failure on primary DB host db-01.us-east-1",
    "resolution_steps": [
        "Automatic failover triggered to replica db-02",
        "DNS updated to point to new primary",
        "Application connection pools recycled",
        "Failed host quarantined for hardware replacement",
    ],
    "users_affected": 0,
    "revenue_impact_usd": 0.0,
}
