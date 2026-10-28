"""
api/audit_logs/payout_integration.py
======================================
Audit log bridge for api.payout_queue.

HOW IT WORKS
------------
receivers._write_audit_log() calls log_payout_event() from each signal
receiver when PAYOUT_AUDIT_LOG_ENABLED=True (default True).

Events written:
  BATCH_COMPLETED         — batch completed or partially completed
  BATCH_FAILED            — batch failed (all items failed)
  ITEM_PERMANENTLY_FAILED — item ran out of retries

AUDIT MODEL ASSUMPTIONS
-----------------------
Assumes your api.audit_logs app has a model roughly like:

    class AuditLog(models.Model):
        event_type  = models.CharField(max_length=100)
        actor_id    = models.IntegerField(null=True, blank=True)
        module      = models.CharField(max_length=50)
        payload     = models.JSONField(default=dict)
        severity    = models.CharField(max_length=10, default="INFO")
        created_at  = models.DateTimeField(auto_now_add=True)

Adjust field names in log_payout_event() to match your actual model.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Map payout event types to severity levels
_SEVERITY_MAP: dict[str, str] = {
    "BATCH_COMPLETED":            "INFO",
    "BATCH_FAILED":               "ERROR",
    "ITEM_PERMANENTLY_FAILED":    "WARNING",
    "PRIORITY_ASSIGNED":          "INFO",
}


def log_payout_event(
    *,
    event_type: str,
    actor_id: Any,
    payload: dict,
) -> None:
    """
    Write a payout lifecycle event to the central audit trail.

    Called by: api.payout_queue.receivers._write_audit_log()

    Args:
        event_type: Short string identifying the event.
                    Examples: "BATCH_COMPLETED", "BATCH_FAILED",
                              "ITEM_PERMANENTLY_FAILED", "PRIORITY_ASSIGNED"
        actor_id:   User PK who triggered the event (may be None for system actions).
        payload:    Dict of event details (batch_id, status, amounts, etc.).

    Raises:
        Nothing — all errors are caught and logged at ERROR level.
    """
    if not event_type:
        logger.warning("log_payout_event: event_type is empty — skipping.")
        return

    severity = _SEVERITY_MAP.get(event_type, "INFO")
    full_event_type = f"PAYOUT_{event_type}"

    try:
        from api.audit_logs.models import AuditLog
        AuditLog.objects.create(
            event_type=full_event_type,
            actor_id=actor_id,
            module="payout_queue",
            payload=payload if isinstance(payload, dict) else {},
            severity=severity,
        )
        logger.debug(
            "log_payout_event: wrote %s to audit_logs (actor=%s)",
            full_event_type, actor_id,
        )
    except ImportError:
        # api.audit_logs not installed — log locally and move on
        logger.info(
            "log_payout_event: audit_logs not available. "
            "event=%s actor=%s payload_keys=%s",
            full_event_type, actor_id, list(payload.keys()) if payload else [],
        )
    except Exception as exc:
        logger.error(
            "log_payout_event: failed to write %s to audit_logs: %s",
            full_event_type, exc,
        )


def get_payout_audit_trail(batch_id: Any) -> list[dict]:
    """
    Retrieve all audit log entries for a specific payout batch.

    Useful for admin views and compliance reports.

    Returns:
        List of dicts with keys: event_type, actor_id, severity,
        created_at, payload.
        Empty list if audit_logs app is not available.
    """
    if batch_id is None:
        return []
    try:
        from api.audit_logs.models import AuditLog
        logs = AuditLog.objects.filter(
            module="payout_queue",
            payload__batch_id=str(batch_id),
        ).order_by("-created_at").values(
            "event_type", "actor_id", "severity", "created_at", "payload"
        )
        return [
            {
                "event_type": log["event_type"],
                "actor_id":   log["actor_id"],
                "severity":   log["severity"],
                "created_at": log["created_at"].isoformat(),
                "payload":    log["payload"],
            }
            for log in logs
        ]
    except Exception as exc:
        logger.warning("get_payout_audit_trail: error: %s", exc)
        return []
