"""
Integration Audit Logs
Comprehensive audit logging for integration system
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from collections import defaultdict
import asyncio

from .integ_exceptions import IntegrationException, AuditLogException

logger = logging.getLogger(__name__)


class AuditLogLevel(Enum):
    """Audit log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class AuditActionType(Enum):
    """Audit action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SEND = "send"
    RECEIVE = "receive"
    BACKUP = "backup"
    RESTORE = "restore"
    SYNC = "sync"
    MIGRATE = "migrate"
    DEPLOY = "deploy"
    CONFIGURE = "configure"
    MONITOR = "monitor"
    ALERT = "alert"
    CUSTOM = "custom"


class AuditResourceType(Enum):
    """Audit resource types"""
    SYSTEM = "system"
    ADAPTER = "adapter"
    BRIDGE = "bridge"
    EVENT = "event"
    WEBHOOK = "webhook"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"
    DATA = "data"
    METRIC = "metric"
    ALERT = "alert"
    SESSION = "session"
    CONNECTION = "connection"
    TRANSACTION = "transaction"
    BACKUP = "backup"
    RESTORATION = "restoration"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    CUSTOM = "custom"


@dataclass
class AuditLogEntry:
    """Audit log entry"""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: AuditLogLevel = AuditLogLevel.INFO
    action_type: AuditActionType = AuditActionType.CUSTOM
    resource_type: AuditResourceType = AuditResourceType.CUSTOM
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    tenant_id: Optional[str] = None
    system: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    duration_ms: Optional[float] = None
    success: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'log_id': self.log_id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'action_type': self.action_type.value,
            'resource_type': self.resource_type.value,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'tenant_id': self.tenant_id,
            'system': self.system,
            'component': self.component,
            'operation': self.operation,
            'message': self.message,
            'details': self.details,
            'request_data': self.request_data,
            'response_data': self.response_data,
            'error_message': self.error_message,
            'error_traceback': self.error_traceback,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'source_ip': self.source_ip,
            'destination_ip': self.destination_ip,
            'duration_ms': self.duration_ms,
            'success': self.success,
            'tags': self.tags,
            'metadata': self.metadata
        }


@dataclass
class AuditFilter:
    """Audit log filter"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    levels: List[AuditLogLevel] = field(default_factory=list)
    action_types: List[AuditActionType] = field(default_factory=list)
    resource_types: List[AuditResourceType] = field(default_factory=list)
    user_ids: List[str] = field(default_factory=list)
    session_ids: List[str] = field(default_factory=list)
    request_ids: List[str] = field(default_factory=list)
    tenant_ids: List[str] = field(default_factory=list)
    systems: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    resource_ids: List[str] = field(default_factory=list)
    success: Optional[bool] = None
    tags: List[str] = field(default_factory=list)
    ip_addresses: List[str] = field(default_factory=list)
    message_contains: Optional[str] = None
    limit: int = 100
    offset: int = 0


@dataclass
class AuditStatistics:
    """Audit statistics"""
    total_logs: int = 0
    logs_by_level: Dict[str, int] = field(default_factory=dict)
    logs_by_action_type: Dict[str, int] = field(default_factory=dict)
    logs_by_resource_type: Dict[str, int] = field(default_factory=dict)
    logs_by_system: Dict[str, int] = field(default_factory=dict)
    logs_by_user: Dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.0
    average_duration_ms: float = 0.0
    error_rate: float = 0.0
    security_events: int = 0
    time_period_hours: float = 24.0


