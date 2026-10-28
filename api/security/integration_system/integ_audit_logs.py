"""
Integration Audit Logs Module
Audit logging for integration system
"""

import logging
import json
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import EventSeverity

User = get_user_model()
logger = logging.getLogger('security.integration.audit_logs')


class IntegrationAuditLogger:
    """Audit logger for integration system"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.log_level = EventSeverity.INFO
        self.retention_days = 90
        self.max_log_entries = 10000
        self.log_entries = []
        self.statistics = {
            'total_logs': 0,
            'logs_by_level': {},
            'logs_by_type': {},
            'last_log': None
        }
    
    def log_event(self, event_type: str, message: str, severity: EventSeverity = EventSeverity.INFO,
                  user: User = None, integration_name: str = None, 
                  metadata: Dict[str, Any] = None):
        """Log integration event"""
        if not self.enabled:
            return
        
        try:
            log_entry = {
                'id': SecurityUtils.generate_uuid(),
                'timestamp': timezone.now(),
                'event_type': event_type,
                'message': message,
                'severity': severity.value,
                'user_id': user.id if user else None,
                'username': user.username if user else None,
                'integration_name': integration_name,
                'logger_name': self.name,
                'metadata': metadata or {}
            }
            
            # Add to log entries
            self.log_entries.append(log_entry)
            
            # Maintain max entries
            if len(self.log_entries) > self.max_log_entries:
                self.log_entries.pop(0)
            
            # Update statistics
            self._update_statistics(log_entry)
            
            # Create security log entry
            self._create_security_log(log_entry)
            
        except Exception as e:
            logger.error(f"Error logging integration event: {e}")
    
    def _update_statistics(self, log_entry: Dict[str, Any]):
        """Update logging statistics"""
        self.statistics['total_logs'] += 1
        self.statistics['last_log'] = log_entry['timestamp']
        
        # Update level counts
        level = log_entry['severity']
        self.statistics['logs_by_level'][level] = self.statistics['logs_by_level'].get(level, 0) + 1
        
        # Update type counts
        event_type = log_entry['event_type']
        self.statistics['logs_by_type'][event_type] = self.statistics['logs_by_type'].get(event_type, 0) + 1
    
    def _create_security_log(self, log_entry: Dict[str, Any]):
        """Create security log entry"""
        try:
            SecurityLog.objects.create(
                user_id=log_entry['user_id'],
                security_type=f'integration_{log_entry["event_type"]}',
                severity=log_entry['severity'],
                description=log_entry['message'],
                metadata={
                    'integration_audit': True,
                    'logger_name': log_entry['logger_name'],
                    'integration_name': log_entry['integration_name'],
                    'event_id': log_entry['id'],
                    **log_entry['metadata']
                }
            )
        except Exception as e:
            logger.error(f"Error creating security log: {e}")
    
    def log_integration_start(self, integration_name: str, user: User = None, 
                             metadata: Dict[str, Any] = None):
        """Log integration start"""
        self.log_event(
            'integration_start',
            f"Integration started: {integration_name}",
            EventSeverity.INFO,
            user,
            integration_name,
            metadata
        )
    
    def log_integration_success(self, integration_name: str, user: User = None,
                               metadata: Dict[str, Any] = None):
        """Log integration success"""
        self.log_event(
            'integration_success',
            f"Integration completed successfully: {integration_name}",
            EventSeverity.INFO,
            user,
            integration_name,
            metadata
        )
    
    def log_integration_error(self, integration_name: str, error: str, user: User = None,
                             metadata: Dict[str, Any] = None):
        """Log integration error"""
        self.log_event(
            'integration_error',
            f"Integration error: {integration_name} - {error}",
            EventSeverity.ERROR,
            user,
            integration_name,
            {**(metadata or {}), 'error': error}
        )
    
    def log_data_transfer(self, source: str, target: str, record_count: int, 
                          user: User = None, metadata: Dict[str, Any] = None):
        """Log data transfer"""
        self.log_event(
            'data_transfer',
            f"Data transferred: {source} -> {target} ({record_count} records)",
            EventSeverity.INFO,
            user,
            None,
            {
                'source': source,
                'target': target,
                'record_count': record_count,
                **(metadata or {})
            }
        )
    
    def log_authentication(self, provider: str, success: bool, user: User = None,
                        metadata: Dict[str, Any] = None):
        """Log authentication attempt"""
        severity = EventSeverity.INFO if success else EventSeverity.WARNING
        message = f"Authentication {'success' if success else 'failed'}: {provider}"
        
        self.log_event(
            'authentication',
            message,
            severity,
            user,
            None,
            {
                'provider': provider,
                'success': success,
                **(metadata or {})
            }
        )
    
    def log_configuration_change(self, integration_name: str, config_key: str, 
                                old_value: Any, new_value: Any, user: User = None):
        """Log configuration change"""
        self.log_event(
            'configuration_change',
            f"Configuration changed: {integration_name}.{config_key}",
            EventSeverity.INFO,
            user,
            integration_name,
            {
                'config_key': config_key,
                'old_value': str(old_value),
                'new_value': str(new_value)
            }
        )
    
    def log_circuit_breaker(self, circuit_name: str, action: str, reason: str = None,
                            user: User = None, metadata: Dict[str, Any] = None):
        """Log circuit breaker event"""
        self.log_event(
            'circuit_breaker',
            f"Circuit breaker {action}: {circuit_name}" + (f" - {reason}" if reason else ""),
            EventSeverity.WARNING if action == 'opened' else EventSeverity.INFO,
            user,
            None,
            {
                'circuit_name': circuit_name,
                'action': action,
                'reason': reason,
                **(metadata or {})
            }
        )
    
    def log_rate_limit(self, integration_name: str, limit_type: str, current_count: int,
                       limit: int, user: User = None, metadata: Dict[str, Any] = None):
        """Log rate limit event"""
        severity = EventSeverity.WARNING if current_count >= limit else EventSeverity.INFO
        
        self.log_event(
            'rate_limit',
            f"Rate limit {limit_type}: {integration_name} ({current_count}/{limit})",
            severity,
            user,
            integration_name,
            {
                'limit_type': limit_type,
                'current_count': current_count,
                'limit': limit,
                **(metadata or {})
            }
        )
    
    def log_webhook_event(self, webhook_name: str, event_type: str, status: str,
                         response_code: int = None, user: User = None, metadata: Dict[str, Any] = None):
        """Log webhook event"""
        severity = EventSeverity.ERROR if status == 'failed' else EventSeverity.INFO
        
        self.log_event(
            'webhook',
            f"Webhook {event_type}: {webhook_name} - {status}",
            severity,
            user,
            None,
            {
                'webhook_name': webhook_name,
                'event_type': event_type,
                'status': status,
                'response_code': response_code,
                **(metadata or {})
            }
        )
    
    def log_sync_operation(self, sync_rule: str, source: str, target: str, 
                          records_synced: int, conflicts: int, user: User = None,
                          metadata: Dict[str, Any] = None):
        """Log sync operation"""
        severity = EventSeverity.WARNING if conflicts > 0 else EventSeverity.INFO
        
        self.log_event(
            'sync_operation',
            f"Sync operation: {sync_rule} ({records_synced} synced, {conflicts} conflicts)",
            severity,
            user,
            None,
            {
                'sync_rule': sync_rule,
                'source': source,
                'target': target,
                'records_synced': records_synced,
                'conflicts': conflicts,
                **(metadata or {})
            }
        )
    
    def get_logs(self, event_type: str = None, severity: EventSeverity = None,
                 integration_name: str = None, user_id: int = None,
                 start_time: datetime = None, end_time: datetime = None,
                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get filtered logs"""
        filtered_logs = self.log_entries.copy()
        
        # Filter by event type
        if event_type:
            filtered_logs = [log for log in filtered_logs if log['event_type'] == event_type]
        
        # Filter by severity
        if severity:
            filtered_logs = [log for log in filtered_logs if log['severity'] == severity.value]
        
        # Filter by integration name
        if integration_name:
            filtered_logs = [log for log in filtered_logs if log['integration_name'] == integration_name]
        
        # Filter by user
        if user_id:
            filtered_logs = [log for log in filtered_logs if log['user_id'] == user_id]
        
        # Filter by time range
        if start_time:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] >= start_time]
        
        if end_time:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] <= end_time]
        
        # Sort by timestamp (newest first)
        filtered_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply limit
        if limit:
            filtered_logs = filtered_logs[:limit]
        
        return filtered_logs
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'log_level': self.log_level.value,
            'retention_days': self.retention_days,
            'max_log_entries': self.max_log_entries,
            'current_entries': len(self.log_entries),
            'statistics': self.statistics
        }
    
    def cleanup_old_logs(self):
        """Clean up old logs"""
        cutoff_date = timezone.now() - timedelta(days=self.retention_days)
        
        original_count = len(self.log_entries)
        self.log_entries = [log for log in self.log_entries if log['timestamp'] >= cutoff_date]
        
        cleaned_count = original_count - len(self.log_entries)
        logger.info(f"Cleaned up {cleaned_count} old log entries from {self.name}")
        
        return cleaned_count
    
    def clear_logs(self):
        """Clear all logs"""
        self.log_entries.clear()
        self.statistics = {
            'total_logs': 0,
            'logs_by_level': {},
            'logs_by_type': {},
            'last_log': None
        }
        logger.info(f"Cleared all logs from {self.name}")
    
    def enable(self):
        """Enable audit logger"""
        self.enabled = True
        logger.info(f"Audit logger {self.name} enabled")
    
    def disable(self):
        """Disable audit logger"""
        self.enabled = False
        logger.info(f"Audit logger {self.name} disabled")
    
    def set_log_level(self, level: EventSeverity):
        """Set minimum log level"""
        self.log_level = level
        logger.info(f"Set log level to {level.value} for {self.name}")


