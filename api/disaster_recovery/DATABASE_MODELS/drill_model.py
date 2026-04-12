"""
Drill Model — SQLAlchemy model for DR drill records.
Tracks scheduled, running, and completed DR exercises including
scenario type, participants, RTO/RPO targets vs. achieved, and lessons learned.
"""
from ..sa_models import RecoveryDrill, RTO_RPO_Metric

__all__ = ["RecoveryDrill", "RTO_RPO_Metric"]

DRILL_EXAMPLE = {
    "id": "drill-2024-Q1-001",
    "name": "Q1 2024 Database Failover Drill",
    "scenario_type": "hardware_failure",
    "status": "completed",
    "scheduled_at": "2024-01-20T10:00:00Z",
    "started_at": "2024-01-20T10:00:00Z",
    "completed_at": "2024-01-20T10:18:45Z",
    "duration_minutes": 18.75,
    "participants": ["alice@co.com", "bob@co.com", "charlie@co.com"],
    "target_rto_seconds": 300,
    "target_rpo_seconds": 60,
    "achieved_rto_seconds": 187.0,
    "achieved_rpo_seconds": 22.0,
    "passed": True,
    "lessons_learned": "DNS TTL was 300s which delayed routing. Reduced to 60s.",
    "action_items": [
        {"action": "Reduce DNS TTL to 60s", "owner": "alice", "due": "2024-02-01"},
        {"action": "Automate connection pool recycling", "owner": "bob", "due": "2024-02-15"},
    ]
}
