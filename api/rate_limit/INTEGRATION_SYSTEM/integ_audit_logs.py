"""
Integration Audit Logs - Comprehensive Audit Trail System

Comprehensive audit logging system for integration events with
structured logging, retention policies, and compliance features.
"""
import time

import logging
import json
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


class AuditLogLevel(Enum):
    """Audit log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class AuditCategory(Enum):
    """Audit log categories."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SYSTEM = "system"
    BUSINESS = "business"


class AuditAction(Enum):
    """Audit action types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    REJECT = "reject"
    LOGIN = "login"
    LOGOUT = "logout"
    BLOCK = "block"
    UNBLOCK = "unblock"
    EXPORT = "export"
    IMPORT = "import"
    SYNC = "sync"
    MIGRATE = "migrate"
    BACKUP = "backup"
    RESTORE = "restore"


@dataclass
class AuditLogEntry:
    """Audit log entry."""
    log_id: str
    timestamp: datetime
    level: AuditLogLevel
    category: AuditCategory
    action: AuditAction
    resource_type: str
    resource_id: Optional[str]
    user_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    correlation_id: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    compliance_relevant: bool = False
    retention_days: int = 365
    created_at: datetime = field(default_factory=timezone.now)


@dataclass
class AuditConfig:
    """Audit configuration."""
    log_all_requests: bool = True
    log_all_responses: bool = False
    log_request_data: bool = True
    log_response_data: bool = False
    log_sensitive_data: bool = False
    sensitive_fields: List[str] = field(default_factory=lambda: [
        'password', 'token', 'secret', 'key', 'credit_card', 'ssn', 'api_key'
    ])
    default_retention_days: int = 365
    max_log_size_mb: int = 1000
    enable_compression: bool = True
    enable_encryption: bool = False
    batch_size: int = 100
    flush_interval_seconds: int = 60
    archive_after_days: int = 90


class AuditLogger:
    """Comprehensive audit logging system."""
    
    def __init__(self, config: AuditConfig = None):
        self.config = config or AuditConfig()
        self.log_queue = Queue(maxsize=10000)
        self.archive_queue = Queue(maxsize=1000)
        self.statistics = {
            'total_logs': 0,
            'logs_by_level': {},
            'logs_by_category': {},
            'logs_by_action': {},
            'compliance_logs': 0,
            'archived_logs': 0,
            'failed_logs': 0,
            'start_time': timezone.now(),
            'last_log_time': None
        }
        self._lock = threading.RLock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._archive_thread: Optional[threading.Thread] = None
        self._log_handlers: Dict[str, Callable] = []
        
        # Start background threads
        self._start_background_threads()
    
    def _start_background_threads(self):
        """Start background threads for log processing."""
        self._running = True
        
        # Start log processing thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="AuditLogWorker",
            daemon=True
        )
        self._worker_thread.start()
        
        # Start archive thread
        self._archive_thread = threading.Thread(
            target=self._archive_loop,
            name="AuditLogArchive",
            daemon=True
        )
        self._archive_thread.start()
        
        logger.info("Started audit logging system")
    
    def _worker_loop(self):
        """Worker thread loop for processing audit logs."""
        batch = []
        last_flush = timezone.now()
        
        while self._running:
            try:
                # Get log entry from queue
                log_entry = self.log_queue.get(timeout=1)
                batch.append(log_entry)
                
                # Check if batch is ready
                should_flush = (
                    len(batch) >= self.config.batch_size or
                    (timezone.now() - last_flush).total_seconds() >= self.config.flush_interval_seconds
                )
                
                if should_flush and batch:
                    self._process_log_batch(batch)
                    batch.clear()
                    last_flush = timezone.now()
                
                # Mark task as done
                self.log_queue.task_done()
                
            except Empty:
                # Flush remaining batch if any
                if batch:
                    self._process_log_batch(batch)
                    batch.clear()
                    last_flush = timezone.now()
                continue
            except Exception as e:
                logger.error(f"Audit log worker error: {str(e)}")
                self.statistics['failed_logs'] += 1
    
    def _archive_loop(self):
        """Archive thread loop for processing old logs."""
        while self._running:
            try:
                # Sleep for 1 hour between archive runs
                time.sleep(3600)
                
                # Get logs to archive
                logs_to_archive = self._get_logs_to_archive()
                
                if logs_to_archive:
                    self._archive_logs(logs_to_archive)
                
            except Exception as e:
                logger.error(f"Audit archive error: {str(e)}")
    
    def _process_log_batch(self, batch: List[AuditLogEntry]):
        """Process a batch of audit logs."""
        try:
            # Process each log entry
            for log_entry in batch:
                self._process_log_entry(log_entry)
            
            # Update statistics
            with self._lock:
                for log_entry in batch:
                    self._update_statistics(log_entry)
            
            logger.debug(f"Processed audit log batch: {len(batch)} entries")
            
        except Exception as e:
            logger.error(f"Failed to process audit log batch: {str(e)}")
            self.statistics['failed_logs'] += len(batch)
    
    def _process_log_entry(self, log_entry: AuditLogEntry):
        """Process individual audit log entry."""
        try:
            # Sanitize sensitive data
            if not self.config.log_sensitive_data:
                log_entry = self._sanitize_log_entry(log_entry)
            
            # Apply custom handlers
            for handler in self._log_handlers:
                try:
                    handler(log_entry)
                except Exception as e:
                    logger.error(f"Custom log handler failed: {str(e)}")
            
            # Store log entry (this would typically save to database)
            self._store_log_entry(log_entry)
            
        except Exception as e:
            logger.error(f"Failed to process audit log entry: {str(e)}")
            raise
    
    def _sanitize_log_entry(self, log_entry: AuditLogEntry) -> AuditLogEntry:
        """Sanitize sensitive data from log entry."""
        sensitive_fields = self.config.sensitive_fields
        
        # Sanitize request data
        if log_entry.request_data:
            log_entry.request_data = self._sanitize_dict(log_entry.request_data, sensitive_fields)
        
        # Sanitize response data
        if log_entry.response_data:
            log_entry.response_data = self._sanitize_dict(log_entry.response_data, sensitive_fields)
        
        # Sanitize details
        if log_entry.details:
            log_entry.details = self._sanitize_dict(log_entry.details, sensitive_fields)
        
        # Sanitize metadata
        if log_entry.metadata:
            log_entry.metadata = self._sanitize_dict(log_entry.metadata, sensitive_fields)
        
        return log_entry
    
    def _sanitize_dict(self, data: Dict[str, Any], sensitive_fields: List[str]) -> Dict[str, Any]:
        """Sanitize dictionary by removing sensitive fields."""
        sanitized = {}
        
        for key, value in data.items():
            # Check if key contains sensitive field
            is_sensitive = any(
                sensitive_field in key.lower() 
                for sensitive_field in sensitive_fields
            )
            
            if is_sensitive:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value, sensitive_fields)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_dict(item, sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _store_log_entry(self, log_entry: AuditLogEntry):
        """Store audit log entry (simplified implementation)."""
        # This would typically save to database
        # For now, we'll just log it
        log_data = {
            'log_id': log_entry.log_id,
            'timestamp': log_entry.timestamp.isoformat(),
            'level': log_entry.level.value,
            'category': log_entry.category.value,
            'action': log_entry.action.value,
            'resource_type': log_entry.resource_type,
            'resource_id': log_entry.resource_id,
            'user_id': log_entry.user_id,
            'ip_address': log_entry.ip_address,
            'message': log_entry.message,
            'compliance_relevant': log_entry.compliance_relevant
        }
        
        # Log based on level
        if log_entry.level == AuditLogLevel.CRITICAL or log_entry.level == AuditLogLevel.SECURITY:
            logger.critical(f"AUDIT: {json.dumps(log_data)}")
        elif log_entry.level == AuditLogLevel.ERROR:
            logger.error(f"AUDIT: {json.dumps(log_data)}")
        elif log_entry.level == AuditLogLevel.WARNING:
            logger.warning(f"AUDIT: {json.dumps(log_data)}")
        else:
            logger.info(f"AUDIT: {json.dumps(log_data)}")
    
    def _update_statistics(self, log_entry: AuditLogEntry):
        """Update audit statistics."""
        self.statistics['total_logs'] += 1
        self.statistics['last_log_time'] = log_entry.timestamp
        
        # Update level statistics
        level_name = log_entry.level.value
        if level_name not in self.statistics['logs_by_level']:
            self.statistics['logs_by_level'][level_name] = 0
        self.statistics['logs_by_level'][level_name] += 1
        
        # Update category statistics
        category_name = log_entry.category.value
        if category_name not in self.statistics['logs_by_category']:
            self.statistics['logs_by_category'][category_name] = 0
        self.statistics['logs_by_category'][category_name] += 1
        
        # Update action statistics
        action_name = log_entry.action.value
        if action_name not in self.statistics['logs_by_action']:
            self.statistics['logs_by_action'][action_name] = 0
        self.statistics['logs_by_action'][action_name] += 1
        
        # Update compliance logs
        if log_entry.compliance_relevant:
            self.statistics['compliance_logs'] += 1
    
    def _get_logs_to_archive(self) -> List[str]:
        """Get logs to archive."""
        # This would query database for logs older than archive threshold
        # For now, return empty list
        return []
    
    def _archive_logs(self, log_ids: List[str]):
        """Archive audit logs."""
        try:
            # This would move logs to archive storage
            archived_count = len(log_ids)
            self.statistics['archived_logs'] += archived_count
            
            logger.info(f"Archived {archived_count} audit logs")
            
        except Exception as e:
            logger.error(f"Failed to archive logs: {str(e)}")
    
    def log_event(self, level: AuditLogLevel, category: AuditCategory, action: AuditAction,
                  resource_type: str, resource_id: str = None, message: str = "", **kwargs):
        """Log an audit event."""
        log_entry = AuditLogEntry(
            log_id=f"audit_{timezone.now().timestamp()}",
            timestamp=timezone.now(),
            level=level,
            category=category,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=kwargs.get('user_id'),
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            session_id=kwargs.get('session_id'),
            correlation_id=kwargs.get('correlation_id'),
            message=message,
            details=kwargs.get('details', {}),
            request_data=kwargs.get('request_data', {}),
            response_data=kwargs.get('response_data', {}),
            metadata=kwargs.get('metadata', {}),
            compliance_relevant=kwargs.get('compliance_relevant', False),
            retention_days=kwargs.get('retention_days', self.config.default_retention_days)
        )
        
        try:
            self.log_queue.put(log_entry, timeout=1)
        except Exception as e:
            logger.error(f"Failed to queue audit log: {str(e)}")
            self.statistics['failed_logs'] += 1
    
    def log_integration_event(self, event_type: IntegrationEvent, status: IntegrationStatus,
                            user_id: str = None, ip_address: str = None, **kwargs):
        """Log integration event."""
        self.log_event(
            level=AuditLogLevel.INFO,
            category=AuditCategory.INTEGRATION,
            action=AuditAction.EXECUTE,
            resource_type="integration",
            resource_id=event_type.value,
            message=f"Integration event: {event_type.value} - {status.value}",
            user_id=user_id,
            ip_address=ip_address,
            details={
                'event_type': event_type.value,
                'status': status.value,
                'priority': kwargs.get('priority', IntegrationPriority.NORMAL).value
            },
            compliance_relevant=event_type in [
                IntegrationEvent.ABUSE_DETECTED,
                IntegrationEvent.IP_BLOCKED,
                IntegrationEvent.SANCTION_APPLIED,
                IntegrationEvent.DATA_INTEGRITY,
                IntegrationEvent.COMPLIANCE_EVENT
            ],
            **kwargs
        )
    
    def log_security_event(self, action: AuditAction, resource_type: str, resource_id: str = None,
                         user_id: str = None, ip_address: str = None, message: str = "", **kwargs):
        """Log security event."""
        self.log_event(
            level=AuditLogLevel.SECURITY,
            category=AuditCategory.SECURITY,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            message=message,
            compliance_relevant=True,
            **kwargs
        )
    
    def log_compliance_event(self, action: AuditAction, resource_type: str, resource_id: str = None,
                           user_id: str = None, message: str = "", **kwargs):
        """Log compliance event."""
        self.log_event(
            level=AuditLogLevel.INFO,
            category=AuditCategory.COMPLIANCE,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            message=message,
            compliance_relevant=True,
            **kwargs
        )
    
    def log_data_access(self, action: AuditAction, resource_type: str, resource_id: str = None,
                       user_id: str = None, ip_address: str = None, **kwargs):
        """Log data access event."""
        self.log_event(
            level=AuditLogLevel.INFO,
            category=AuditCategory.DATA_ACCESS,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            message=f"Data access: {action.value} on {resource_type}",
            **kwargs
        )
    
    def log_configuration_change(self, action: AuditAction, resource_type: str, resource_id: str = None,
                                user_id: str = None, old_values: Dict[str, Any] = None,
                                new_values: Dict[str, Any] = None, **kwargs):
        """Log configuration change."""
        self.log_event(
            level=AuditLogLevel.WARNING,
            category=AuditCategory.CONFIGURATION,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            message=f"Configuration change: {action.value} on {resource_type}",
            details={
                'old_values': old_values or {},
                'new_values': new_values or {}
            },
            compliance_relevant=True,
            **kwargs
        )
    
    def search_logs(self, criteria: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search audit logs."""
        # This would query the database
        # For now, return empty list
        return []
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'queue_size': self.log_queue.qsize(),
                'archive_queue_size': self.archive_queue.qsize(),
                'running': self._running,
                'uptime_hours': (timezone.now() - stats['start_time']).total_seconds() / 3600
            })
            return stats
    
    def register_log_handler(self, handler: Callable):
        """Register custom log handler."""
        self._log_handlers.append(handler)
        logger.info("Registered custom audit log handler")
    
    def cleanup_old_logs(self, older_than_days: int = None) -> int:
        """Clean up old audit logs."""
        cleanup_days = older_than_days or self.config.default_retention_days
        cutoff_date = timezone.now() - timedelta(days=cleanup_days)
        
        # This would delete old logs from database
        # For now, return 0
        logger.info(f"Cleaned up audit logs older than {cleanup_days} days")
        return 0
    
    def export_logs(self, format: str = "json", criteria: Dict[str, Any] = None,
                   limit: int = 10000) -> str:
        """Export audit logs."""
        logs = self.search_logs(criteria, limit)
        
        if format == "json":
            return json.dumps(logs, indent=2, default=str)
        elif format == "csv":
            return self._export_to_csv(logs)
        else:
            raise IntegrationError(f"Unsupported export format: {format}")
    
    def _export_to_csv(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs to CSV format."""
        import csv
        import io
        
        if not logs:
            return ""
        
        output = io.StringIO()
        
        # Get all possible fields
        all_fields = set()
        for log in logs:
            all_fields.update(log.keys())
        
        fieldnames = sorted(all_fields)
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for log in logs:
            writer.writerow(log)
        
        return output.getvalue()
    
    def shutdown(self):
        """Shutdown audit logging system."""
        logger.info("Shutting down audit logging system...")
        
        self._running = False
        
        # Wait for threads to finish
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        
        if self._archive_thread:
            self._archive_thread.join(timeout=5)
        
        # Process remaining logs
        remaining_logs = []
        while not self.log_queue.empty():
            try:
                log_entry = self.log_queue.get_nowait()
                remaining_logs.append(log_entry)
            except Empty:
                break
        
        if remaining_logs:
            self._process_log_batch(remaining_logs)
        
        logger.info("Audit logging system shutdown complete")


# Global audit logger instance
audit_logger = AuditLogger()


# Decorators for audit logging
def audit_log_event(category: AuditCategory, action: AuditAction, resource_type: str,
                   message: str = "", level: AuditLogLevel = AuditLogLevel.INFO):
    """Decorator to audit log function calls."""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Extract context from request
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = str(request.user.id)
            
            ip_address = getattr(request, 'ip_address', None)
            if not ip_address and hasattr(request, 'META'):
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Log the event
            audit_logger.log_event(
                level=level,
                category=category,
                action=action,
                resource_type=resource_type,
                resource_id=kwargs.get('id'),
                user_id=user_id,
                ip_address=ip_address,
                message=message or f"{action.value} on {resource_type}",
                request_data=getattr(request, 'data', {}),
                details={'function': func.__name__, 'args': args, 'kwargs': kwargs}
            )
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def audit_log_integration(event_type: IntegrationEvent, message: str = ""):
    """Decorator to audit log integration events."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = timezone.now()
            
            try:
                result = func(*args, **kwargs)
                status = IntegrationStatus.SUCCESS
                return result
            except Exception as e:
                status = IntegrationStatus.FAILED
                raise
            finally:
                # Log integration event
                audit_logger.log_integration_event(
                    event_type=event_type,
                    status=status,
                    message=message,
                    execution_time=(timezone.now() - start_time).total_seconds()
                )
        
        return wrapper
    return decorator


def audit_log_security(action: AuditAction, resource_type: str, message: str = ""):
    """Decorator to audit log security events."""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Extract context from request
            user_id = getattr(request, 'user_id', None)
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = str(request.user.id)
            
            ip_address = getattr(request, 'ip_address', None)
            if not ip_address and hasattr(request, 'META'):
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Log security event
            audit_logger.log_security_event(
                action=action,
                resource_type=resource_type,
                resource_id=kwargs.get('id'),
                user_id=user_id,
                ip_address=ip_address,
                message=message or f"Security event: {action.value} on {resource_type}",
                details={'function': func.__name__, 'args': args, 'kwargs': kwargs}
            )
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# Convenience functions
def log_authentication_event(user_id: str, action: str, success: bool, ip_address: str = None):
    """Log authentication event."""
    audit_logger.log_event(
        level=AuditLogLevel.INFO if success else AuditLogLevel.WARNING,
        category=AuditCategory.AUTHENTICATION,
        action=AuditAction.LOGIN if action == 'login' else AuditAction.LOGOUT,
        resource_type="user",
        resource_id=user_id,
        user_id=user_id,
        ip_address=ip_address,
        message=f"Authentication {action}: {'success' if success else 'failed'}",
        compliance_relevant=True
    )


def log_data_access_event(user_id: str, resource_type: str, resource_id: str, 
                         action: str = "read", ip_address: str = None):
    """Log data access event."""
    audit_action = AuditAction.READ if action == "read" else AuditAction.UPDATE if action == "update" else AuditAction.DELETE
    
    audit_logger.log_data_access(
        action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        ip_address=ip_address
    )
