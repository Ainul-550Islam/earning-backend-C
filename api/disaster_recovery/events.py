"""Events — Domain events for DR system (CQRS pattern support)."""
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BackupCompletedEvent(DomainEvent):
    event_type: str = "backup.completed"
    backup_job_id: str = ""
    size_bytes: int = 0
    duration_seconds: float = 0.0

@dataclass
class FailoverTriggeredEvent(DomainEvent):
    event_type: str = "failover.triggered"
    primary_node: str = ""
    secondary_node: str = ""
    reason: str = ""

@dataclass
class IncidentCreatedEvent(DomainEvent):
    event_type: str = "incident.created"
    incident_id: str = ""
    severity: str = ""
    title: str = ""

class EventBus:
    """Simple in-process event bus."""
    _handlers: Dict[str, list] = {}

    @classmethod
    def subscribe(cls, event_type: str, handler):
        cls._handlers.setdefault(event_type, []).append(handler)

    @classmethod
    def publish(cls, event: DomainEvent):
        for handler in cls._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Event handler error: {e}")
