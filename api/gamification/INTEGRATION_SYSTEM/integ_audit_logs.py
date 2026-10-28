"""
Integration Audit Logs — Comprehensive audit logging for integration system.

This module provides audit logging capabilities for tracking all integration
activities, security events, and compliance requirements.
"""

from __future__ import annotations
from datetime import timedelta

import logging
import threading
import time
import json
import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit Log Types
# ---------------------------------------------------------------------------

class AuditAction(Enum):
    """Audit action enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SEND = "send"
    RECEIVE = "receive"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    SYNC = "sync"
    BACKUP = "backup"
    RESTORE = "restore"
    CONFIGURE = "configure"
    START = "start"
    STOP = "stop"
    ERROR = "error"
    SECURITY = "security"


class ResourceType(Enum):
    """Resource type enumeration."""
    INTEGRATION = "integration"
    USER = "user"
    CONTEST = "contest"
    ACHIEVEMENT = "achievement"
    LEADERBOARD = "leaderboard"
    BADGE = "badge"
    REWARD = "reward"
    SYSTEM = "system"


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


# ---------------------------------------------------------------------------
# Audit Log Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AuditLogEntry:
    """Audit log entry."""
    
    id: str
    action: AuditAction
    resource_type: ResourceType
    resource_id: Optional[str]
    user_id: Optional[str]
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    error: Optional[str] = None
    level: LogLevel = LogLevel.INFO
    checksum: str = field(default="")
    
    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for audit entry."""
        data = {
            'id': self.id,
            'action': self.action.value,
            'resource_type': self.resource_type.value,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'error': self.error,
            'level': self.level.value
        }
        
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'action': self.action.value,
            'resource_type': self.resource_type.value,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'error': self.error,
            'level': self.level.value,
            'checksum': self.checksum
        }


# ---------------------------------------------------------------------------
# Audit Logger Implementation
# ---------------------------------------------------------------------------

