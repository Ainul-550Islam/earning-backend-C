"""
Restore Policy Model — Defines rules for when and how restores can be executed.
Includes approval requirements, notification rules, and target environment restrictions.
"""
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime
from datetime import datetime
import uuid
from ..sa_models import Base


class RestorePolicy(Base):
    """
    Governs restore operations:
    - Which environments require approval
    - Maximum restore window
    - Allowed restore types
    - Notification requirements
    """
    __tablename__ = "restore_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, unique=True)
    description = Column(String(1000))
    require_approval = Column(Boolean, default=True)
    approval_count = Column(Integer, default=1)       # how many approvers needed
    allowed_restore_types = Column(JSON, default=list) # ["full","partial","table","point_in_time"]
    allowed_environments = Column(JSON, default=list)  # ["staging","production"]
    max_restore_size_gb = Column(Integer)
    notify_on_start = Column(Boolean, default=True)
    notify_on_complete = Column(Boolean, default=True)
    notification_emails = Column(JSON, default=list)
    max_concurrent_restores = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


__all__ = ["RestorePolicy"]
