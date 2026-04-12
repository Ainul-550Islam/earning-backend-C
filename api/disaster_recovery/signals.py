"""Signals — Event-driven hooks for DR system events."""
import logging
from typing import Callable, Dict, List
logger = logging.getLogger(__name__)

_listeners: Dict[str, List[Callable]] = {}

def on(event: str):
    """Decorator to register an event listener."""
    def decorator(fn: Callable):
        _listeners.setdefault(event, []).append(fn)
        return fn
    return decorator

def emit(event: str, **kwargs):
    """Emit an event to all registered listeners."""
    listeners = _listeners.get(event, [])
    for fn in listeners:
        try:
            fn(**kwargs)
        except Exception as e:
            logger.error(f"Signal listener error [{event}]: {e}")

# Pre-defined signal events
BACKUP_STARTED = "backup.started"
BACKUP_COMPLETED = "backup.completed"
BACKUP_FAILED = "backup.failed"
RESTORE_STARTED = "restore.started"
RESTORE_COMPLETED = "restore.completed"
FAILOVER_TRIGGERED = "failover.triggered"
FAILOVER_COMPLETED = "failover.completed"
INCIDENT_CREATED = "incident.created"
INCIDENT_RESOLVED = "incident.resolved"
HEALTH_DEGRADED = "health.degraded"
SLA_BREACHED = "sla.breached"
DRILL_COMPLETED = "drill.completed"