class AuditLogger:
    """Main audit logger implementation."""
    AuditAction = AuditAction
    ResourceType = ResourceType
    LogLevel = LogLevel
    
    def __init__(self):
        self.logs: List[AuditLogEntry] = []
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self.max_logs = 10000  # Maximum logs to keep in memory
    
    def log_audit(
        self,
        action: AuditAction,
        description: str,
        resource_type: ResourceType = ResourceType.INTEGRATION,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error: Optional[str] = None,
        level: LogLevel = LogLevel.INFO
    ) -> None:
        """Log an audit event."""
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            description=description,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            error=error,
            level=level
        )
        
        with self._lock:
            self.logs.append(entry)
            
            # Keep only the most recent logs
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
        
        # Log to standard logger as well
        log_message = f"[AUDIT] {action.value.upper()} {resource_type.value} - {description}"
        if error:
            log_message += f" (ERROR: {error})"
        
        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)
        elif level == LogLevel.SECURITY:
            self.logger.warning(f"[SECURITY] {log_message}")
    
    def log(self, *args, **kwargs) -> None:
        """Alias for log_audit().

        Several callers (api/gamification/models.py, api/gamification/
        services/services_core.py) call audit_logger.log(...) using the
        same keyword arguments as log_audit() (action, description,
        resource_type, resource_id, user_id, details, error, etc).
        This alias exists purely for backward compatibility with those
        call sites and simply forwards to log_audit().
        """
        self.log_audit(*args, **kwargs)

    def log(self, *args, **kwargs) -> None:
        """Alias for log_audit().

        Several callers (api/gamification/models.py, api/gamification/
        services/services_core.py) call audit_logger.log(...) using the
        same keyword arguments as log_audit() (action, description,
        resource_type, resource_id, user_id, details, error, etc).
        This alias exists purely for backward compatibility with those
        call sites and simply forwards to log_audit().
        """
        self.log_audit(*args, **kwargs)

    def get_logs(
        self,
        action: Optional[AuditAction] = None,
        resource_type: Optional[ResourceType] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Get audit logs with optional filtering."""
        with self._lock:
            logs = self.logs.copy()
        
        # Apply filters
        if action:
            logs = [log for log in logs if log.action == action]
        
        if resource_type:
            logs = [log for log in logs if log.resource_type == resource_type]
        
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        
        # Sort by timestamp descending
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return logs[:limit]
    
    def query_logs(self, filter: "AuditFilter") -> List[AuditLogEntry]:
        """Query audit logs using an AuditFilter (admin export compatibility).

        NOTE: AuditFilter.levels (type AuditLevel) and AuditFilter.tags are
        NOT applied here because this AuditLogger's entries use a different
        enum (LogLevel) and have no 'tags' attribute. Those two filter
        fields are silently ignored by this implementation.
        """
        with self._lock:
            logs = self.logs.copy()

        if filter.start_date:
            logs = [log for log in logs if log.timestamp >= filter.start_date]

        if filter.end_date:
            logs = [log for log in logs if log.timestamp <= filter.end_date]

        if filter.actions:
            logs = [log for log in logs if log.action in filter.actions]

        if filter.resource_types:
            logs = [log for log in logs if log.resource_type in filter.resource_types]

        if filter.resource_ids:
            logs = [log for log in logs if log.resource_id in filter.resource_ids]

        if filter.user_ids:
            logs = [log for log in logs if log.user_id in filter.user_ids]

        if filter.ip_addresses:
            logs = [log for log in logs if log.ip_address in filter.ip_addresses]

        if filter.search_text:
            search = filter.search_text.lower()
            logs = [log for log in logs if search in log.description.lower()]

        # Sort by timestamp descending (consistent with get_logs())
        logs.sort(key=lambda x: x.timestamp, reverse=True)

        offset = filter.offset or 0
        limit = filter.limit or 100
        return logs[offset:offset + limit]

    def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Get logs within a date range."""
        with self._lock:
            logs = self.logs.copy()
        
        logs = [
            log for log in logs
            if start_date <= log.timestamp <= end_date
        ]
        
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return logs[:limit]
    
    def verify_log_integrity(self, log_id: str) -> bool:
        """Verify the integrity of a specific log entry."""
        with self._lock:
            log = next((l for l in self.logs if l.id == log_id), None)
        
        if not log:
            return False
        
        # Recalculate checksum
        original_checksum = log.checksum
        log.checksum = ""
        recalculated_checksum = log._calculate_checksum()
        log.checksum = original_checksum
        
        return original_checksum == recalculated_checksum
    
    def export_logs(
        self,
        format: str = "json",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> str:
        """Export logs in specified format."""
        logs = self.get_logs_by_date_range(
            start_date or datetime.min.replace(tzinfo=timezone.utc),
            end_date or datetime.max.replace(tzinfo=timezone.utc),
            limit=10000
        )
        
        if format.lower() == "json":
            return json.dumps([log.to_dict() for log in logs], indent=2)
        elif format.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if logs:
                writer = csv.DictWriter(output, fieldnames=logs[0].to_dict().keys())
                writer.writeheader()
                for log in logs:
                    writer.writerow(log.to_dict())
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_old_logs(self, days: int = 30) -> int:
        """Clear logs older than specified days."""
        cutoff_date = datetime.now(timezone.utc) - timezone.timedelta(days=days)
        
        with self._lock:
            original_count = len(self.logs)
            self.logs = [log for log in self.logs if log.timestamp >= cutoff_date]
            cleared_count = original_count - len(self.logs)
        
        self.logger.info(f"Cleared {cleared_count} old audit logs")
        return cleared_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        with self._lock:
            logs = self.logs.copy()
        
        if not logs:
            return {"total_logs": 0}
        
        stats = {
            "total_logs": len(logs),
            "by_action": {},
            "by_resource_type": {},
            "by_level": {},
            "by_user": {},
            "error_count": 0,
            "security_count": 0,
            "date_range": {
                "earliest": min(log.timestamp for log in logs).isoformat(),
                "latest": max(log.timestamp for log in logs).isoformat()
            }
        }
        
        for log in logs:
            # Count by action
            action_key = log.action.value
            stats["by_action"][action_key] = stats["by_action"].get(action_key, 0) + 1
            
            # Count by resource type
            resource_key = log.resource_type.value
            stats["by_resource_type"][resource_key] = stats["by_resource_type"].get(resource_key, 0) + 1
            
            # Count by level
            level_key = log.level.value
            stats["by_level"][level_key] = stats["by_level"].get(level_key, 0) + 1
            
            # Count by user
            if log.user_id:
                user_key = log.user_id
                stats["by_user"][user_key] = stats["by_user"].get(user_key, 0) + 1
            
            # Count errors and security events
            if log.error:
                stats["error_count"] += 1
            
            if log.level == LogLevel.SECURITY:
                stats["security_count"] += 1
        
        return stats


# Global audit logger instance
audit_logger = AuditLogger()

# Initialize logging
logger.info("Integration audit logs module initialized")


class AuditLevel(Enum):
    """Audit level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class ResourceType(Enum):
    """Resource type enumeration."""
    INTEGRATION = "integration"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    MESSAGE = "message"
    EVENT = "event"
    CONFIGURATION = "configuration"
    CREDENTIAL = "credential"
    BRIDGE = "bridge"
    QUEUE = "queue"
    WEBHOOK = "webhook"
    SYSTEM = "system"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Audit Log Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AuditLog:
    """Audit log entry."""
    
    id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    action: AuditAction = AuditAction.EXECUTE
    level: AuditLevel = AuditLevel.INFO
    resource_type: ResourceType = ResourceType.SYSTEM
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    integration_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for integrity verification."""
        # Create canonical representation
        data = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "level": self.level.value,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "description": self.description,
            "details": self.details
        }
        
        # Sort keys for consistent ordering
        canonical_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
        self.checksum = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        
        return self.checksum
    
    def verify_checksum(self) -> bool:
        """Verify data integrity using checksum."""
        if not self.checksum:
            return True
        
        original_checksum = self.checksum
        calculated_checksum = self.calculate_checksum()
        
        return original_checksum == calculated_checksum
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "level": self.level.value,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "integration_id": self.integration_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "description": self.description,
            "details": self.details,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "error": self.error,
            "stack_trace": self.stack_trace,
            "tags": self.tags,
            "checksum": self.checksum,
            "verified": self.verify_checksum() if self.checksum else None
        }


