# api/rate_limit/integ_audit_logs.py
"""
Integration audit logs for rate limit module.

Provides comprehensive audit trail for integration operations.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
import json
import hashlib

from api.rate_limit.integ_constants import IntegrationEvent, IntegrationStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class IntegrationAuditLog:
    """Represents an integration audit log entry."""
    
    def __init__(self, event_type: str, integration_id: str, action: str,
                 user_id: int = None, ip_address: str = None, 
                 details: Dict[str, Any] = None, status: str = 'success',
                 error_message: str = None, timestamp: datetime = None):
        self.log_id = f"audit_{timezone.now().timestamp()}_{id(self)}"
        self.event_type = event_type
        self.integration_id = integration_id
        self.action = action
        self.user_id = user_id
        self.ip_address = ip_address
        self.details = details or {}
        self.status = status
        self.error_message = error_message
        self.timestamp = timestamp or timezone.now()
        self.session_id = None
        self.request_id = None
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary."""
        return {
            'log_id': self.log_id,
            'event_type': self.event_type,
            'integration_id': self.integration_id,
            'action': self.action,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'details': self.details,
            'status': self.status,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'request_id': self.request_id,
            'metadata': self.metadata
        }
    
    def get_hash(self) -> str:
        """Get hash of audit log for integrity verification."""
        log_data = self.to_dict()
        log_string = json.dumps(log_data, sort_keys=True)
        return hashlib.sha256(log_string.encode()).hexdigest()


