"""Integration Audit Logs

This module provides comprehensive audit logging for integration system
with detailed activity tracking and compliance reporting.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_constants import LogLevel, HealthStatus
from .integ_exceptions import IntegrationError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class AuditLog:
    """Audit log entry for integration system."""
    
    def __init__(self, event_type: str, action: str, **kwargs):
        """Initialize audit log entry."""
        self.id = kwargs.get('id', self._generate_id())
        self.event_type = event_type
        self.action = action
        self.timestamp = kwargs.get('timestamp', timezone.now())
        self.user_id = kwargs.get('user_id')
        self.source = kwargs.get('source', 'integration_system')
        self.target = kwargs.get('target')
        self.details = kwargs.get('details', {})
        self.metadata = kwargs.get('metadata', {})
        self.ip_address = kwargs.get('ip_address')
        self.user_agent = kwargs.get('user_agent')
        self.session_id = kwargs.get('session_id')
        self.request_id = kwargs.get('request_id')
        self.level = kwargs.get('level', LogLevel.INFO)
        self.success = kwargs.get('success', True)
        self.error_message = kwargs.get('error_message')
        self.duration_ms = kwargs.get('duration_ms')
        
        # Add system metadata
        self.metadata.update({
            'log_id': self.id,
            'created_at': self.timestamp.isoformat(),
            'audit_system': True
        })
    
    def _generate_id(self) -> str:
        """Generate unique log ID."""
        import uuid
        return str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'action': self.action,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'source': self.source,
            'target': self.target,
            'details': self.details,
            'metadata': self.metadata,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'level': self.level,
            'success': self.success,
            'error_message': self.error_message,
            'duration_ms': self.duration_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditLog':
        """Create audit log from dictionary."""
        return cls(
            event_type=data['event_type'],
            action=data['action'],
            timestamp=timezone.parse(data['timestamp']),
            user_id=data.get('user_id'),
            source=data.get('source'),
            target=data.get('target'),
            details=data.get('details', {}),
            metadata=data.get('metadata', {}),
            ip_address=data.get('ip_address'),
            user_agent=data.get('user_agent'),
            session_id=data.get('session_id'),
            request_id=data.get('request_id'),
            level=data.get('level', LogLevel.INFO),
            success=data.get('success', True),
            error_message=data.get('error_message'),
            duration_ms=data.get('duration_ms')
        )


class AuditLogger:
    """Audit logger for integration system."""
    
    def __init__(self):
        """Initialize the audit logger."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize audit logging
        self._initialize_audit_logging()
    
    def _load_configuration(self):
        """Load audit logging configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_AUDIT_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.log_level = self.config.get('log_level', LogLevel.INFO)
            self.max_log_size = self.config.get('max_log_size', 10000)
            self.retention_days = self.config.get('retention_days', 90)
            self.enable_file_logging = self.config.get('enable_file_logging', True)
            self.enable_database_logging = self.config.get('enable_database_logging', False)
            self.enable_cache_logging = self.config.get('enable_cache_logging', True)
            
        except Exception as e:
            self.logger.error(f"Error loading audit configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.log_level = LogLevel.INFO
            self.max_log_size = 10000
            self.retention_days = 90
            self.enable_file_logging = True
            self.enable_database_logging = False
            self.enable_cache_logging = True
    
    def _initialize_audit_logging(self):
        """Initialize audit logging system."""
        try:
            # Initialize log storage
            self.log_storage = AuditLogStorage(self.config)
            
            # Initialize log processors
            self.log_processors = []
            if self.enable_file_logging:
                self.log_processors.append(FileLogProcessor(self.config))
            if self.enable_database_logging:
                self.log_processors.append(DatabaseLogProcessor(self.config))
            if self.enable_cache_logging:
                self.log_processors.append(CacheLogProcessor(self.config))
            
            self.logger.info("Audit logging system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing audit logging: {str(e)}")
    
    def log_event(self, event_type: str, action: str, **kwargs) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action performed
            **kwargs: Additional event data
            
        Returns:
            Log entry ID
        """
        try:
            if not self.enabled:
                return None
            
            with self.monitor.measure_fallback('audit_log') as measurement:
                # Create audit log
                audit_log = AuditLog(event_type, action, **kwargs)
                
                # Store log
                self.log_storage.store_log(audit_log)
                
                # Process log
                for processor in self.log_processors:
                    try:
                        processor.process_log(audit_log)
                    except Exception as e:
                        self.logger.error(f"Error in log processor {processor.__class__.__name__}: {str(e)}")
                        continue
                
                return audit_log.id
                
        except Exception as e:
            self.logger.error(f"Error logging audit event: {str(e)}")
            return None
    
    def log_handler_event(self, handler_name: str, action: str, **kwargs) -> str:
        """Log handler event."""
        return self.log_event('handler', action, target=handler_name, **kwargs)
    
    def log_adapter_event(self, adapter_type: str, action: str, **kwargs) -> str:
        """Log adapter event."""
        return self.log_event('adapter', action, target=adapter_type, **kwargs)
    
    def log_bridge_event(self, bridge_type: str, action: str, **kwargs) -> str:
        """Log bridge event."""
        return self.log_event('bridge', action, target=bridge_type, **kwargs)
    
    def log_webhook_event(self, webhook_id: str, action: str, **kwargs) -> str:
        """Log webhook event."""
        return self.log_event('webhook', action, target=webhook_id, **kwargs)
    
    def log_auth_event(self, auth_type: str, action: str, **kwargs) -> str:
        """Log authentication event."""
        return self.log_event('auth', action, target=auth_type, **kwargs)
    
    def log_validation_event(self, validation_type: str, action: str, **kwargs) -> str:
        """Log validation event."""
        return self.log_event('validation', action, target=validation_type, **kwargs)
    
    def log_fallback_event(self, fallback_type: str, action: str, **kwargs) -> str:
        """Log fallback event."""
        return self.log_event('fallback', action, target=fallback_type, **kwargs)
    
    def log_error_event(self, error_type: str, error_message: str, **kwargs) -> str:
        """Log error event."""
        return self.log_event('error', 'error_occurred', details={'error_type': error_type, 'error_message': error_message}, success=False, **kwargs)
    
    def log_security_event(self, security_type: str, action: str, **kwargs) -> str:
        """Log security event."""
        return self.log_event('security', action, target=security_type, **kwargs)
    
    def get_audit_logs(self, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit logs.
        
        Args:
            filters: Optional filters
            limit: Maximum number of logs to return
            
        Returns:
            List of audit logs
        """
        try:
            return self.log_storage.get_logs(filters, limit)
            
        except Exception as e:
            self.logger.error(f"Error getting audit logs: {str(e)}")
            return []
    
    def get_audit_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific audit log.
        
        Args:
            log_id: Log ID
            
        Returns:
            Audit log or None
        """
        try:
            return self.log_storage.get_log(log_id)
            
        except Exception as e:
            self.logger.error(f"Error getting audit log {log_id}: {str(e)}")
            return None
    
    def get_audit_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get audit summary.
        
        Args:
            days: Number of days to summarize
            
        Returns:
            Audit summary
        """
        try:
            since = timezone.now() - timedelta(days=days)
            
            # Get logs for the period
            logs = self.log_storage.get_logs({'since': since})
            
            # Calculate summary
            summary = {
                'period_days': days,
                'total_logs': len(logs),
                'event_types': {},
                'actions': {},
                'success_rate': 0,
                'error_count': 0,
                'top_users': {},
                'top_sources': {}
            }
            
            success_count = 0
            
            for log in logs:
                # Count event types
                event_type = log.get('event_type', 'unknown')
                summary['event_types'][event_type] = summary['event_types'].get(event_type, 0) + 1
                
                # Count actions
                action = log.get('action', 'unknown')
                summary['actions'][action] = summary['actions'].get(action, 0) + 1
                
                # Count success/failure
                if log.get('success', True):
                    success_count += 1
                else:
                    summary['error_count'] += 1
                
                # Count users
                user_id = log.get('user_id')
                if user_id:
                    summary['top_users'][user_id] = summary['top_users'].get(user_id, 0) + 1
                
                # Count sources
                source = log.get('source', 'unknown')
                summary['top_sources'][source] = summary['top_sources'].get(source, 0) + 1
            
            # Calculate success rate
            if summary['total_logs'] > 0:
                summary['success_rate'] = (success_count / summary['total_logs']) * 100
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting audit summary: {str(e)}")
            return {'error': str(e)}
    
    def search_audit_logs(self, query: str, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search audit logs.
        
        Args:
            query: Search query
            filters: Optional filters
            limit: Maximum number of logs to return
            
        Returns:
            List of matching audit logs
        """
        try:
            return self.log_storage.search_logs(query, filters, limit)
            
        except Exception as e:
            self.logger.error(f"Error searching audit logs: {str(e)}")
            return []
    
    def export_audit_logs(self, filters: Dict[str, Any] = None, format: str = 'json') -> Dict[str, Any]:
        """
        Export audit logs.
        
        Args:
            filters: Optional filters
            format: Export format (json, csv, xml)
            
        Returns:
            Export result
        """
        try:
            logs = self.log_storage.get_logs(filters)
            
            if format == 'json':
                return {
                    'format': 'json',
                    'data': logs,
                    'count': len(logs),
                    'exported_at': timezone.now().isoformat()
                }
            elif format == 'csv':
                return self._export_csv(logs)
            elif format == 'xml':
                return self._export_xml(logs)
            else:
                return {'error': f'Unsupported format: {format}'}
                
        except Exception as e:
            self.logger.error(f"Error exporting audit logs: {str(e)}")
            return {'error': str(e)}
    
    def _export_csv(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export logs as CSV."""
        try:
            import csv
            import io
            
            output = io.StringIO()
            
            if logs:
                fieldnames = logs[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(logs)
            
            return {
                'format': 'csv',
                'data': output.getvalue(),
                'count': len(logs),
                'exported_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting CSV: {str(e)}")
            return {'error': str(e)}
    
    def _export_xml(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Export logs as XML."""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.Element('audit_logs')
            
            for log in logs:
                log_elem = ET.SubElement(root, 'log')
                for key, value in log.items():
                    elem = ET.SubElement(log_elem, key)
                    elem.text = str(value)
            
            xml_data = ET.tostring(root, encoding='unicode')
            
            return {
                'format': 'xml',
                'data': xml_data,
                'count': len(logs),
                'exported_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error exporting XML: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_logs(self) -> int:
        """
        Clean up old audit logs.
        
        Returns:
            Number of logs cleaned up
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=self.retention_days)
            
            return self.log_storage.cleanup_logs(cutoff_date)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {str(e)}")
            return 0
    
    def get_audit_status(self) -> Dict[str, Any]:
        """
        Get audit logging status.
        
        Returns:
            Audit status
        """
        try:
            return {
                'audit_logger': {
                    'status': 'running' if self.enabled else 'disabled',
                    'log_level': self.log_level,
                    'max_log_size': self.max_log_size,
                    'retention_days': self.retention_days,
                    'enable_file_logging': self.enable_file_logging,
                    'enable_database_logging': self.enable_database_logging,
                    'enable_cache_logging': self.enable_cache_logging,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'log_storage': self.log_storage.get_status(),
                'processors': [
                    processor.__class__.__name__ for processor in self.log_processors
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting audit status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of audit logging system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check log storage
            storage_health = self.log_storage.health_check()
            health_status['components']['log_storage'] = storage_health
            
            if storage_health['status'] != HealthStatus.HEALTHY:
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            # Check processors
            health_status['components']['processors'] = {
                'status': HealthStatus.HEALTHY,
                'total_processors': len(self.log_processors)
            }
            
            # Check log size
            current_size = self.log_storage.get_log_count()
            if current_size >= self.max_log_size * 0.9:
                health_status['overall'] = HealthStatus.DEGRADED
            elif current_size >= self.max_log_size:
                health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }


class AuditLogStorage:
    """Audit log storage manager."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the audit log storage."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load storage configuration."""
        try:
            self.max_cache_size = self.config.get('max_cache_size', 1000)
            self.cache_timeout = self.config.get('cache_timeout', 3600)  # 1 hour
            
        except Exception as e:
            self.logger.error(f"Error loading storage configuration: {str(e)}")
            self.max_cache_size = 1000
            self.cache_timeout = 3600
    
    def store_log(self, audit_log: AuditLog):
        """Store audit log."""
        try:
            # Store in cache
            cache_key = f"audit_log:{audit_log.id}"
            cache.set(cache_key, audit_log.to_dict(), timeout=self.cache_timeout)
            
            # Add to recent logs cache
            recent_logs_key = "recent_audit_logs"
            recent_logs = cache.get(recent_logs_key, [])
            recent_logs.append(audit_log.to_dict())
            
            # Limit recent logs size
            if len(recent_logs) > self.max_cache_size:
                recent_logs = recent_logs[-self.max_cache_size:]
            
            cache.set(recent_logs_key, recent_logs, timeout=self.cache_timeout)
            
        except Exception as e:
            self.logger.error(f"Error storing audit log: {str(e)}")
    
    def get_logs(self, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs."""
        try:
            recent_logs_key = "recent_audit_logs"
            logs = cache.get(recent_logs_key, [])
            
            # Apply filters
            if filters:
                logs = self._apply_filters(logs, filters)
            
            # Limit results
            if limit:
                logs = logs[-limit:]
            
            return logs
            
        except Exception as e:
            self.logger.error(f"Error getting audit logs: {str(e)}")
            return []
    
    def get_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit log."""
        try:
            cache_key = f"audit_log:{log_id}"
            return cache.get(cache_key)
            
        except Exception as e:
            self.logger.error(f"Error getting audit log {log_id}: {str(e)}")
            return None
    
    def search_logs(self, query: str, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search audit logs."""
        try:
            logs = self.get_logs(filters, None)
            
            # Search in logs
            matching_logs = []
            query_lower = query.lower()
            
            for log in logs:
                log_str = json.dumps(log).lower()
                if query_lower in log_str:
                    matching_logs.append(log)
            
            # Limit results
            if limit:
                matching_logs = matching_logs[-limit:]
            
            return matching_logs
            
        except Exception as e:
            self.logger.error(f"Error searching audit logs: {str(e)}")
            return []
    
    def _apply_filters(self, logs: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply filters to logs."""
        try:
            filtered_logs = logs
            
            # Filter by event type
            if 'event_type' in filters:
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('event_type') == filters['event_type']
                ]
            
            # Filter by action
            if 'action' in filters:
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('action') == filters['action']
                ]
            
            # Filter by user ID
            if 'user_id' in filters:
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('user_id') == filters['user_id']
                ]
            
            # Filter by success
            if 'success' in filters:
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('success') == filters['success']
                ]
            
            # Filter by date range
            if 'since' in filters:
                since = filters['since']
                filtered_logs = [
                    log for log in filtered_logs
                    if timezone.parse(log['timestamp']) >= since
                ]
            
            if 'until' in filters:
                until = filters['until']
                filtered_logs = [
                    log for log in filtered_logs
                    if timezone.parse(log['timestamp']) <= until
                ]
            
            return filtered_logs
            
        except Exception as e:
            self.logger.error(f"Error applying filters: {str(e)}")
            return logs
    
    def get_log_count(self) -> int:
        """Get total log count."""
        try:
            recent_logs_key = "recent_audit_logs"
            logs = cache.get(recent_logs_key, [])
            return len(logs)
            
        except Exception as e:
            self.logger.error(f"Error getting log count: {str(e)}")
            return 0
    
    def cleanup_logs(self, cutoff_date: timezone.datetime) -> int:
        """Clean up old logs."""
        try:
            recent_logs_key = "recent_audit_logs"
            logs = cache.get(recent_logs_key, [])
            
            # Filter out old logs
            cleaned_logs = [
                log for log in logs
                if timezone.parse(log['timestamp']) >= cutoff_date
            ]
            
            # Update cache
            cache.set(recent_logs_key, cleaned_logs, timeout=self.cache_timeout)
            
            # Remove individual log entries
            for log in logs:
                if log not in cleaned_logs:
                    cache_key = f"audit_log:{log['id']}"
                    cache.delete(cache_key)
            
            return len(logs) - len(cleaned_logs)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up logs: {str(e)}")
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get storage status."""
        return {
            'log_count': self.get_log_count(),
            'max_cache_size': self.max_cache_size,
            'cache_timeout': self.cache_timeout
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of storage."""
        try:
            # Test cache operations
            test_key = "health_check_test"
            test_value = {"test": True}
            
            cache.set(test_key, test_value, timeout=10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)
            
            is_healthy = retrieved == test_value
            
            return {
                'status': HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                'cache_operations': 'working' if is_healthy else 'failed',
                'log_count': self.get_log_count(),
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in storage health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class FileLogProcessor:
    """File log processor for audit logs."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the file log processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load processor configuration."""
        try:
            self.log_file = self.config.get('log_file', 'audit.log')
            self.max_file_size = self.config.get('max_file_size', 10 * 1024 * 1024)  # 10MB
            self.backup_count = self.config.get('backup_count', 5)
            
        except Exception as e:
            self.logger.error(f"Error loading processor configuration: {str(e)}")
            self.log_file = 'audit.log'
            self.max_file_size = 10 * 1024 * 1024
            self.backup_count = 5
    
    def process_log(self, audit_log: AuditLog):
        """Process audit log."""
        try:
            import os
            import json
            
            # Write to file
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(audit_log.to_dict()) + '\n')
            
            # Check file size and rotate if needed
            if os.path.exists(self.log_file):
                file_size = os.path.getsize(self.log_file)
                if file_size >= self.max_file_size:
                    self._rotate_log_file()
            
        except Exception as e:
            self.logger.error(f"Error processing audit log: {str(e)}")
    
    def _rotate_log_file(self):
        """Rotate log file."""
        try:
            import os
            import shutil
            
            # Rotate existing files
            for i in range(self.backup_count - 1, 0, -1):
                old_file = f"{self.log_file}.{i}"
                new_file = f"{self.log_file}.{i + 1}"
                
                if os.path.exists(old_file):
                    if os.path.exists(new_file):
                        os.remove(new_file)
                    shutil.move(old_file, new_file)
            
            # Move current file
            if os.path.exists(self.log_file):
                shutil.move(self.log_file, f"{self.log_file}.1")
            
            self.logger.info(f"Rotated audit log file: {self.log_file}")
            
        except Exception as e:
            self.logger.error(f"Error rotating log file: {str(e)}")


class DatabaseLogProcessor:
    """Database log processor for audit logs."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the database log processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process_log(self, audit_log: AuditLog):
        """Process audit log."""
        try:
            # This would integrate with your database model
            # For now, just log the event
            self.logger.info(f"Database log: {audit_log.event_type} - {audit_log.action}")
            
        except Exception as e:
            self.logger.error(f"Error processing audit log: {str(e)}")


class CacheLogProcessor:
    """Cache log processor for audit logs."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the cache log processor."""
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def process_log(self, audit_log: AuditLog):
        """Process audit log."""
        try:
            # This would integrate with your cache system
            # For now, just log the event
            self.logger.info(f"Cache log: {audit_log.event_type} - {audit_log.action}")
            
        except Exception as e:
            self.logger.error(f"Error processing audit log: {str(e)}")


# Global audit logger instance
audit_logger = AuditLogger()