@dataclass
class AuditFilter:
    """Filter for audit log queries."""
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    actions: Optional[List[AuditAction]] = None
    levels: Optional[List[AuditLevel]] = None
    resource_types: Optional[List[ResourceType]] = None
    resource_ids: Optional[List[str]] = None
    user_ids: Optional[List[str]] = None
    integration_ids: Optional[List[str]] = None
    ip_addresses: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    search_text: Optional[str] = None
    limit: int = 100
    offset: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "actions": [a.value for a in self.actions] if self.actions else None,
            "levels": [l.value for l in self.levels] if self.levels else None,
            "resource_types": [rt.value for rt in self.resource_types] if self.resource_types else None,
            "resource_ids": self.resource_ids,
            "user_ids": self.user_ids,
            "integration_ids": self.integration_ids,
            "ip_addresses": self.ip_addresses,
            "tags": self.tags,
            "search_text": self.search_text,
            "limit": self.limit,
            "offset": self.offset
        }


@dataclass
class AuditConfig:
    """Audit logging configuration."""
    
    enabled: bool = True
    log_level: AuditLevel = AuditLevel.INFO
    retention_days: int = 90
    max_entries: int = 1000000
    enable_checksum: bool = True
    enable_compression: bool = False
    async_logging: bool = True
    buffer_size: int = 1000
    flush_interval: float = 5.0
    excluded_actions: List[AuditAction] = field(default_factory=list)
    excluded_levels: List[AuditLevel] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    
    def should_log(self, action: AuditAction, level: AuditLevel) -> bool:
        """Check if action/level should be logged."""
        if not self.enabled:
            return False
        
        if action in self.excluded_actions:
            return False
        
        if level in self.excluded_levels:
            return False
        
        return True


