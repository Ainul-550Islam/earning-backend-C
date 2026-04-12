"""
Alert Model — SQLAlchemy model for system alerts.
Tracks fired alerts, their severity, acknowledgment, and resolution.
Links to incidents when alerts escalate to full incident reports.
"""
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid

from ..sa_models import Base
from ..enums import AlertSeverity


class Alert(Base):
    """
    Persisted alert record — created when an alert rule fires
    and persists until acknowledged and resolved.
    """
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_name = Column(String(200), nullable=False, index=True)
    metric = Column(String(200), nullable=False)
    value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    severity = Column(SAEnum(AlertSeverity), nullable=False)
    message = Column(Text, nullable=False)
    labels = Column(JSON, default=dict)
    fired_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(200))
    resolved_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    notification_sent = Column(Boolean, default=False)
    incident_id = Column(String(36))       # linked incident if escalated
    suppressed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def acknowledge(self, user_id: str):
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = user_id

    def resolve(self):
        self.resolved_at = datetime.utcnow()
        self.is_active = False

    def to_dict(self) -> dict:
        return {
            "id": self.id, "rule_name": self.rule_name, "metric": self.metric,
            "value": self.value, "threshold": self.threshold,
            "severity": self.severity.value if self.severity else None,
            "message": self.message, "fired_at": self.fired_at.isoformat() if self.fired_at else None,
            "is_active": self.is_active, "acknowledged_by": self.acknowledged_by,
        }


__all__ = ["Alert"]
