"""
Audit Model — SQLAlchemy model for immutable DR system audit trail.
Every action (backup, restore, failover, config change) is logged
with actor, timestamp, old/new values, and IP address.
Required for GDPR, HIPAA, SOC2, ISO27001 compliance.
"""
from ..sa_models import DR_AuditTrail

__all__ = ["DR_AuditTrail"]

AUDIT_EXAMPLES = [
    {
        "actor_id": "user@company.com",
        "actor_type": "user",
        "action": "backup_policy.create",
        "resource_type": "backup_policy",
        "resource_id": "policy-123",
        "ip_address": "10.0.1.50",
        "result": "success",
        "new_values": {"name": "Production DB Daily", "retention_days": 30},
    },
    {
        "actor_id": "auto",
        "actor_type": "system",
        "action": "failover.trigger",
        "resource_type": "failover_event",
        "resource_id": "failover-001",
        "result": "success",
        "new_values": {"primary": "db-01", "secondary": "db-02", "reason": "health check failed"},
    },
    {
        "actor_id": "admin@company.com",
        "actor_type": "user",
        "action": "restore.approve",
        "resource_type": "restore_request",
        "resource_id": "restore-001",
        "ip_address": "10.0.1.20",
        "result": "success",
    },
]
