"""
Config Model — SQLAlchemy model for runtime DR system configuration.
Stores key-value config that can be changed at runtime without redeployment.
Includes version history and audit trail.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON
from datetime import datetime
import uuid
from ..sa_models import Base


class DRConfig(Base):
    """
    Runtime configuration key-value store.
    Allows operators to change thresholds, toggle features,
    and update notification settings without code changes.
    """
    __tablename__ = "dr_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(300), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(50), default="string")   # string, int, float, bool, json
    description = Column(String(1000))
    is_secret = Column(Boolean, default=False)           # mask in logs/API
    updated_by = Column(String(200))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    version = Column(JSON, default=list)                 # history of old values

    def get_typed_value(self):
        """Return value cast to its declared type."""
        if self.value_type == "int":
            return int(self.value)
        if self.value_type == "float":
            return float(self.value)
        if self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes")
        if self.value_type == "json":
            import json
            return json.loads(self.value)
        return self.value

    def to_dict(self, mask_secrets: bool = True) -> dict:
        return {
            "key": self.key,
            "value": "***" if self.is_secret and mask_secrets else self.value,
            "value_type": self.value_type,
            "description": self.description,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


DEFAULT_CONFIGS = [
    {"key": "backup.auto_enabled", "value": "true", "value_type": "bool", "description": "Enable automatic scheduled backups"},
    {"key": "failover.auto_enabled", "value": "true", "value_type": "bool", "description": "Enable automatic failover"},
    {"key": "failover.health_check_failures", "value": "3", "value_type": "int", "description": "Consecutive failures before auto-failover"},
    {"key": "backup.encryption_enabled", "value": "true", "value_type": "bool", "description": "Encrypt all backup files"},
    {"key": "backup.compression_enabled", "value": "true", "value_type": "bool", "description": "Compress backup files"},
    {"key": "alert.cpu_threshold_pct", "value": "85.0", "value_type": "float", "description": "CPU alert threshold (%)"},
    {"key": "alert.memory_threshold_pct", "value": "90.0", "value_type": "float", "description": "Memory alert threshold (%)"},
    {"key": "alert.disk_threshold_pct", "value": "85.0", "value_type": "float", "description": "Disk alert threshold (%)"},
    {"key": "replication.lag_warning_seconds", "value": "30", "value_type": "int", "description": "Replication lag warning threshold"},
    {"key": "replication.lag_critical_seconds", "value": "120", "value_type": "int", "description": "Replication lag critical threshold"},
    {"key": "drill.min_interval_days", "value": "30", "value_type": "int", "description": "Minimum days between DR drills"},
    {"key": "sla.target_uptime_percent", "value": "99.9", "value_type": "float", "description": "Default SLA uptime target"},
]


__all__ = ["DRConfig", "DEFAULT_CONFIGS"]