class IntegrationAuditLogger:
    """
    Logger for integration audit events.
    """
    
    def __init__(self):
        self.logs: List[IntegrationAuditLog] = []
        self.max_logs = 10000
        self.cache_timeout = 86400 * 30  # 30 days
        self.log_retention_days = 365  # 1 year
        self.compliance_mode = getattr(settings, 'INTEGRATION_AUDIT_COMPLIANCE_MODE', False)
    
    def log_event(self, event_type: str, integration_id: str, action: str,
                  user_id: int = None, ip_address: str = None,
                  details: Dict[str, Any] = None, status: str = 'success',
                  error_message: str = None, session_id: str = None,
                  request_id: str = None, metadata: Dict[str, Any] = None):
        """
        Log an integration event.
        
        Args:
            event_type: Type of event
            integration_id: Integration identifier
            action: Action performed
            user_id: User ID
            ip_address: IP address
            details: Event details
            status: Event status
            error_message: Error message if failed
            session_id: Session ID
            request_id: Request ID
            metadata: Additional metadata
        """
        try:
            audit_log = IntegrationAuditLog(
                event_type=event_type,
                integration_id=integration_id,
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                details=details,
                status=status,
                error_message=error_message
            )
            
            if session_id:
                audit_log.session_id = session_id
            
            if request_id:
                audit_log.request_id = request_id
            
            if metadata:
                audit_log.metadata = metadata
            
            # Add to memory logs
            self.logs.append(audit_log)
            
            # Maintain memory size
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
            
            # Store in cache
            cache_key = f"integration_audit:{audit_log.timestamp.date()}"
            day_logs = cache.get(cache_key, [])
            day_logs.append(audit_log.to_dict())
            cache.set(cache_key, day_logs, timeout=self.cache_timeout)
            
            # Log to system logger
            log_level = logging.INFO if status == 'success' else logging.ERROR
            log_message = f"Integration Audit: {action} on {integration_id} by user {user_id}"
            
            if status == 'failure' and error_message:
                log_message += f" - ERROR: {error_message}"
            
            logger.log(log_level, log_message, extra={
                'audit_log': audit_log.to_dict()
            })
            
            # Compliance mode - ensure immutability
            if self.compliance_mode:
                self._ensure_immutability(audit_log)
            
        except Exception as e:
            logger.error(f"Failed to log integration audit event: {str(e)}")
    
    def _ensure_immutability(self, audit_log: IntegrationAuditLog):
        """Ensure audit log immutability for compliance."""
        try:
            # Create immutable hash
            log_hash = audit_log.get_hash()
            
            # Store hash for verification
            hash_key = f"audit_hash:{audit_log.log_id}"
            cache.set(hash_key, log_hash, timeout=self.cache_timeout * 2)  # Longer retention for hashes
            
        except Exception as e:
            logger.error(f"Failed to ensure audit log immutability: {str(e)}")
    
    def verify_integrity(self, log_id: str) -> bool:
        """
        Verify audit log integrity.
        
        Args:
            log_id: Log ID to verify
            
        Returns:
            True if integrity is verified
        """
        try:
            # Get stored hash
            hash_key = f"audit_hash:{log_id}"
            stored_hash = cache.get(hash_key)
            
            if not stored_hash:
                return False
            
            # Find log and recalculate hash
            audit_log = None
            for log in self.logs:
                if log.log_id == log_id:
                    audit_log = log
                    break
            
            if not audit_log:
                # Try to get from cache
                cache_keys = cache.keys("integration_audit:*")
                for cache_key in cache_keys:
                    day_logs = cache.get(cache_key, [])
                    for log_data in day_logs:
                        if log_data.get('log_id') == log_id:
                            # Recreate audit log from data
                            audit_log = IntegrationAuditLog(
                                event_type=log_data['event_type'],
                                integration_id=log_data['integration_id'],
                                action=log_data['action'],
                                user_id=log_data.get('user_id'),
                                ip_address=log_data.get('ip_address'),
                                details=log_data.get('details'),
                                status=log_data.get('status'),
                                error_message=log_data.get('error_message'),
                                timestamp=datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00'))
                            )
                            break
                    if audit_log:
                        break
            
            if not audit_log:
                return False
            
            # Verify hash
            current_hash = audit_log.get_hash()
            return current_hash == stored_hash
            
        except Exception as e:
            logger.error(f"Failed to verify audit log integrity: {str(e)}")
            return False
    
    def get_logs(self, event_type: str = None, integration_id: str = None,
                user_id: int = None, status: str = None, start_date: datetime = None,
                end_date: datetime = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit logs with filtering.
        
        Args:
            event_type: Filter by event type
            integration_id: Filter by integration ID
            user_id: Filter by user ID
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of logs
            
        Returns:
            List of audit logs
        """
        try:
            # Get logs from cache for date range
            if start_date and end_date:
                logs = []
                current_date = start_date.date()
                
                while current_date <= end_date.date():
                    cache_key = f"integration_audit:{current_date}"
                    day_logs = cache.get(cache_key, [])
                    logs.extend(day_logs)
                    current_date += timedelta(days=1)
            else:
                # Get from memory
                logs = [log.to_dict() for log in self.logs]
            
            # Apply filters
            if event_type:
                logs = [log for log in logs if log.get('event_type') == event_type]
            
            if integration_id:
                logs = [log for log in logs if log.get('integration_id') == integration_id]
            
            if user_id:
                logs = [log for log in logs if log.get('user_id') == user_id]
            
            if status:
                logs = [log for log in logs if log.get('status') == status]
            
            # Sort by timestamp (most recent first)
            logs.sort(key=lambda log: log['timestamp'], reverse=True)
            
            return logs[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get audit logs: {str(e)}")
            return []
    
    def get_log_statistics(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Get audit log statistics.
        
        Args:
            period_days: Period in days
            
        Returns:
            Statistics dictionary
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            logs = self.get_logs(start_date=start_date, end_date=end_date, limit=10000)
            
            if not logs:
                return {
                    'period_days': period_days,
                    'total_logs': 0,
                    'event_types': {},
                    'integration_ids': {},
                    'status_counts': {},
                    'user_activity': {},
                    'daily_counts': {}
                }
            
            # Calculate statistics
            event_types = {}
            integration_ids = {}
            status_counts = {}
            user_activity = {}
            daily_counts = {}
            
            for log in logs:
                # Event types
                event_type = log.get('event_type', 'unknown')
                event_types[event_type] = event_types.get(event_type, 0) + 1
                
                # Integration IDs
                integration_id = log.get('integration_id', 'unknown')
                integration_ids[integration_id] = integration_ids.get(integration_id, 0) + 1
                
                # Status counts
                status = log.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # User activity
                user_id = log.get('user_id')
                if user_id:
                    user_activity[user_id] = user_activity.get(user_id, 0) + 1
                
                # Daily counts
                log_date = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')).date()
                date_key = log_date.isoformat()
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
            
            return {
                'period_days': period_days,
                'total_logs': len(logs),
                'event_types': event_types,
                'integration_ids': integration_ids,
                'status_counts': status_counts,
                'user_activity': user_activity,
                'daily_counts': daily_counts,
                'success_rate': (status_counts.get('success', 0) / len(logs)) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to get audit log statistics: {str(e)}")
            return {'error': str(e)}
    
    def export_logs(self, format: str = 'json', start_date: datetime = None,
                  end_date: datetime = None) -> Dict[str, Any]:
        """
        Export audit logs.
        
        Args:
            format: Export format (json, csv)
            start_date: Start date
            end_date: End date
            
        Returns:
            Export result
        """
        try:
            logs = self.get_logs(start_date=start_date, end_date=end_date, limit=10000)
            
            if format == 'json':
                export_data = {
                    'export_metadata': {
                        'format': format,
                        'start_date': start_date.isoformat() if start_date else None,
                        'end_date': end_date.isoformat() if end_date else None,
                        'record_count': len(logs),
                        'exported_at': timezone.now().isoformat()
                    },
                    'logs': logs
                }
                
                return {
                    'success': True,
                    'data': export_data,
                    'content_type': 'application/json'
                }
            
            elif format == 'csv':
                # Convert to CSV format
                if logs:
                    headers = list(logs[0].keys())
                    csv_data = [headers]
                    
                    for log in logs:
                        row = []
                        for header in headers:
                            value = log.get(header, '')
                            if isinstance(value, (dict, list)):
                                value = json.dumps(value)
                            row.append(str(value))
                        csv_data.append(row)
                    
                    return {
                        'success': True,
                        'data': csv_data,
                        'content_type': 'text/csv'
                    }
                else:
                    return {
                        'success': True,
                        'data': [],
                        'content_type': 'text/csv'
                    }
            
            else:
                return {
                    'success': False,
                    'error': f'Unsupported export format: {format}'
                }
                
        except Exception as e:
            logger.error(f"Failed to export audit logs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_logs(self, retention_days: int = None) -> Dict[str, Any]:
        """
        Clean up old audit logs.
        
        Args:
            retention_days: Retention period in days
            
        Returns:
            Cleanup result
        """
        try:
            retention_days = retention_days or self.log_retention_days
            cutoff_date = timezone.now() - timedelta(days=retention_days)
            
            # Clean up memory logs
            original_count = len(self.logs)
            self.logs = [log for log in self.logs if log.timestamp >= cutoff_date]
            memory_removed = original_count - len(self.logs)
            
            # Clean up cache
            cache_keys = cache.keys("integration_audit:*")
            cache_removed = 0
            
            for cache_key in cache_keys:
                # Extract date from cache key
                date_str = cache_key.split(':')[-1]
                try:
                    cache_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if cache_date < cutoff_date.date():
                        cache.delete(cache_key)
                        cache_removed += 1
                except ValueError:
                    continue
            
            logger.info(f"Cleaned up {memory_removed} memory logs and {cache_removed} cache entries")
            
            return {
                'success': True,
                'retention_days': retention_days,
                'memory_removed': memory_removed,
                'cache_removed': cache_removed,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup audit logs: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance report.
        
        Returns:
            Compliance report
        """
        try:
            report = {
                'generated_at': timezone.now().isoformat(),
                'compliance_mode': self.compliance_mode,
                'retention_days': self.log_retention_days,
                'max_logs': self.max_logs,
                'cache_timeout': self.cache_timeout,
                'statistics': self.get_log_statistics(period_days=30),
                'integrity_checks': {
                    'total_logs_checked': 0,
                    'passed_checks': 0,
                    'failed_checks': 0
                }
            }
            
            # Perform integrity checks on recent logs
            recent_logs = self.get_logs(limit=100)
            passed_checks = 0
            failed_checks = 0
            
            for log in recent_logs:
                if self.verify_integrity(log['log_id']):
                    passed_checks += 1
                else:
                    failed_checks += 1
            
            report['integrity_checks'] = {
                'total_logs_checked': len(recent_logs),
                'passed_checks': passed_checks,
                'failed_checks': failed_checks,
                'integrity_rate': (passed_checks / max(len(recent_logs), 1)) * 100
            }
            
            # Compliance recommendations
            recommendations = []
            
            if failed_checks > 0:
                recommendations.append("Some audit logs failed integrity verification")
            
            if not self.compliance_mode:
                recommendations.append("Consider enabling compliance mode for enhanced security")
            
            if report['statistics']['success_rate'] < 95:
                recommendations.append("Low success rate detected - investigate integration issues")
            
            report['recommendations'] = recommendations
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {str(e)}")
            return {'error': str(e)}


# Global audit logger instance
integration_audit_logger = IntegrationAuditLogger()


# Decorator for automatic audit logging
def audit_integration_event(event_type: str, action: str, include_user: bool = True,
                          include_ip: bool = True):
    """
    Decorator for automatic integration audit logging.
    
    Args:
        event_type: Type of event
        action: Action performed
        include_user: Whether to include user information
        include_ip: Whether to include IP address
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                # Get context information
                request = kwargs.get('request')
                user = getattr(request, 'user', None) if request else None
                integration_id = kwargs.get('integration_id', 'unknown')
                
                # Get IP address
                ip_address = None
                if request:
                    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                    if x_forwarded_for:
                        ip_address = x_forwarded_for.split(',')[0].strip()
                    else:
                        ip_address = request.META.get('REMOTE_ADDR')
                
                # Execute function
                start_time = timezone.now()
                result = func(*args, **kwargs)
                execution_time = (timezone.now() - start_time).total_seconds()
                
                # Determine status
                status = 'success'
                error_message = None
                
                if isinstance(result, dict):
                    if not result.get('success', True):
                        status = 'failure'
                        error_message = result.get('error')
                elif hasattr(result, 'success') and not result.success:
                    status = 'failure'
                    error_message = getattr(result, 'error', None)
                
                # Log audit event
                integration_audit_logger.log_event(
                    event_type=event_type,
                    integration_id=integration_id,
                    action=action,
                    user_id=user.id if user and include_user else None,
                    ip_address=ip_address if include_ip else None,
                    details={
                        'function': func.__name__,
                        'execution_time': execution_time,
                        'args_count': len(args),
                        'kwargs_count': len(kwargs)
                    },
                    status=status,
                    error_message=error_message,
                    metadata={
                        'module': func.__module__,
                        'args': str(args)[:200],  # Truncate for security
                        'kwargs': str(kwargs)[:200]  # Truncate for security
                    }
                )
                
                return result
                
            except Exception as e:
                # Log failure
                integration_audit_logger.log_event(
                    event_type=event_type,
                    integration_id=kwargs.get('integration_id', 'unknown'),
                    action=action,
                    status='failure',
                    error_message=str(e),
                    details={
                        'function': func.__name__,
                        'exception_type': type(e).__name__
                    }
                )
                
                raise
        
        return wrapper
    return decorator


# Export classes and functions
__all__ = [
    'IntegrationAuditLog',
    'IntegrationAuditLogger',
    'integration_audit_logger',
    'audit_integration_event'
]
