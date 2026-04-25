"""
Integration Audit Logs

Audit logging service for integration system
to track all integration activities and events.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
import uuid
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    ERROR_CODES
)
from ..exceptions import (
    IntegrationError, ValidationError
)

logger = logging.getLogger(__name__)


class IntegrationAuditLogger:
    """
    Integration audit logging service.
    
    Provides comprehensive audit logging for:
    - Integration registration and configuration
    - Execution events and results
    - Security and authentication events
    - Performance metrics and timing
    - Error tracking and resolution
    - Compliance and regulatory logging
    """
    
    def __init__(self):
        self.log_buffer = []
        self.log_levels = INTEGRATION_LOG_LEVELS
        self.audit_stats = {
            'total_logs': 0,
            'logs_by_level': {level: 0 for level in self.log_levels},
            'logs_by_type': {integration_type: 0 for integration_type in INTEGRATION_TYPES},
            'logs_by_status': {status: 0 for status in INTEGRATION_STATUSES},
            'avg_log_size_bytes': 0.0
        }
        self.retention_days = 90  # Keep logs for 90 days
    
    def log_integration_event(self, integration_id: str, event_type: str, 
                          event_data: Dict[str, Any], level: IntegrationLogLevel = IntegrationLogLevel.INFO,
                          user_id: Optional[str] = None, 
                          session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Log integration event with comprehensive details.
        
        Args:
            integration_id: Integration identifier
            event_type: Type of event (registration, execution, error, etc.)
            event_data: Event data dictionary
            level: Log level (INFO, WARNING, ERROR, etc.)
            user_id: User ID who triggered event
            session_id: Session ID for tracking
            
        Returns:
            Log entry with success status and details
        """
        try:
            # Create log entry
            log_entry = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'integration_id': integration_id,
                'event_type': event_type,
                'level': level.value,
                'user_id': user_id,
                'session_id': session_id,
                'event_data': event_data,
                'source_ip': self._get_source_ip(),
                'user_agent': self._get_user_agent(),
                'request_id': self._generate_request_id(),
                'correlation_id': self._generate_correlation_id(integration_id, event_type)
            }
            
            # Add to buffer
            self.log_buffer.append(log_entry)
            
            # Update statistics
            self._update_audit_stats(level)
            
            # Check if buffer should be flushed
            if len(self.log_buffer) >= 100:  # Flush every 100 entries
                self._flush_log_buffer()
            
            return {
                'success': True,
                'log_id': log_entry['id'],
                'timestamp': log_entry['timestamp'],
                'message': 'Integration event logged successfully'
            }
            
        except Exception as e:
            logger.error(f"Error logging integration event: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def log_registration(self, integration_id: str, integration_type: IntegrationType, 
                      config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Log integration registration event."""
        try:
            event_data = {
                'integration_type': integration_type.value,
                'config_hash': self._hash_config(config),
                'config_size': len(json.dumps(config)),
                'registration_status': IntegrationStatus.ACTIVE.value
            }
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='registration',
                event_data=event_data,
                level=IntegrationLogLevel.INFO,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error logging registration: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_execution(self, integration_id: str, operation: str, 
                   parameters: Dict[str, Any], result: Dict[str, Any], 
                   execution_time_ms: float, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Log integration execution event."""
        try:
            event_data = {
                'operation': operation,
                'parameters': parameters,
                'result': result,
                'execution_time_ms': execution_time_ms,
                'success': result.get('success', False),
                'error_code': result.get('error_code'),
                'response_size': len(json.dumps(result))
            }
            
            level = IntegrationLogLevel.ERROR if not result.get('success') else IntegrationLogLevel.INFO
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='execution',
                event_data=event_data,
                level=level,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error logging execution: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_error(self, integration_id: str, error_type: str, 
                 error_message: str, error_code: str, 
                 context: Dict[str, Any] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Log integration error event."""
        try:
            event_data = {
                'error_type': error_type,
                'error_message': error_message,
                'error_code': error_code,
                'context': context or {},
                'stack_trace': self._get_stack_trace()
            }
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='error',
                event_data=event_data,
                level=IntegrationLogLevel.ERROR,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error logging error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_security_event(self, integration_id: str, security_event: str, 
                        details: Dict[str, Any], user_id: str, 
                        source_ip: str, risk_level: str = 'medium') -> Dict[str, Any]:
        """Log security-related event."""
        try:
            event_data = {
                'security_event': security_event,
                'details': details,
                'source_ip': source_ip,
                'risk_level': risk_level,
                'blocked': False,
                'action_taken': 'logged'
            }
            
            level = IntegrationLogLevel.WARNING if risk_level == 'low' else IntegrationLogLevel.ERROR
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='security',
                event_data=event_data,
                level=level,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_performance_event(self, integration_id: str, metric_name: str, 
                          metric_value: float, unit: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Log performance metric event."""
        try:
            event_data = {
                'metric_name': metric_name,
                'metric_value': metric_value,
                'unit': unit,
                'context': context or {}
            }
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='performance',
                event_data=event_data,
                level=IntegrationLogLevel.INFO,
                user_id=None
            )
            
        except Exception as e:
            logger.error(f"Error logging performance event: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def log_compliance_event(self, integration_id: str, compliance_type: str, 
                           details: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Log compliance-related event."""
        try:
            event_data = {
                'compliance_type': compliance_type,
                'details': details,
                'regulation': self._get_regulation_for_type(compliance_type)
            }
            
            return self.log_integration_event(
                integration_id=integration_id,
                event_type='compliance',
                event_data=event_data,
                level=IntegrationLogLevel.INFO,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error logging compliance event: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_logs(self, integration_id: Optional[str] = None, 
                  event_type: Optional[str] = None, 
                  level: Optional[IntegrationLogLevel] = None,
                  start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, 
                  limit: int = 100) -> Dict[str, Any]:
        """Search audit logs with filters."""
        try:
            # This would search through stored logs
            # For now, return buffer contents as example
            filtered_logs = self.log_buffer.copy()
            
            # Apply filters
            if integration_id:
                filtered_logs = [log for log in filtered_logs if log['integration_id'] == integration_id]
            
            if event_type:
                filtered_logs = [log for log in filtered_logs if log['event_type'] == event_type]
            
            if level:
                filtered_logs = [log for log in filtered_logs if log['level'] == level.value]
            
            if start_time:
                filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log['timestamp']) >= start_time]
            
            if end_time:
                filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log['timestamp']) <= end_time]
            
            # Apply limit
            filtered_logs = filtered_logs[:limit]
            
            return {
                'success': True,
                'logs': filtered_logs,
                'total_found': len(filtered_logs),
                'filters_applied': {
                    'integration_id': integration_id,
                    'event_type': event_type,
                    'level': level.value if level else None,
                    'start_time': start_time.isoformat() if start_time else None,
                    'end_time': end_time.isoformat() if end_time else None
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit logging statistics."""
        try:
            return {
                'success': True,
                'stats': self.audit_stats,
                'log_levels': self.log_levels,
                'integration_types': INTEGRATION_TYPES,
                'integration_statuses': INTEGRATION_STATUSES,
                'retention_days': self.retention_days,
                'buffer_size': len(self.log_buffer),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting audit stats: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def export_logs(self, integration_id: Optional[str] = None, 
                  format_type: str = 'json', start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Export audit logs in specified format."""
        try:
            # Get filtered logs
            search_result = self.search_logs(integration_id, start_time=start_time, end_time=end_time)
            
            if not search_result['success']:
                return search_result
            
            logs = search_result['logs']
            
            if format_type == 'json':
                return {
                    'success': True,
                    'format': 'json',
                    'logs': logs,
                    'exported_at': datetime.now().isoformat()
                }
            elif format_type == 'csv':
                # Convert to CSV format
                csv_data = self._convert_to_csv(logs)
                return {
                    'success': True,
                    'format': 'csv',
                    'logs': csv_data,
                    'exported_at': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': f'Unsupported export format: {format_type}',
                    'supported_formats': ['json', 'csv']
                }
            
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def cleanup_old_logs(self) -> Dict[str, Any]:
        """Clean up old audit logs based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Count logs to be deleted
            logs_to_delete = [
                log for log in self.log_buffer
                if datetime.fromisoformat(log['timestamp']) < cutoff_date
            ]
            
            # Delete old logs
            original_count = len(self.log_buffer)
            self.log_buffer = [
                log for log in self.log_buffer
                if datetime.fromisoformat(log['timestamp']) >= cutoff_date
            ]
            
            deleted_count = original_count - len(self.log_buffer)
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'retention_days': self.retention_days,
                'cutoff_date': cutoff_date.isoformat(),
                'remaining_logs': len(self.log_buffer),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _flush_log_buffer(self):
        """Flush log buffer to storage."""
        try:
            # This would persist logs to database or file
            # For now, just log that buffer was flushed
            logger.info(f"Flushing {len(self.log_buffer)} audit log entries")
            
            # Clear buffer
            self.log_buffer.clear()
            
        except Exception as e:
            logger.error(f"Error flushing log buffer: {e}")
    
    def _update_audit_stats(self, level: IntegrationLogLevel):
        """Update audit statistics."""
        try:
            self.audit_stats['total_logs'] += 1
            self.audit_stats['logs_by_level'][level.value] += 1
            
            # Update average log size
            if self.log_buffer:
                total_size = sum(len(json.dumps(log['event_data'])) for log in self.log_buffer)
                self.audit_stats['avg_log_size_bytes'] = total_size / len(self.log_buffer)
            
        except Exception as e:
            logger.error(f"Error updating audit stats: {e}")
    
    def _get_source_ip(self) -> str:
        """Get source IP address from request context."""
        try:
            # This would extract from request context
            # For now, return placeholder
            return '127.0.0.1'
        except Exception:
            return 'unknown'
    
    def _get_user_agent(self) -> str:
        """Get user agent from request context."""
        try:
            # This would extract from request context
            # For now, return placeholder
            return 'Integration System'
        except Exception:
            return 'unknown'
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        try:
            return str(uuid.uuid4())
        except Exception:
            return str(uuid.uuid4())
    
    def _generate_correlation_id(self, integration_id: str, event_type: str) -> str:
        """Generate correlation ID for related events."""
        try:
            return f"{integration_id}_{event_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        except Exception:
            return f"{integration_id}_{event_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def _hash_config(self, config: Dict[str, Any]) -> str:
        """Hash configuration for integrity checking."""
        try:
            import hashlib
            config_str = json.dumps(config, sort_keys=True)
            return hashlib.sha256(config_str.encode()).hexdigest()
        except Exception:
            return 'unknown'
    
    def _get_stack_trace(self) -> str:
        """Get current stack trace."""
        try:
            import traceback
            return traceback.format_exc()
        except Exception:
            return 'unavailable'
    
    def _get_regulation_for_type(self, compliance_type: str) -> str:
        """Get applicable regulation for compliance type."""
        try:
            regulations = {
                'gdpr': 'personal_data_protection',
                'hipaa': 'health_information',
                'pci_dss': 'payment_card',
                'sox': 'financial_reporting'
            }
            
            mapping = {
                'data_privacy': 'gdpr',
                'health_data': 'hipaa',
                'payment_processing': 'pci_dss',
                'financial_reporting': 'sox'
            }
            
            return regulations.get(compliance_type, 'general')
        except Exception:
            return 'general'
    
    def _convert_to_csv(self, logs: List[Dict[str, Any]]) -> str:
        """Convert logs to CSV format."""
        try:
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            header = ['id', 'timestamp', 'integration_id', 'event_type', 'level', 'user_id', 'event_data']
            writer.writerow(header)
            
            # Write log entries
            for log in logs:
                writer.writerow([
                    log['id'],
                    log['timestamp'],
                    log['integration_id'],
                    log['event_type'],
                    log['level'],
                    log['user_id'],
                    json.dumps(log['event_data'])
                ])
            
            return output.getvalue()
        except Exception as e:
            logger.error(f"Error converting to CSV: {e}")
            return ''
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on audit logger."""
        try:
            # Test basic logging functionality
            test_log = self.log_integration_event(
                integration_id='health_check',
                event_type='test',
                event_data={'test': True},
                level=IntegrationLogLevel.INFO
            )
            
            # Check buffer functionality
            buffer_healthy = len(self.log_buffer) < 10000  # Max 10k entries in buffer
            
            # Check statistics
            stats_healthy = self.audit_stats['total_logs'] >= 0
            
            overall_healthy = test_log['success'] and buffer_healthy and stats_healthy
            
            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'test_log': test_log,
                'buffer_size': len(self.log_buffer),
                'stats': self.audit_stats,
                'retention_days': self.retention_days,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in audit logger health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
integ_audit_logger = IntegrationAuditLogger()