# ---------------------------------------------------------------------------
# Abstract Audit Storage
# ---------------------------------------------------------------------------

class BaseAuditStorage(ABC):
    """Abstract base class for audit log storage."""
    
    @abstractmethod
    def store(self, audit_log: AuditLog) -> bool:
        """Store an audit log entry."""
        pass
    
    @abstractmethod
    def retrieve(self, log_id: str) -> Optional[AuditLog]:
        """Retrieve an audit log entry by ID."""
        pass
    
    @abstractmethod
    def query(self, filter: AuditFilter) -> List[AuditLog]:
        """Query audit logs with filter."""
        pass
    
    @abstractmethod
    def delete(self, log_id: str) -> bool:
        """Delete an audit log entry."""
        pass
    
    @abstractmethod
    def cleanup(self, retention_days: int) -> int:
        """Clean up old audit logs."""
        pass


# ---------------------------------------------------------------------------
# In-Memory Audit Storage
# ---------------------------------------------------------------------------

class InMemoryAuditStorage(BaseAuditStorage):
    """In-memory audit log storage."""
    
    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self.logs: Dict[str, AuditLog] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def store(self, audit_log: AuditLog) -> bool:
        """Store an audit log entry."""
        with self._lock:
            # Check if we need to remove old entries
            if len(self.logs) >= self.max_entries:
                # Remove oldest entries
                sorted_logs = sorted(self.logs.values(), key=lambda x: x.timestamp)
                for old_log in sorted_logs[:100]:  # Remove 100 oldest
                    del self.logs[old_log.id]
            
            # Calculate checksum if enabled
            if hasattr(audit_log, 'calculate_checksum'):
                audit_log.calculate_checksum()
            
            self.logs[audit_log.id] = audit_log
            return True
    
    def retrieve(self, log_id: str) -> Optional[AuditLog]:
        """Retrieve an audit log entry by ID."""
        with self._lock:
            log = self.logs.get(log_id)
            if log and hasattr(log, 'verify_checksum'):
                # Verify integrity
                if not log.verify_checksum():
                    self.logger.warning(f"Audit log integrity check failed: {log_id}")
                    return None
            return log
    
    def query(self, filter: AuditFilter) -> List[AuditLog]:
        """Query audit logs with filter."""
        with self._lock:
            logs = list(self.logs.values())
            
            # Apply filters
            if filter.start_date:
                logs = [log for log in logs if log.timestamp >= filter.start_date]
            
            if filter.end_date:
                logs = [log for log in logs if log.timestamp <= filter.end_date]
            
            if filter.actions:
                logs = [log for log in logs if log.action in filter.actions]
            
            if filter.levels:
                logs = [log for log in logs if log.level in filter.levels]
            
            if filter.resource_types:
                logs = [log for log in logs if log.resource_type in filter.resource_types]
            
            if filter.resource_ids:
                logs = [log for log in logs if log.resource_id in filter.resource_ids]
            
            if filter.user_ids:
                logs = [log for log in logs if log.user_id in filter.user_ids]
            
            if filter.integration_ids:
                logs = [log for log in logs if log.integration_id in filter.integration_ids]
            
            if filter.ip_addresses:
                logs = [log for log in logs if log.ip_address in filter.ip_addresses]
            
            if filter.tags:
                logs = [log for log in logs if any(tag in log.tags for tag in filter.tags)]
            
            if filter.search_text:
                search_lower = filter.search_text.lower()
                logs = [log for log in logs if 
                       search_lower in log.description.lower() or
                       search_lower in json.dumps(log.details).lower()]
            
            # Sort by timestamp descending
            logs.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Apply pagination
            if filter.offset:
                logs = logs[filter.offset:]
            
            if filter.limit:
                logs = logs[:filter.limit]
            
            return logs
    
    def delete(self, log_id: str) -> bool:
        """Delete an audit log entry."""
        with self._lock:
            if log_id in self.logs:
                del self.logs[log_id]
                return True
            return False
    
    def cleanup(self, retention_days: int) -> int:
        """Clean up old audit logs."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        with self._lock:
            old_logs = [log for log in self.logs.values() if log.timestamp < cutoff_date]
            
            for log in old_logs:
                del self.logs[log.id]
            
            return len(old_logs)


# ---------------------------------------------------------------------------
# Audit Logger Implementation
# ---------------------------------------------------------------------------

class AdvancedAuditLogger:
    """Main audit logging system."""
    
    def __init__(self, config: Optional[AuditConfig] = None, storage: Optional[BaseAuditStorage] = None):
        self.config = config or AuditConfig()
        self.storage = storage or InMemoryAuditStorage(max_entries=self.config.max_entries)
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._buffer: List[AuditLog] = []
        self._buffer_lock = threading.RLock()
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        
        if self.config.async_logging:
            self.start_async_logging()
    
    def start_async_logging(self) -> None:
        """Start async logging."""
        if self._running:
            return
        
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        
        self.logger.info("Async audit logging started")
    
    def stop_async_logging(self) -> None:
        """Stop async logging."""
        self._running = False
        
        if self._flush_thread:
            self._flush_thread.join(timeout=5.0)
        
        # Flush remaining buffer
        self.flush_buffer()
        
        self.logger.info("Async audit logging stopped")
    
    def log(
        self,
        action: AuditAction,
        description: str,
        level: AuditLevel = AuditLevel.INFO,
        resource_type: ResourceType = ResourceType.SYSTEM,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        integration_id: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Log an audit event."""
        if not self.config.should_log(action, level):
            return ""
        
        import uuid
        
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            level=level,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            integration_id=integration_id,
            description=description,
            details=kwargs.get("details", {}),
            old_values=kwargs.get("old_values"),
            new_values=kwargs.get("new_values"),
            error=kwargs.get("error"),
            stack_trace=kwargs.get("stack_trace"),
            tags=kwargs.get("tags", []),
            ip_address=kwargs.get("ip_address"),
            user_agent=kwargs.get("user_agent"),
            request_id=kwargs.get("request_id"),
            correlation_id=kwargs.get("correlation_id"),
            session_id=kwargs.get("session_id")
        )
        
        # Validate required fields
        for field in self.config.required_fields:
            if not getattr(audit_log, field, None):
                self.logger.error(f"Required audit field missing: {field}")
                return ""
        
        if self.config.async_logging:
            self._add_to_buffer(audit_log)
        else:
            self._store_log(audit_log)
        
        return audit_log.id
    
    def log_authentication(
        self,
        user_id: str,
        success: bool,
        auth_type: str,
        ip_address: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Log authentication event."""
        return self.log(
            action=AuditAction.AUTHENTICATE,
            description=f"User authentication {'success' if success else 'failed'} using {auth_type}",
            level=AuditLevel.INFO if success else AuditLevel.WARNING,
            resource_type=ResourceType.USER,
            resource_id=user_id,
            user_id=user_id,
            ip_address=ip_address,
            details={"auth_type": auth_type, "success": success},
            **kwargs
        )
    
    def log_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        granted: bool,
        **kwargs: Any
    ) -> str:
        """Log authorization event."""
        return self.log(
            action=AuditAction.AUTHORIZE,
            description=f"Authorization {'granted' if granted else 'denied'} for {action} on {resource}",
            level=AuditLevel.INFO if granted else AuditLevel.WARNING,
            resource_type=ResourceType.PERMISSION,
            resource_id=resource,
            user_id=user_id,
            details={"resource": resource, "action": action, "granted": granted},
            **kwargs
        )
    
    def log_integration_event(
        self,
        integration_id: str,
        action: AuditAction,
        description: str,
        success: bool = True,
        **kwargs: Any
    ) -> str:
        """Log integration event."""
        return self.log(
            action=action,
            description=description,
            level=AuditLevel.INFO if success else AuditLevel.ERROR,
            resource_type=ResourceType.INTEGRATION,
            resource_id=integration_id,
            integration_id=integration_id,
            details={"success": success},
            error=kwargs.get("error") if not success else None,
            **kwargs
        )
    
    def log_data_access(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        action: AuditAction,
        **kwargs: Any
    ) -> str:
        """Log data access event."""
        return self.log(
            action=action,
            description=f"Data {action.value} on {resource_type.value} {resource_id}",
            level=AuditLevel.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            **kwargs
        )
    
    def log_configuration_change(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        old_values: Optional[Dict[str, Any]],
        new_values: Optional[Dict[str, Any]],
        **kwargs: Any
    ) -> str:
        """Log configuration change."""
        return self.log(
            action=AuditAction.CONFIGURE,
            description=f"Configuration changed for {resource_type.value} {resource_id}",
            level=AuditLevel.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            **kwargs
        )
    
    def log_security_event(
        self,
        description: str,
        severity: AuditLevel = AuditLevel.SECURITY,
        **kwargs: Any
    ) -> str:
        """Log security event."""
        return self.log(
            action=AuditAction.SECURITY,
            description=description,
            level=severity,
            resource_type=ResourceType.SYSTEM,
            tags=["security"],
            **kwargs
        )
    
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """Get an audit log by ID."""
        return self.storage.retrieve(log_id)
    
    def query_logs(self, filter: AuditFilter) -> List[AuditLog]:
        """Query audit logs."""
        return self.storage.query(filter)
    
    def delete_log(self, log_id: str) -> bool:
        """Delete an audit log."""
        return self.storage.delete(log_id)
    
    def cleanup_old_logs(self) -> int:
        """Clean up old audit logs."""
        return self.storage.cleanup(self.config.retention_days)
    
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics."""
        # This would aggregate statistics from storage
        # For now, return basic stats
        return {
            "enabled": self.config.enabled,
            "async_logging": self.config.async_logging,
            "retention_days": self.config.retention_days,
            "buffer_size": len(self._buffer) if self.config.async_logging else 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _add_to_buffer(self, audit_log: AuditLog) -> None:
        """Add log to buffer for async processing."""
        with self._buffer_lock:
            self._buffer.append(audit_log)
            
            # Flush if buffer is full
            if len(self._buffer) >= self.config.buffer_size:
                self.flush_buffer()
    
    def flush_buffer(self) -> int:
        """Flush buffer to storage."""
        with self._buffer_lock:
            if not self._buffer:
                return 0
            
            logs_to_flush = self._buffer.copy()
            self._buffer.clear()
            
            # Store logs
            stored_count = 0
            for log in logs_to_flush:
                if self._store_log(log):
                    stored_count += 1
            
            return stored_count
    
    def _store_log(self, audit_log: AuditLog) -> bool:
        """Store a single audit log."""
        try:
            return self.storage.store(audit_log)
        except Exception as e:
            self.logger.error(f"Error storing audit log: {e}")
            return False
    
    def _flush_loop(self) -> None:
        """Main flush loop for async logging."""
        while self._running:
            try:
                time.sleep(self.config.flush_interval)
                self.flush_buffer()
            except Exception as e:
                self.logger.error(f"Error in flush loop: {e}")


# Global audit logger instance
advanced_audit_logger = AdvancedAuditLogger()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def log_audit(
    action: AuditAction,
    description: str,
    level: AuditLevel = AuditLevel.INFO,
    **kwargs: Any
) -> str:
    """Log an audit event."""
    return advanced_audit_logger.log(action, description, level, **kwargs)


def log_auth_event(user_id: str, success: bool, auth_type: str, **kwargs: Any) -> str:
    """Log authentication event."""
    return advanced_audit_logger.log_authentication(user_id, success, auth_type, **kwargs)


def log_security_event(description: str, **kwargs: Any) -> str:
    """Log security event."""
    return advanced_audit_logger.log_security_event(description, **kwargs)


# Initialize logging
logger.info("Integration audit logs module initialized")