class AuditLogStorage:
    """Audit log storage interface"""
    
    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self.logs: List[AuditLogEntry] = []
        self.indexes = {
            'user_id': defaultdict(list),
            'session_id': defaultdict(list),
            'request_id': defaultdict(list),
            'tenant_id': defaultdict(list),
            'system': defaultdict(list),
            'component': defaultdict(list),
            'level': defaultdict(list),
            'action_type': defaultdict(list),
            'resource_type': defaultdict(list),
            'timestamp': defaultdict(list)
        }
    
    async def store_log(self, entry: AuditLogEntry):
        """Store audit log entry"""
        # Add to main storage
        self.logs.append(entry)
        
        # Maintain max size
        if len(self.logs) > self.max_entries:
            removed_entry = self.logs.pop(0)
            self._remove_from_indexes(removed_entry)
        
        # Update indexes
        self._update_indexes(entry)
    
    def _update_indexes(self, entry: AuditLogEntry):
        """Update indexes for fast lookup"""
        self.indexes['user_id'][entry.user_id].append(entry)
        self.indexes['session_id'][entry.session_id].append(entry)
        self.indexes['request_id'][entry.request_id].append(entry)
        self.indexes['tenant_id'][entry.tenant_id].append(entry)
        self.indexes['system'][entry.system].append(entry)
        self.indexes['component'][entry.component].append(entry)
        self.indexes['level'][entry.level.value].append(entry)
        self.indexes['action_type'][entry.action_type.value].append(entry)
        self.indexes['resource_type'][entry.resource_type.value].append(entry)
        
        # Time-based index (hour buckets)
        hour_key = entry.timestamp.strftime('%Y-%m-%d-%H')
        self.indexes['timestamp'][hour_key].append(entry)
    
    def _remove_from_indexes(self, entry: AuditLogEntry):
        """Remove entry from indexes"""
        for index_type, index in self.indexes.items():
            key = getattr(entry, index_type, None)
            if key and key in index:
                index[key].remove(entry)
    
    async def query_logs(self, filter: AuditFilter) -> List[AuditLogEntry]:
        """Query audit logs with filter"""
        results = self.logs
        
        # Apply filters
        if filter.start_time:
            results = [log for log in results if log.timestamp >= filter.start_time]
        
        if filter.end_time:
            results = [log for log in results if log.timestamp <= filter.end_time]
        
        if filter.levels:
            level_values = [level.value for level in filter.levels]
            results = [log for log in results if log.level.value in level_values]
        
        if filter.action_types:
            action_values = [action.value for action in filter.action_types]
            results = [log for log in results if log.action_type.value in action_values]
        
        if filter.resource_types:
            resource_values = [resource.value for resource in filter.resource_types]
            results = [log for log in results if log.resource_type.value in resource_values]
        
        if filter.user_ids:
            results = [log for log in results if log.user_id in filter.user_ids]
        
        if filter.session_ids:
            results = [log for log in results if log.session_id in filter.session_ids]
        
        if filter.request_ids:
            results = [log for log in results if log.request_id in filter.request_ids]
        
        if filter.tenant_ids:
            results = [log for log in results if log.tenant_id in filter.tenant_ids]
        
        if filter.systems:
            results = [log for log in results if log.system in filter.systems]
        
        if filter.components:
            results = [log for log in results if log.component in filter.components]
        
        if filter.operations:
            results = [log for log in results if log.operation in filter.operations]
        
        if filter.resource_ids:
            results = [log for log in results if log.resource_id in filter.resource_ids]
        
        if filter.success is not None:
            results = [log for log in results if log.success == filter.success]
        
        if filter.tags:
            results = [log for log in results if any(tag in log.tags for tag in filter.tags)]
        
        if filter.ip_addresses:
            results = [log for log in results if log.ip_address in filter.ip_addresses]
        
        if filter.message_contains:
            results = [log for log in results if filter.message_contains.lower() in log.message.lower()]
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply pagination
        start_idx = filter.offset
        end_idx = start_idx + filter.limit
        
        return results[start_idx:end_idx]
    
    async def get_statistics(self, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> AuditStatistics:
        """Get audit statistics"""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()
        
        # Filter logs for time period
        time_logs = [log for log in self.logs if start_time <= log.timestamp <= end_time]
        
        if not time_logs:
            return AuditStatistics(time_period_hours=24.0)
        
        stats = AuditStatistics(
            total_logs=len(time_logs),
            time_period_hours=(end_time - start_time).total_seconds() / 3600
        )
        
        # Count by level
        for log in time_logs:
            level_key = log.level.value
            stats.logs_by_level[level_key] = stats.logs_by_level.get(level_key, 0) + 1
        
        # Count by action type
        for log in time_logs:
            action_key = log.action_type.value
            stats.logs_by_action_type[action_key] = stats.logs_by_action_type.get(action_key, 0) + 1
        
        # Count by resource type
        for log in time_logs:
            resource_key = log.resource_type.value
            stats.logs_by_resource_type[resource_key] = stats.logs_by_resource_type.get(resource_key, 0) + 1
        
        # Count by system
        for log in time_logs:
            if log.system:
                stats.logs_by_system[log.system] = stats.logs_by_system.get(log.system, 0) + 1
        
        # Count by user
        for log in time_logs:
            if log.user_id:
                stats.logs_by_user[log.user_id] = stats.logs_by_user.get(log.user_id, 0) + 1
        
        # Calculate success rate
        success_count = sum(1 for log in time_logs if log.success)
        stats.success_rate = (success_count / len(time_logs)) * 100 if time_logs else 0
        
        # Calculate error rate
        error_count = sum(1 for log in time_logs if not log.success)
        stats.error_rate = (error_count / len(time_logs)) * 100 if time_logs else 0
        
        # Calculate average duration
        durations = [log.duration_ms for log in time_logs if log.duration_ms is not None]
        if durations:
            stats.average_duration_ms = sum(durations) / len(durations)
        
        # Count security events
        stats.security_events = len([log for log in time_logs if log.level == AuditLogLevel.SECURITY])
        
        return stats
    
    async def cleanup_old_logs(self, retention_days: int = 90):
        """Clean up old logs"""
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
        
        # Find old logs
        old_logs = [log for log in self.logs if log.timestamp < cutoff_time]
        
        # Remove old logs
        for log in old_logs:
            self.logs.remove(log)
            self._remove_from_indexes(log)
        
        logger.info(f"Cleaned up {len(old_logs)} old audit logs")


class AuditLogger:
    """
    Comprehensive audit logger for integration system
    """
    
    def __init__(self, storage: Optional[AuditLogStorage] = None):
        self.storage = storage or AuditLogStorage()
        self.log_handlers: List[Callable] = []
        self.context_stack: List[Dict[str, Any]] = []
        self.default_context: Dict[str, Any] = {}
        self.sensitive_fields = ['password', 'token', 'secret', 'key', 'credential']
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default log handlers"""
        # Console handler
        def console_handler(entry: AuditLogEntry):
            level_map = {
                AuditLogLevel.DEBUG: logging.DEBUG,
                AuditLogLevel.INFO: logging.INFO,
                AuditLogLevel.WARNING: logging.WARNING,
                AuditLogLevel.ERROR: logging.ERROR,
                AuditLogLevel.CRITICAL: logging.CRITICAL,
                AuditLogLevel.SECURITY: logging.CRITICAL
            }
            
            log_level = level_map.get(entry.level, logging.INFO)
            logger.log(log_level, f"[AUDIT] {entry.message}", extra=entry.to_dict())
        
        self.add_handler(console_handler)
    
    def add_handler(self, handler: Callable):
        """Add a log handler"""
        self.log_handlers.append(handler)
    
    def set_default_context(self, **context):
        """Set default context for all logs"""
        self.default_context.update(context)
    
    def push_context(self, **context):
        """Push context to stack"""
        self.context_stack.append(context)
    
    def pop_context(self):
        """Pop context from stack"""
        if self.context_stack:
            return self.context_stack.pop()
        return {}
    
    def get_current_context(self) -> Dict[str, Any]:
        """Get current context"""
        context = self.default_context.copy()
        
        # Merge stack contexts
        for stack_context in self.context_stack:
            context.update(stack_context)
        
        return context
    
    async def log(self, level: AuditLogLevel, action_type: AuditActionType,
                 resource_type: AuditResourceType, message: str,
                 resource_id: Optional[str] = None, **kwargs):
        """Log an audit entry"""
        # Get current context
        context = self.get_current_context()
        
        # Merge with provided kwargs
        context.update(kwargs)
        
        # Create audit entry
        entry = AuditLogEntry(
            level=level,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            message=message,
            user_id=context.get('user_id'),
            session_id=context.get('session_id'),
            request_id=context.get('request_id'),
            tenant_id=context.get('tenant_id'),
            system=context.get('system'),
            component=context.get('component'),
            operation=context.get('operation'),
            details=context.get('details', {}),
            request_data=self._sanitize_data(context.get('request_data')),
            response_data=self._sanitize_data(context.get('response_data')),
            error_message=context.get('error_message'),
            error_traceback=context.get('error_traceback'),
            ip_address=context.get('ip_address'),
            user_agent=context.get('user_agent'),
            source_ip=context.get('source_ip'),
            destination_ip=context.get('destination_ip'),
            duration_ms=context.get('duration_ms'),
            success=context.get('success', True),
            tags=context.get('tags', []),
            metadata=context.get('metadata', {})
        )
        
        # Store entry
        await self.storage.store_log(entry)
        
        # Notify handlers
        for handler in self.log_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(entry)
                else:
                    handler(entry)
            except Exception as e:
                logger.error(f"Error in audit log handler: {e}")
    
    def _sanitize_data(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Sanitize sensitive data"""
        if not data:
            return None
        
        sanitized = data.copy()
        
        for key, value in sanitized.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
        
        return sanitized
    
    async def log_info(self, action_type: AuditActionType, resource_type: AuditResourceType,
                      message: str, **kwargs):
        """Log info level audit entry"""
        await self.log(AuditLogLevel.INFO, action_type, resource_type, message, **kwargs)
    
    async def log_warning(self, action_type: AuditActionType, resource_type: AuditResourceType,
                        message: str, **kwargs):
        """Log warning level audit entry"""
        await self.log(AuditLogLevel.WARNING, action_type, resource_type, message, **kwargs)
    
    async def log_error(self, action_type: AuditActionType, resource_type: AuditResourceType,
                       message: str, **kwargs):
        """Log error level audit entry"""
        await self.log(AuditLogLevel.ERROR, action_type, resource_type, message, **kwargs)
    
    async def log_critical(self, action_type: AuditActionType, resource_type: AuditResourceType,
                          message: str, **kwargs):
        """Log critical level audit entry"""
        await self.log(AuditLogLevel.CRITICAL, action_type, resource_type, message, **kwargs)
    
    async def log_security(self, action_type: AuditActionType, resource_type: AuditResourceType,
                          message: str, **kwargs):
        """Log security level audit entry"""
        await self.log(AuditLogLevel.SECURITY, action_type, resource_type, message, **kwargs)
    
    async def log_authentication(self, user_id: str, success: bool, ip_address: str,
                               user_agent: Optional[str] = None, **kwargs):
        """Log authentication event"""
        level = AuditLogLevel.INFO if success else AuditLogLevel.SECURITY
        message = f"User authentication {'successful' if success else 'failed'}"
        
        await self.log(
            level=level,
            action_type=AuditActionType.AUTHENTICATE,
            resource_type=AuditResourceType.USER,
            message=message,
            resource_id=user_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            tags=['authentication'],
            **kwargs
        )
    
    async def log_authorization(self, user_id: str, resource_id: str, resource_type: AuditResourceType,
                              operation: str, success: bool, **kwargs):
        """Log authorization event"""
        level = AuditLogLevel.INFO if success else AuditLogLevel.SECURITY
        message = f"User {user_id} {'authorized' if success else 'denied'} for {operation} on {resource_type.value}"
        
        await self.log(
            level=level,
            action_type=AuditActionType.AUTHORIZE,
            resource_type=resource_type,
            message=message,
            resource_id=resource_id,
            user_id=user_id,
            operation=operation,
            success=success,
            tags=['authorization'],
            **kwargs
        )
    
    async def log_data_access(self, user_id: str, resource_type: AuditResourceType,
                            resource_id: str, operation: str, success: bool, **kwargs):
        """Log data access event"""
        level = AuditLogLevel.INFO if success else AuditLogLevel.WARNING
        message = f"Data {operation} {'successful' if success else 'failed'} for {resource_type.value}"
        
        await self.log(
            level=level,
            action_type=AuditActionType.READ if operation == 'read' else AuditActionType.UPDATE,
            resource_type=resource_type,
            message=message,
            resource_id=resource_id,
            user_id=user_id,
            operation=operation,
            success=success,
            tags=['data_access'],
            **kwargs
        )
    
    async def log_integration_event(self, system: str, component: str, operation: str,
                                   success: bool, duration_ms: Optional[float] = None,
                                   **kwargs):
        """Log integration event"""
        level = AuditLogLevel.INFO if success else AuditLogLevel.ERROR
        message = f"Integration {operation} {'successful' if success else 'failed'}"
        
        await self.log(
            level=level,
            action_type=AuditActionType.EXECUTE,
            resource_type=AuditResourceType.SYSTEM,
            message=message,
            system=system,
            component=component,
            operation=operation,
            success=success,
            duration_ms=duration_ms,
            tags=['integration'],
            **kwargs
        )
    
    async def log_backup_event(self, backup_id: str, operation: str, success: bool,
                             duration_ms: Optional[float] = None, **kwargs):
        """Log backup event"""
        level = AuditLogLevel.INFO if success else AuditLogLevel.ERROR
        message = f"Backup {operation} {'successful' if success else 'failed'}"
        
        await self.log(
            level=level,
            action_type=AuditActionType.BACKUP,
            resource_type=AuditResourceType.BACKUP,
            message=message,
            resource_id=backup_id,
            operation=operation,
            success=success,
            duration_ms=duration_ms,
            tags=['backup'],
            **kwargs
        )
    
    async def query_logs(self, filter: AuditFilter) -> List[AuditLogEntry]:
        """Query audit logs"""
        return await self.storage.query_logs(filter)
    
    async def get_statistics(self, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> AuditStatistics:
        """Get audit statistics"""
        return await self.storage.get_statistics(start_time, end_time)
    
    async def cleanup_old_logs(self, retention_days: int = 90):
        """Clean up old logs"""
        await self.storage.cleanup_old_logs(retention_days)


# Decorator for automatic audit logging
def audit_log(action_type: AuditActionType, resource_type: AuditResourceType,
              log_level: AuditLogLevel = AuditLogLevel.INFO):
    """Decorator for automatic audit logging"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            success = True
            error_message = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # Get audit logger
                audit_logger = get_audit_logger()
                
                # Calculate duration
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Log the event
                await audit_logger.log(
                    level=log_level if success else AuditLogLevel.ERROR,
                    action_type=action_type,
                    resource_type=resource_type,
                    message=f"{func.__name__} {'completed' if success else 'failed'}",
                    operation=func.__name__,
                    success=success,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    metadata={'function': func.__name__, 'args_count': len(args), 'kwargs': list(kwargs.keys())}
                )
        
        return wrapper
    return decorator


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def initialize_audit_logger(storage: Optional[AuditLogStorage] = None) -> AuditLogger:
    """Initialize the global audit logger"""
    global _audit_logger
    _audit_logger = AuditLogger(storage)
    return _audit_logger


# Export main classes and functions
__all__ = [
    'AuditLogger',
    'AuditLogEntry',
    'AuditFilter',
    'AuditStatistics',
    'AuditLogStorage',
    'AuditLogLevel',
    'AuditActionType',
    'AuditResourceType',
    'audit_log',
    'get_audit_logger',
    'initialize_audit_logger',
]
