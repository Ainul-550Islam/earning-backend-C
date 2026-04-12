"""
Failover Model — SQLAlchemy model for failover event records.
Documents every failover: who triggered it, why, what happened,
and the actual RTO/RPO achieved vs. target.
"""
from ..sa_models import FailoverEvent, ReplicationLag

__all__ = ["FailoverEvent", "ReplicationLag"]

FAILOVER_EVENT_EXAMPLE = {
    "id": "failover-001",
    "failover_type": "automatic",
    "status": "completed",
    "primary_node": "db-primary-us-east-1a",
    "secondary_node": "db-replica-us-east-1b",
    "triggered_by": "auto",
    "trigger_reason": "Health check failed: 3 consecutive timeouts",
    "initiated_at": "2024-01-15T03:22:11Z",
    "completed_at": "2024-01-15T03:24:55Z",
    "duration_seconds": 164.0,
    "rto_achieved_seconds": 164.0,
    "data_loss_seconds": 8.2,
    "timeline": [
        {"time": "03:22:11", "event": "Health check failure #3 detected"},
        {"time": "03:22:12", "event": "Automatic failover triggered"},
        {"time": "03:22:45", "event": "Replica promotion started"},
        {"time": "03:23:15", "event": "DNS updated to new primary"},
        {"time": "03:24:55", "event": "Failover completed — service restored"},
    ]
}
