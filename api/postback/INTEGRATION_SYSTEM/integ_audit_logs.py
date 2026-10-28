"""
integ_audit_logs.py – Integration audit logs for postback module.

Provides comprehensive audit logging functionality including:
- Integration event logging
- Security audit trails
- Compliance logging
- Audit log management and retention
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import hashlib
import threading
from collections import deque

from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationEventType, IntegrationLogLevel
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditAction(Enum):
    """Audit action enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_DENIED = "access_denied"
    CONFIG_CHANGE = "config_change"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ERROR = "error"
    WARNING = "warning"
    SECURITY_EVENT = "security_event"


class AuditResource(Enum):
    """Audit resource enumeration."""
    INTEGRATION = "integration"
    WEBHOOK = "webhook"
    API_ENDPOINT = "api_endpoint"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    EVENT_BUS = "event_bus"


class AuditSeverity(Enum):
    """Audit severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditLog:
    """Audit log entry data structure."""
    id: str
    action: AuditAction
    resource: AuditResource
    resource_id: Optional[str]
    user_id: Optional[int]
    user_email: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime = field(default_factory=timezone.now)
    details: Dict[str, Any] = field(default_factory=dict)
    severity: AuditSeverity = AuditSeverity.MEDIUM
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'action': self.action.value,
            'resource': self.resource.value,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'severity': self.severity.value,
            'correlation_id': self.correlation_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'status_code': self.status_code,
            'error_message': self.error_message,
            'metadata': self.metadata,
        }
    
    def generate_hash(self) -> str:
        """Generate hash for audit log."""
        content = json.dumps({
            'action': self.action.value,
            'resource': self.resource.value,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
        }, sort_keys=True)
        
        return hashlib.sha256(content.encode()).hexdigest()


class AuditLogger:
    """
    Audit logger for integration system.
    
    Handles audit log creation, storage, and management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audit_logs: deque = deque(maxlen=10000)  # In-memory storage
        self.lock = threading.Lock()
        self.retention_days = getattr(settings, 'AUDIT_LOG_RETENTION_DAYS', 90)
        self.enable_persistence = getattr(settings, 'AUDIT_LOG_PERSISTENCE', True)
        self.enable_compression = getattr(settings, 'AUDIT_LOG_COMPRESSION', True)
        self._setup_audit_handlers()
    
    def _setup_audit_handlers(self):
        """Setup audit log handlers."""
        # This would setup database storage, file storage, etc.
        pass
    
    def log_action(self, action: AuditAction, resource: AuditResource,
                   resource_id: str = None, user_id: int = None,
                   user_email: str = None, ip_address: str = None,
                   user_agent: str = None, details: Dict[str, Any] = None,
                   severity: AuditSeverity = AuditSeverity.MEDIUM,
                   correlation_id: str = None, session_id: str = None,
                   request_id: str = None, status_code: int = None,
                   error_message: str = None, metadata: Dict[str, Any] = None) -> str:
        """
        Log audit action.
        
        Args:
            action: Action performed
            resource: Resource type
            resource_id: Resource identifier
            user_id: User ID
            user_email: User email
            ip_address: IP address
            user_agent: User agent string
            details: Additional details
            severity: Log severity
            correlation_id: Correlation ID
            session_id: Session ID
            request_id: Request ID
            status_code: HTTP status code
            error_message: Error message
            metadata: Additional metadata
            
        Returns:
            Audit log ID
        """
        import uuid
        
        audit_log = AuditLog(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            action=action,
            resource=resource,
            resource_id=resource_id,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            severity=severity,
            correlation_id=correlation_id,
            session_id=session_id,
            request_id=request_id,
            status_code=status_code,
            error_message=error_message,
            metadata=metadata or {}
        )
        
        # Store audit log
        with self.lock:
            self.audit_logs.append(audit_log)
        
        # Persist if enabled
        if self.enable_persistence:
            self._persist_audit_log(audit_log)
        
        # Log to system logger for critical events
        if severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
            self.logger.warning(
                f"Audit Event: {action.value} on {resource.value} - {resource_id or 'N/A'}",
                extra={'audit_log': audit_log.to_dict()}
            )
        
        return audit_log.id
    
    def _persist_audit_log(self, audit_log: AuditLog):
        """Persist audit log to storage."""
        try:
            # This would typically save to database
            # For now, just cache the log
            cache_key = f"audit_log_{audit_log.id}"
            cache.set(cache_key, audit_log.to_dict(), timeout=86400 * self.retention_days)
        
        except Exception as e:
            self.logger.error(f"Failed to persist audit log {audit_log.id}: {str(e)}")
    
    def get_audit_log(self, log_id: str) -> Optional[AuditLog]:
        """
        Get audit log by ID.
        
        Args:
            log_id: Audit log ID
            
        Returns:
            Audit log or None
        """
        # Check in-memory first
        with self.lock:
            for log in self.audit_logs:
                if log.id == log_id:
                    return log
        
        # Check cache
        cache_key = f"audit_log_{log_id}"
        cached_log = cache.get(cache_key)
        if cached_log:
            # Reconstruct audit log from cached data
            return AuditLog(
                id=cached_log['id'],
                action=AuditAction(cached_log['action']),
                resource=AuditResource(cached_log['resource']),
                resource_id=cached_log['resource_id'],
                user_id=cached_log['user_id'],
                user_email=cached_log['user_email'],
                ip_address=cached_log['ip_address'],
                user_agent=cached_log['user_agent'],
                timestamp=datetime.fromisoformat(cached_log['timestamp']),
                details=cached_log['details'],
                severity=AuditSeverity(cached_log['severity']),
                correlation_id=cached_log['correlation_id'],
                session_id=cached_log['session_id'],
                request_id=cached_log['request_id'],
                status_code=cached_log['status_code'],
                error_message=cached_log['error_message'],
                metadata=cached_log['metadata'],
            )
        
        return None
    
    def search_audit_logs(self, action: AuditAction = None, resource: AuditResource = None,
                          resource_id: str = None, user_id: int = None,
                          start_date: datetime = None, end_date: datetime = None,
                          severity: AuditSeverity = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search audit logs.
        
        Args:
            action: Filter by action
            resource: Filter by resource
            resource_id: Filter by resource ID
            user_id: Filter by user ID
            start_date: Start date filter
            end_date: End date filter
            severity: Filter by severity
            limit: Maximum number of results
            
        Returns:
            List of audit logs
        """
        with self.lock:
            filtered_logs = list(self.audit_logs)
        
        # Apply filters
        if action:
            filtered_logs = [log for log in filtered_logs if log.action == action]
        
        if resource:
            filtered_logs = [log for log in filtered_logs if log.resource == resource]
        
        if resource_id:
            filtered_logs = [log for log in filtered_logs if log.resource_id == resource_id]
        
        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]
        
        if start_date:
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_date]
        
        if end_date:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_date]
        
        if severity:
            filtered_logs = [log for log in filtered_logs if log.severity == severity]
        
        # Sort by timestamp (newest first)
        filtered_logs.sort(key=lambda log: log.timestamp, reverse=True)
        
        # Limit results
        filtered_logs = filtered_logs[:limit]
        
        return [log.to_dict() for log in filtered_logs]
    
    def get_user_activity(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get user activity audit logs.
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            List of user's audit logs
        """
        start_date = timezone.now() - timedelta(days=days)
        
        return self.search_audit_logs(
            user_id=user_id,
            start_date=start_date,
            limit=1000
        )
    
    def get_resource_activity(self, resource: AuditResource, resource_id: str = None,
                             days: int = 30) -> List[Dict[str, Any]]:
        """
        Get resource activity audit logs.
        
        Args:
            resource: Resource type
            resource_id: Resource ID
            days: Number of days to look back
            
        Returns:
            List of resource's audit logs
        """
        start_date = timezone.now() - timedelta(days=days)
        
        return self.search_audit_logs(
            resource=resource,
            resource_id=resource_id,
            start_date=start_date,
            limit=1000
        )
    
    def get_security_events(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get security-related audit logs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of security audit logs
        """
        start_date = timezone.now() - timedelta(days=days)
        
        security_actions = [
            AuditAction.LOGIN,
            AuditAction.LOGOUT,
            AuditAction.ACCESS_DENIED,
            AuditAction.SECURITY_EVENT,
        ]
        
        security_logs = []
        for action in security_actions:
            logs = self.search_audit_logs(
                action=action,
                start_date=start_date,
                limit=1000
            )
            security_logs.extend(logs)
        
        # Sort by timestamp (newest first)
        security_logs.sort(key=lambda log: log['timestamp'], reverse=True)
        
        return security_logs[:1000]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        with self.lock:
            total_logs = len(self.audit_logs)
        
        if total_logs == 0:
            return {
                'total_logs': 0,
                'logs_by_action': {},
                'logs_by_resource': {},
                'logs_by_severity': {},
                'logs_by_user': {},
                'recent_activity': [],
            }
        
        # Count by action
        action_counts = {}
        for log in self.audit_logs:
            action = log.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Count by resource
        resource_counts = {}
        for log in self.audit_logs:
            resource = log.resource.value
            resource_counts[resource] = resource_counts.get(resource, 0) + 1
        
        # Count by severity
        severity_counts = {}
        for log in self.audit_logs:
            severity = log.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by user
        user_counts = {}
        for log in self.audit_logs:
            if log.user_id:
                user_id = log.user_id
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        # Recent activity (last 24 hours)
        recent_cutoff = timezone.now() - timedelta(hours=24)
        recent_activity = []
        for log in self.audit_logs:
            if log.timestamp >= recent_cutoff:
                recent_activity.append(log.to_dict())
        
        recent_activity.sort(key=lambda log: log['timestamp'], reverse=True)
        recent_activity = recent_activity[:100]
        
        return {
            'total_logs': total_logs,
            'logs_by_action': action_counts,
            'logs_by_resource': resource_counts,
            'logs_by_severity': severity_counts,
            'logs_by_user': user_counts,
            'recent_activity_count': len(recent_activity),
            'recent_activity': recent_activity[:20],  # Last 20 for summary
        }
    
    def cleanup_old_logs(self) -> int:
        """
        Clean up old audit logs based on retention policy.
        
        Returns:
            Number of logs cleaned up
        """
        cutoff_date = timezone.now() - timedelta(days=self.retention_days)
        
        with self.lock:
            original_count = len(self.audit_logs)
            self.audit_logs = deque(
                [log for log in self.audit_logs if log.timestamp >= cutoff_date],
                maxlen=10000
            )
            cleaned_count = original_count - len(self.audit_logs)
        
        # Clean up cache
        # This would typically clean up database records as well
        
        self.logger.info(f"Cleaned up {cleaned_count} old audit logs")
        return cleaned_count
    
    def export_audit_logs(self, format_type: str = 'json', start_date: datetime = None,
                          end_date: datetime = None, filters: Dict[str, Any] = None) -> str:
        """
        Export audit logs.
        
        Args:
            format_type: Export format (json, csv)
            start_date: Start date
            end_date: End date
            filters: Additional filters
            
        Returns:
            Exported data
        """
        filters = filters or {}
        
        # Get logs based on filters
        logs = self.search_audit_logs(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        if format_type == 'json':
            return json.dumps(logs, indent=2, default=str)
        elif format_type == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            if logs:
                fieldnames = logs[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(logs)
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def verify_audit_trail(self, resource_id: str, expected_actions: List[AuditAction]) -> bool:
        """
        Verify audit trail for resource.
        
        Args:
            resource_id: Resource ID
            expected_actions: Expected actions
            
        Returns:
            True if audit trail is complete
        """
        logs = self.search_audit_logs(
            resource_id=resource_id,
            limit=1000
        )
        
        found_actions = {AuditAction(log['action']) for log in logs}
        
        for expected_action in expected_actions:
            if expected_action not in found_actions:
                self.logger.warning(f"Missing expected audit action: {expected_action.value}")
                return False
        
        return True


class ComplianceAuditor:
    """
    Compliance auditor for audit logs.
    
    Handles compliance checking and reporting.
    """
    
    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def check_gdpr_compliance(self, days: int = 30) -> Dict[str, Any]:
        """
        Check GDPR compliance.
        
        Args:
            days: Number of days to check
            
        Returns:
            Compliance report
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Get user-related audit logs
        user_logs = self.audit_logger.search_audit_logs(
            start_date=start_date,
            limit=10000
        )
        
        # Check for required GDPR audit events
        gdpr_events = {
            'data_processing': 0,
            'data_access': 0,
            'consent_records': 0,
            'data_deletion': 0,
            'access_requests': 0,
        }
        
        for log in user_logs:
            details = log.get('details', {})
            
            if 'data_processing' in details:
                gdpr_events['data_processing'] += 1
            if 'data_access' in details:
                gdpr_events['data_access'] += 1
            if 'consent' in details:
                gdpr_events['consent_records'] += 1
            if 'data_deletion' in details:
                gdpr_events['data_deletion'] += 1
            if 'access_request' in details:
                gdpr_events['access_requests'] += 1
        
        return {
            'compliant': all(count > 0 for count in gdpr_events.values()),
            'events': gdpr_events,
            'total_logs': len(user_logs),
            'period_days': days,
        }
    
    def check_sox_compliance(self, days: int = 90) -> Dict[str, Any]:
        """
        Check SOX compliance.
        
        Args:
            days: Number of days to check
            
        Returns:
            Compliance report
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Get financial/administrative audit logs
        sox_logs = self.audit_logger.search_audit_logs(
            start_date=start_date,
            limit=10000
        )
        
        # Check for required SOX controls
        sox_controls = {
            'access_control': 0,
            'change_management': 0,
            'data_integrity': 0,
            'segregation_of_duties': 0,
            'audit_trail': 0,
        }
        
        for log in sox_logs:
            details = log.get('details', {})
            
            if 'access_control' in details:
                sox_controls['access_control'] += 1
            if 'change_management' in details:
                sox_controls['change_management'] += 1
            if 'data_integrity' in details:
                sox_controls['data_integrity'] += 1
            if 'segregation_of_duties' in details:
                sox_controls['segregation_of_duties'] += 1
            if 'audit_trail' in details:
                sox_controls['audit_trail'] += 1
        
        return {
            'compliant': all(count > 0 for count in sox_controls.values()),
            'controls': sox_controls,
            'total_logs': len(sox_logs),
            'period_days': days,
        }
    
    def generate_compliance_report(self, standards: List[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            standards: Compliance standards to check
            
        Returns:
            Compliance report
        """
        standards = standards or ['gdpr', 'sox']
        
        report = {
            'generated_at': timezone.now().isoformat(),
            'standards': {},
            'overall_compliant': True,
        }
        
        for standard in standards:
            if standard == 'gdpr':
                report['standards']['gdpr'] = self.check_gdpr_compliance()
            elif standard == 'sox':
                report['standards']['sox'] = self.check_sox_compliance()
        
        # Check overall compliance
        for standard, result in report['standards'].items():
            if not result['compliant']:
                report['overall_compliant'] = False
        
        return report


# Global audit logger instance
audit_logger = AuditLogger()
compliance_auditor = ComplianceAuditor(audit_logger)


# Decorators for audit logging
def audit_action(action: AuditAction, resource: AuditResource, resource_id_param: str = None,
                 severity: AuditSeverity = AuditSeverity.MEDIUM):
    """
    Decorator for auditing function actions.
    
    Args:
        action: Action to log
        resource: Resource type
        resource_id_param: Parameter name containing resource ID
        severity: Log severity
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract request context if available
            request = None
            if args and hasattr(args[0], 'META'):
                request = args[0]
            
            # Get user information
            user_id = None
            user_email = None
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
                user_email = request.user.email
            
            # Get IP address and user agent
            ip_address = None
            user_agent = None
            if request:
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT')
            
            # Get resource ID
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = str(kwargs[resource_id_param])
            
            # Get correlation and request IDs
            correlation_id = kwargs.get('correlation_id')
            request_id = kwargs.get('request_id')
            
            # Log before execution
            log_id = audit_logger.log_action(
                action=action,
                resource=resource,
                resource_id=resource_id,
                user_id=user_id,
                user_email=user_email,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()),
                },
                severity=severity,
                correlation_id=correlation_id,
                request_id=request_id,
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful execution
                audit_logger.log_action(
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        'function': func.__name__,
                        'status': 'success',
                        'log_id': log_id,
                    },
                    severity=severity,
                    correlation_id=correlation_id,
                    request_id=request_id,
                )
                
                return result
            
            except Exception as e:
                # Log error
                audit_logger.log_action(
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        'function': func.__name__,
                        'status': 'error',
                        'error': str(e),
                        'log_id': log_id,
                    },
                    severity=AuditSeverity.HIGH,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    error_message=str(e),
                )
                
                raise
        
        return wrapper
    return decorator


# Convenience functions
def log_integration_event(action: AuditAction, resource: AuditResource, resource_id: str = None,
                        user_id: int = None, user_email: str = None, details: Dict[str, Any] = None):
    """Log integration event."""
    return audit_logger.log_action(
        action=action,
        resource=resource,
        resource_id=resource_id,
        user_id=user_id,
        user_email=user_email,
        details=details,
    )


def log_security_event(event_type: str, user_id: int = None, ip_address: str = None,
                       details: Dict[str, Any] = None, severity: AuditSeverity = AuditSeverity.HIGH):
    """Log security event."""
    return audit_logger.log_action(
        action=AuditAction.SECURITY_EVENT,
        resource=AuditResource.SYSTEM,
        user_id=user_id,
        ip_address=ip_address,
        details={
            'security_event_type': event_type,
            **(details or {})
        },
        severity=severity,
    )


def get_audit_statistics() -> Dict[str, Any]:
    """Get audit statistics."""
    return audit_logger.get_statistics()


def get_user_activity(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Get user activity."""
    return audit_logger.get_user_activity(user_id, days)


def get_security_events(days: int = 30) -> List[Dict[str, Any]]:
    """Get security events."""
    return audit_logger.get_security_events(days)


def generate_compliance_report(standards: List[str] = None) -> Dict[str, Any]:
    """Generate compliance report."""
    return compliance_auditor.generate_compliance_report(standards)
