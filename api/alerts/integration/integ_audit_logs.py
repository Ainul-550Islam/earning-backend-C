"""
Integration Audit Logs for alerts app - Comprehensive logging and audit trail
"""
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import json
import logging
import uuid
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Audit event types"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    INTEGRATION_CREATED = "integration_created"
    INTEGRATION_UPDATED = "integration_updated"
    INTEGRATION_DELETED = "integration_deleted"
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    DATA_SENT = "data_sent"
    DATA_RECEIVED = "data_received"
    ERROR_OCCURRED = "error_occurred"
    CONFIGURATION_CHANGED = "configuration_changed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    WEBHOOK_TRIGGERED = "webhook_triggered"
    ALERT_PROCESSED = "alert_processed"
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_RESTORE = "system_restore"
    # Members referenced by signals/*.py (they raised AttributeError, which the
    # callers swallowed, so these audit events were silently never written).
    RULE_CREATED = "rule_created"
    RULE_UPDATED = "rule_updated"
    ALERT_CREATED = "alert_created"
    INCIDENT_RESOLVED = "incident_resolved"
    SLA_BREACH_DETECTED = "sla_breach_detected"


class AuditSeverity(Enum):
    """Audit severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INFO = "info"
    WARNING = "warning"


def _enum_value(value):
    """Return ``value.value`` for Enum members, otherwise the value unchanged."""
    return value.value if isinstance(value, Enum) else value


def _coerce_enum(enum_cls, value):
    """Accept an Enum member, its value or its name; fall back to the raw value."""
    if value is None or isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value.lower())
        except ValueError:
            try:
                return enum_cls[value.upper()]
            except KeyError:
                return value
    return value


class AuditLogEntry:
    """Represents a single audit log entry"""
    
    def __init__(self, event_type: AuditEventType, severity: AuditSeverity, 
                 description: str, user_id: str = None, integration_name: str = None,
                 details: Dict[str, Any] = None, correlation_id: str = None):
        self.id = str(uuid.uuid4())
        self.event_type = _coerce_enum(AuditEventType, event_type)
        self.severity = _coerce_enum(AuditSeverity, severity)
        self.description = description
        self.user_id = user_id
        self.integration_name = integration_name
        self.details = details or {}
        self.correlation_id = correlation_id
        self.timestamp = timezone.now()
        self.ip_address = None
        self.user_agent = None
        self.session_id = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'event_type': _enum_value(self.event_type),
            'severity': _enum_value(self.severity),
            'description': self.description,
            'user_id': self.user_id,
            'integration_name': self.integration_name,
            'details': self.details,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'session_id': self.session_id
        }
    
    def add_context(self, request = None, **kwargs):
        """Add context information"""
        if request:
            self.ip_address = self._get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
            self.session_id = request.session.session_key if hasattr(request, 'session') else None
        
        # Add additional context
        for key, value in kwargs.items():
            self.details[key] = value
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR', 'unknown')


class AuditLogger:
    """Main audit logging system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.log_to_file = self.config.get('log_to_file', True)
        self.log_to_database = self.config.get('log_to_database', False)
        self.log_to_external = self.config.get('log_to_external', False)
        self.external_endpoint = self.config.get('external_endpoint')
        self.max_entries = self.config.get('max_entries', 10000)
        self.cache_timeout = self.config.get('cache_timeout', 3600)  # 1 hour
        
        # Initialize storage
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize storage backends"""
        self.file_path = self.config.get('file_path', 'logs/audit.log')
        self.cache_prefix = 'audit_logs'
        
        # Ensure log directory exists
        if self.log_to_file:
            import os
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
    
    def log_event(self, event_type: AuditEventType, severity: AuditSeverity,
                  description: str, user_id: str = None, integration_name: str = None,
                  details: Dict[str, Any] = None, request = None, **kwargs):
        """Log an audit event"""
        if not self.enabled:
            return
        
        try:
            # Create audit entry
            entry = AuditLogEntry(
                event_type=event_type,
                severity=severity,
                description=description,
                user_id=user_id,
                integration_name=integration_name,
                details=details,
                correlation_id=kwargs.get('correlation_id')
            )
            
            # Add context
            entry.add_context(request, **kwargs)
            
            # Store entry
            self._store_entry(entry)
            
            logger.debug(f"Audit event logged: {entry.id} - {description}")
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def _store_entry(self, entry: AuditLogEntry):
        """Store audit entry in all configured backends"""
        entry_dict = entry.to_dict()
        
        # Store in cache
        if self.cache_timeout > 0:
            cache_key = f"{self.cache_prefix}_{entry.id}"
            cache.set(cache_key, entry_dict, timeout=self.cache_timeout)
        
        # Store in file
        if self.log_to_file:
            self._store_in_file(entry_dict)
        
        # Store in database (if configured)
        if self.log_to_database:
            self._store_in_database(entry_dict)
        
        # Send to external endpoint (if configured)
        if self.log_to_external:
            self._send_to_external(entry_dict)
    
    def _store_in_file(self, entry: Dict[str, Any]):
        """Store entry in log file"""
        try:
            import json
            
            log_line = json.dumps(entry) + '\n'
            
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
                
        except Exception as e:
            logger.error(f"Error storing audit entry in file: {e}")
    
    def _store_in_database(self, entry: Dict[str, Any]):
        """Store entry in database"""
        try:
            # This would store in a database table
            # For now, just log the attempt
            logger.info(f"Would store audit entry in database: {entry['id']}")
            
        except Exception as e:
            logger.error(f"Error storing audit entry in database: {e}")
    
    def _send_to_external(self, entry: Dict[str, Any]):
        """Send entry to external endpoint"""
        try:
            import requests
            
            response = requests.post(
                self.external_endpoint,
                json=entry,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code != 200:
                logger.warning(f"External audit log endpoint returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending audit entry to external endpoint: {e}")
    
    def get_entries(self, limit: int = 100, event_type: AuditEventType = None,
                   severity: AuditSeverity = None, user_id: str = None,
                   integration_name: str = None, start_time = None, end_time = None) -> List[Dict[str, Any]]:
        """Get audit entries with filters"""
        try:
            # Try to get from cache first
            cache_key = f"{self.cache_prefix}_filtered_{hash(str(limit) + str(event_type) + str(severity) + str(user_id) + str(integration_name) + str(start_time) + str(end_time))}"
            cached_entries = cache.get(cache_key)
            
            if cached_entries:
                return cached_entries
            
            # Get entries from storage
            entries = self._get_entries_from_storage(
                limit, event_type, severity, user_id, integration_name, start_time, end_time
            )
            
            # Cache the result
            cache.set(cache_key, entries, timeout=300)  # 5 minutes
            
            return entries
            
        except Exception as e:
            logger.error(f"Error getting audit entries: {e}")
            return []
    
    def _get_entries_from_storage(self, limit: int, event_type: AuditEventType = None,
                               severity: AuditSeverity = None, user_id: str = None,
                               integration_name: str = None, start_time = None, end_time = None) -> List[Dict[str, Any]]:
        """Get entries from storage backends"""
        entries = []
        
        # If file logging is enabled, read from file
        if self.log_to_file:
            entries.extend(self._get_entries_from_file(limit, event_type, severity, user_id, integration_name, start_time, end_time))
        
        # Sort by timestamp (newest first)
        entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Apply limit
        return entries[:limit]
    
    def _get_entries_from_file(self, limit: int, event_type: AuditEventType = None,
                              severity: AuditSeverity = None, user_id: str = None,
                              integration_name: str = None, start_time = None, end_time = None) -> List[Dict[str, Any]]:
        """Get entries from log file"""
        try:
            import json
            
            entries = []
            
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line.strip())
                            
                            # Apply filters
                            if self._matches_filters(entry, event_type, severity, user_id, integration_name, start_time, end_time):
                                entries.append(entry)
            except FileNotFoundError:
                logger.warning(f"Audit log file not found: {self.file_path}")
                return []
            
            return entries
            
        except Exception as e:
            logger.error(f"Error reading audit log file: {e}")
            return []
    
    def _matches_filters(self, entry: Dict[str, Any], event_type: AuditEventType = None,
                       severity: AuditSeverity = None, user_id: str = None,
                       integration_name: str = None, start_time = None, end_time = None) -> bool:
        """Check if entry matches all filters"""
        # Event type filter
        if event_type and entry.get('event_type') != _enum_value(event_type):
            return False
        
        # Severity filter
        if severity and entry.get('severity') != _enum_value(severity):
            return False
        
        # User ID filter
        if user_id and entry.get('user_id') != user_id:
            return False
        
        # Integration name filter
        if integration_name and entry.get('integration_name') != integration_name:
            return False
        
        # Time range filter
        entry_time = timezone.datetime.fromisoformat(entry.get('timestamp', ''))
        
        if start_time and entry_time < start_time:
            return False
        
        if end_time and entry_time > end_time:
            return False
        
        return True
    
    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit entry by ID"""
        try:
            cache_key = f"{self.cache_prefix}_{entry_id}"
            entry = cache.get(cache_key)
            
            if entry:
                return entry
            
            # Search in storage
            entries = self.get_entries(limit=1000)
            for entry in entries:
                if entry.get('id') == entry_id:
                    cache.set(cache_key, entry, timeout=self.cache_timeout)
                    return entry
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting audit entry by ID: {e}")
            return None
    
    def get_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get audit statistics for time window"""
        try:
            end_time = timezone.now()
            start_time = end_time - timezone.timedelta(hours=time_window_hours)
            
            entries = self.get_entries(
                limit=10000,
                start_time=start_time,
                end_time=end_time
            )
            
            # Calculate statistics
            stats = {
                'time_window_hours': time_window_hours,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_entries': len(entries),
                'event_types': {},
                'severities': {},
                'users': {},
                'integrations': {},
                'top_events': [],
                'critical_events': []
            }
            
            # Count by event type
            for entry in entries:
                event_type = entry.get('event_type', 'unknown')
                severity = entry.get('severity', 'unknown')
                user_id = entry.get('user_id', 'anonymous')
                integration_name = entry.get('integration_name', 'none')
                
                # Event type counts
                stats['event_types'][event_type] = stats['event_types'].get(event_type, 0) + 1
                
                # Severity counts
                stats['severities'][severity] = stats['severities'].get(severity, 0) + 1
                
                # User counts
                stats['users'][user_id] = stats['users'].get(user_id, 0) + 1
                
                # Integration counts
                stats['integrations'][integration_name] = stats['integrations'].get(integration_name, 0) + 1
                
                # Critical events
                if severity == AuditSeverity.CRITICAL.value:
                    stats['critical_events'].append(entry)
            
            # Top events (by frequency)
            sorted_events = sorted(stats['event_types'].items(), key=lambda x: x[1], reverse=True)
            stats['top_events'] = sorted_events[:10]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating audit statistics: {e}")
            return {}
    
    def cleanup_old_entries(self, days_to_keep: int = 90):
        """Clean up old audit entries"""
        try:
            cutoff_time = timezone.now() - timezone.timedelta(days=days_to_keep)
            
            if self.log_to_file:
                self._cleanup_file_entries(cutoff_time)
            
            # Clean up cache
            self._cleanup_cache_entries(cutoff_time)
            
            logger.info(f"Cleaned up audit entries older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up audit entries: {e}")
    
    def _cleanup_file_entries(self, cutoff_time: timezone.datetime):
        """Clean up old entries from file"""
        try:
            import json
            import tempfile
            import os
            
            # Read and filter entries
            valid_entries = []
            
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line.strip())
                            entry_time = timezone.datetime.fromisoformat(entry.get('timestamp', ''))
                            
                            if entry_time > cutoff_time:
                                valid_entries.append(line.strip())
            except FileNotFoundError:
                return
            
            # Write back valid entries
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                temp_file.write('\n'.join(valid_entries))
                temp_file_path = temp_file.name
            
            # Replace original file
            os.replace(temp_file_path, self.file_path)
            
        except Exception as e:
            logger.error(f"Error cleaning up file entries: {e}")
    
    def _cleanup_cache_entries(self, cutoff_time: timezone.datetime):
        """Clean up old entries from cache"""
        try:
            # This is a simplified cleanup - in production, you'd iterate through cache keys
            cache_keys_pattern = f"{self.cache_prefix}_*"
            # Implementation depends on cache backend
            logger.info(f"Would clean up cache entries older than {cutoff_time}")
            
        except Exception as e:
            logger.error(f"Error cleaning up cache entries: {e}")


# Global audit logger
audit_logger = None


def get_audit_logger() -> Optional[AuditLogger]:
    """Get the global audit logger"""
    return audit_logger


def initialize_audit_logging():
    """Initialize audit logging from settings"""
    from django.conf import settings
    
    global audit_logger
    
    config = getattr(settings, 'AUDIT_LOGGING_CONFIG', {
        'enabled': True,
        'log_to_file': True,
        'log_to_database': False,
        'log_to_external': False,
        'file_path': 'logs/audit.log',
        'max_entries': 10000,
        'cache_timeout': 3600
    })
    
    try:
        audit_logger = AuditLogger(config)
        logger.info("Audit logging system initialized")
    except Exception as e:
        logger.error(f"Error initializing audit logging: {e}")


# Log a single audit event immediately (no-op if audit logging isn't
# initialized). This is the calling convention used throughout the codebase,
# e.g. AuditLogViewSet.log_event(): audit_event(event_type=..., message=..., user=...)
def audit_event(event_type, message: str = "", user: str = None,
                 severity: AuditSeverity = AuditSeverity.MEDIUM, **kwargs):
    """Log an audit event via the global audit logger, if initialized."""
    if audit_logger:
        audit_logger.log_event(
            event_type=event_type,
            severity=severity,
            description=message,
            user_id=user,
            **kwargs
        )


# Convenience functions for common audit events
def log_user_login(user_id: str, request = None, **kwargs):
    """Log user login event"""
    if audit_logger:
        audit_logger.log_event(
            event_type=AuditEventType.USER_LOGIN,
            severity=AuditSeverity.MEDIUM,
            description=f"User {user_id} logged in",
            user_id=user_id,
            request=request,
            **kwargs
        )


def log_user_logout(user_id: str, request = None, **kwargs):
    """Log user logout event"""
    if audit_logger:
        audit_logger.log_event(
            event_type=AuditEventType.USER_LOGOUT,
            severity=AuditSeverity.MEDIUM,
            description=f"User {user_id} logged out",
            user_id=user_id,
            request=request,
            **kwargs
        )


def log_integration_event(event_type: AuditEventType, integration_name: str, 
                        severity: AuditSeverity = AuditSeverity.MEDIUM, **kwargs):
    """Log integration-related event"""
    if audit_logger:
        audit_logger.log_event(
            event_type=event_type,
            severity=severity,
            description=f"Integration {integration_name} {_enum_value(event_type).replace('_', ' ')}",
            integration_name=integration_name,
            **kwargs
        )


def log_error_event(error_message: str, integration_name: str = None, 
                   severity: AuditSeverity = AuditSeverity.HIGH, **kwargs):
    """Log error event"""
    if audit_logger:
        audit_logger.log_event(
            event_type=AuditEventType.ERROR_OCCURRED,
            severity=severity,
            description=error_message,
            integration_name=integration_name,
            details={'error_message': error_message},
            **kwargs
        )


def log_data_event(event_type: AuditEventType, data_info: Dict[str, Any], 
                  severity: AuditSeverity = AuditSeverity.LOW, **kwargs):
    """Log data transfer event"""
    if audit_logger:
        audit_logger.log_event(
            event_type=event_type,
            severity=severity,
            description=f"Data {_enum_value(event_type).replace('_', ' ')}",
            details=data_info,
            **kwargs
        )


# Initialize on module import
try:
    initialize_audit_logging()
except Exception as e:
    logger.error(f"Error initializing audit logging: {e}")