class AuditLogManager:
    """Manager for integration audit logs"""
    
    def __init__(self):
        self.loggers = {}
        self.global_settings = {
            'retention_days': 90,
            'max_entries_per_logger': 10000,
            'auto_cleanup': True,
            'cleanup_interval_hours': 24
        }
        self.enabled = True
        self.last_cleanup = timezone.now()
    
    def create_logger(self, logger_name: str, retention_days: int = None,
                     max_entries: int = None) -> IntegrationAuditLogger:
        """Create audit logger"""
        logger = IntegrationAuditLogger(logger_name)
        
        if retention_days:
            logger.retention_days = retention_days
        
        if max_entries:
            logger.max_log_entries = max_entries
        
        self.loggers[logger_name] = logger
        logger.info(f"Created audit logger: {logger_name}")
        
        return logger
    
    def remove_logger(self, logger_name: str) -> bool:
        """Remove audit logger"""
        if logger_name in self.loggers:
            del self.loggers[logger_name]
            logger.info(f"Removed audit logger: {logger_name}")
            return True
        return False
    
    def get_logger(self, logger_name: str) -> Optional[IntegrationAuditLogger]:
        """Get logger by name"""
        return self.loggers.get(logger_name)
    
    def log_event(self, logger_name: str, event_type: str, message: str,
                  severity: EventSeverity = EventSeverity.INFO, **kwargs):
        """Log event to specific logger"""
        logger = self.get_logger(logger_name)
        if logger:
            logger.log_event(event_type, message, severity, **kwargs)
        else:
            # Create default logger if not exists
            default_logger = self.create_logger(logger_name)
            default_logger.log_event(event_type, message, severity, **kwargs)
    
    def get_all_logs(self, **filters) -> Dict[str, List[Dict[str, Any]]]:
        """Get logs from all loggers"""
        result = {}
        
        for logger_name, logger in self.loggers.items():
            result[logger_name] = logger.get_logs(**filters)
        
        return result
    
    def get_aggregated_statistics(self) -> Dict[str, Any]:
        """Get aggregated statistics from all loggers"""
        aggregated = {
            'total_loggers': len(self.loggers),
            'enabled_loggers': len([l for l in self.loggers.values() if l.enabled]),
            'total_logs': 0,
            'logs_by_level': {},
            'logs_by_type': {},
            'loggers': {}
        }
        
        for logger_name, logger in self.loggers.items():
            stats = logger.get_statistics()
            
            aggregated['total_logs'] += stats['statistics']['total_logs']
            aggregated['loggers'][logger_name] = stats
            
            # Aggregate level counts
            for level, count in stats['statistics']['logs_by_level'].items():
                aggregated['logs_by_level'][level] = aggregated['logs_by_level'].get(level, 0) + count
            
            # Aggregate type counts
            for event_type, count in stats['statistics']['logs_by_type'].items():
                aggregated['logs_by_type'][event_type] = aggregated['logs_by_type'].get(event_type, 0) + count
        
        return aggregated
    
    def cleanup_all_logs(self):
        """Clean up old logs from all loggers"""
        total_cleaned = 0
        
        for logger in self.loggers.values():
            cleaned = logger.cleanup_old_logs()
            total_cleaned += cleaned
        
        self.last_cleanup = timezone.now()
        logger.info(f"Cleaned up {total_cleaned} old log entries from all loggers")
        
        return total_cleaned
    
    def auto_cleanup_if_needed(self):
        """Auto cleanup if interval passed"""
        if not self.global_settings['auto_cleanup']:
            return
        
        interval = timedelta(hours=self.global_settings['cleanup_interval_hours'])
        
        if timezone.now() - self.last_cleanup >= interval:
            self.cleanup_all_logs()
    
    def enable_all_loggers(self):
        """Enable all loggers"""
        for logger in self.loggers.values():
            logger.enable()
    
    def disable_all_loggers(self):
        """Disable all loggers"""
        for logger in self.loggers.values():
            logger.disable()
    
    def clear_all_logs(self):
        """Clear all logs"""
        for logger in self.loggers.values():
            logger.clear_logs()
    
    def get_status(self) -> Dict[str, Any]:
        """Get audit log status"""
        return {
            'enabled': self.enabled,
            'global_settings': self.global_settings,
            'total_loggers': len(self.loggers),
            'last_cleanup': self.last_cleanup.isoformat(),
            'aggregated_statistics': self.get_aggregated_statistics()
        }
    
    def enable(self):
        """Enable audit log manager"""
        self.enabled = True
        logger.info("Audit log manager enabled")
    
    def disable(self):
        """Disable audit log manager"""
        self.enabled = False
        logger.info("Audit log manager disabled")


# Global audit log manager
audit_log_manager = AuditLogManager()

# Create default loggers
def create_default_audit_loggers():
    """Create default audit loggers"""
    
    # Integration logger
    integration_logger = audit_log_manager.create_logger(
        'integration',
        retention_days=90,
        max_entries=10000
    )
    
    # Webhook logger
    webhook_logger = audit_log_manager.create_logger(
        'webhook',
        retention_days=60,
        max_entries=5000
    )
    
    # Data sync logger
    sync_logger = audit_log_manager.create_logger(
        'data_sync',
        retention_days=120,
        max_entries=15000
    )
    
    # Authentication logger
    auth_logger = audit_log_manager.create_logger(
        'authentication',
        retention_days=90,
        max_entries=8000
    )
    
    # Performance logger
    perf_logger = audit_log_manager.create_logger(
        'performance',
        retention_days=30,
        max_entries=20000
    )
    
    logger.info("Created default audit loggers")


# Initialize default loggers
create_default_audit_loggers()


# Export symbols
__all__ = [
    'IntegrationAuditLogger',
    'AuditLogManager',
    'audit_log_manager',
    'create_default_audit_loggers'
]