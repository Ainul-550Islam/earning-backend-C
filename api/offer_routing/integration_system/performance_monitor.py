"""
Performance Monitor

Performance monitoring service for integration system
to track system health and performance metrics.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
import psutil
import time
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    ERROR_CODES
)
from ..exceptions import (
    IntegrationError, PerformanceError
)

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Performance monitoring service for integration system.
    
    Provides comprehensive performance monitoring for:
    - System resource usage
    - Integration execution times
    - Error rates and patterns
    - Throughput and latency metrics
    - Health checks and alerts
    - Performance trend analysis
    """
    
    def __init__(self):
        self.performance_metrics = {
            'system_resources': {
                'cpu_usage': 0.0,
                'memory_usage': 0.0,
                'disk_usage': 0.0,
                'network_io': 0.0
            },
            'integration_performance': {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'avg_execution_time_ms': 0.0,
                'max_execution_time_ms': 0.0,
                'min_execution_time_ms': 0.0,
                'error_rate': 0.0
            },
            'throughput_metrics': {
                'requests_per_second': 0.0,
                'responses_per_second': 0.0,
                'bytes_per_second': 0.0,
                'concurrent_connections': 0
            },
            'latency_metrics': {
                'avg_response_time_ms': 0.0,
                'p50_response_time_ms': 0.0,
                'p95_response_time_ms': 0.0,
                'p99_response_time_ms': 0.0
            }
        }
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'error_rate': 5.0,
            'response_time_ms': 1000.0
        }
        self.performance_history = []
        self.alert_handlers = []
        self.monitoring_active = True
    
    def start_monitoring(self) -> Dict[str, Any]:
        """Start performance monitoring."""
        try:
            if self.monitoring_active:
                return {
                    'success': False,
                    'error': 'Monitoring is already active',
                    'status': 'already_running'
                }
            
            self.monitoring_active = True
            
            # Start system resource monitoring
            self._start_system_monitoring()
            
            # Start integration performance monitoring
            self._start_integration_monitoring()
            
            # Start alert monitoring
            self._start_alert_monitoring()
            
            return {
                'success': True,
                'message': 'Performance monitoring started',
                'timestamp': datetime.now().isoformat(),
                'monitoring_components': [
                    'system_resources',
                    'integration_performance',
                    'throughput_metrics',
                    'latency_metrics'
                ]
            }
            
        except Exception as e:
            logger.error(f"Error starting performance monitoring: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop performance monitoring."""
        try:
            if not self.monitoring_active:
                return {
                    'success': False,
                    'error': 'Monitoring is not active',
                    'status': 'not_running'
                }
            
            self.monitoring_active = False
            
            # Save final performance snapshot
            self._save_performance_snapshot()
            
            return {
                'success': True,
                'message': 'Performance monitoring stopped',
                'timestamp': datetime.now().isoformat(),
                'final_metrics': self.performance_metrics
            }
            
        except Exception as e:
            logger.error(f"Error stopping performance monitoring: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def record_integration_execution(self, integration_id: str, execution_time_ms: float, 
                              success: bool, error: Optional[str] = None) -> Dict[str, Any]:
        """Record integration execution performance."""
        try:
            # Update integration performance metrics
            self.performance_metrics['integration_performance']['total_executions'] += 1
            
            if success:
                self.performance_metrics['integration_performance']['successful_executions'] += 1
            else:
                self.performance_metrics['integration_performance']['failed_executions'] += 1
            
            # Update execution time statistics
            current_avg = self.performance_metrics['integration_performance']['avg_execution_time_ms']
            total_executions = self.performance_metrics['integration_performance']['total_executions']
            
            self.performance_metrics['integration_performance']['avg_execution_time_ms'] = (
                (current_avg * (total_executions - 1) + execution_time_ms) / total_executions
            )
            
            # Update min/max execution times
            if execution_time_ms > self.performance_metrics['integration_performance']['max_execution_time_ms']:
                self.performance_metrics['integration_performance']['max_execution_time_ms'] = execution_time_ms
            
            if execution_time_ms < self.performance_metrics['integration_performance']['min_execution_time_ms'] or execution_time_ms == 0:
                self.performance_metrics['integration_performance']['min_execution_time_ms'] = execution_time_ms
            
            # Update error rate
            self.performance_metrics['integration_performance']['error_rate'] = (
                self.performance_metrics['integration_performance']['failed_executions'] / total_executions * 100
            )
            
            # Check for performance alerts
            self._check_performance_alerts(integration_id, execution_time_ms, success, error)
            
            return {
                'success': True,
                'integration_id': integration_id,
                'execution_time_ms': execution_time_ms,
                'success': success,
                'error': error,
                'updated_metrics': self.performance_metrics['integration_performance']
            }
            
        except Exception as e:
            logger.error(f"Error recording integration execution: {e}")
            return {
                'success': False,
                'error': str(e),
                'integration_id': integration_id
            }
    
    def record_throughput_metrics(self, requests_count: int, responses_count: int, 
                              bytes_transferred: int, time_window_seconds: int = 60) -> Dict[str, Any]:
        """Record throughput metrics."""
        try:
            # Calculate throughput metrics
            self.performance_metrics['throughput_metrics']['requests_per_second'] = requests_count / time_window_seconds
            self.performance_metrics['throughput_metrics']['responses_per_second'] = responses_count / time_window_seconds
            self.performance_metrics['throughput_metrics']['bytes_per_second'] = bytes_transferred / time_window_seconds
            
            return {
                'success': True,
                'requests_per_second': self.performance_metrics['throughput_metrics']['requests_per_second'],
                'responses_per_second': self.performance_metrics['throughput_metrics']['responses_per_second'],
                'bytes_per_second': self.performance_metrics['throughput_metrics']['bytes_per_second'],
                'time_window_seconds': time_window_seconds
            }
            
        except Exception as e:
            logger.error(f"Error recording throughput metrics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def record_latency_metrics(self, response_times_ms: List[float]) -> Dict[str, Any]:
        """Record latency metrics."""
        try:
            if not response_times_ms:
                return {
                    'success': False,
                    'error': 'No response times provided'
                }
            
            # Calculate latency statistics
            response_times_ms.sort()
            
            self.performance_metrics['latency_metrics']['avg_response_time_ms'] = sum(response_times_ms) / len(response_times_ms)
            self.performance_metrics['latency_metrics']['min_response_time_ms'] = response_times_ms[0]
            self.performance_metrics['latency_metrics']['max_response_time_ms'] = response_times_ms[-1]
            
            # Calculate percentiles
            length = len(response_times_ms)
            self.performance_metrics['latency_metrics']['p50_response_time_ms'] = response_times_ms[int(length * 0.5)]
            self.performance_metrics['latency_metrics']['p95_response_time_ms'] = response_times_ms[int(length * 0.95)]
            self.performance_metrics['latency_metrics']['p99_response_time_ms'] = response_times_ms[int(length * 0.99)]
            
            return {
                'success': True,
                'avg_response_time_ms': self.performance_metrics['latency_metrics']['avg_response_time_ms'],
                'p50_response_time_ms': self.performance_metrics['latency_metrics']['p50_response_time_ms'],
                'p95_response_time_ms': self.performance_metrics['latency_metrics']['p95_response_time_ms'],
                'p99_response_time_ms': self.performance_metrics['latency_metrics']['p99_response_time_ms'],
                'sample_count': length
            }
            
        except Exception as e:
            logger.error(f"Error recording latency metrics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        try:
            return {
                'success': True,
                'metrics': self.performance_metrics,
                'timestamp': datetime.now().isoformat(),
                'monitoring_active': self.monitoring_active
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_performance_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance history."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Filter history within time window
            recent_history = [
                entry for entry in self.performance_history
                if datetime.fromisoformat(entry['timestamp']) > cutoff_time
            ]
            
            return {
                'success': True,
                'history': recent_history,
                'time_window_hours': hours,
                'total_entries': len(recent_history)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def set_alert_thresholds(self, thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Set alert thresholds."""
        try:
            # Validate thresholds
            valid_thresholds = ['cpu_usage', 'memory_usage', 'disk_usage', 'error_rate', 'response_time_ms']
            
            for key, value in thresholds.items():
                if key not in valid_thresholds:
                    return {
                        'success': False,
                        'error': f'Invalid threshold: {key}',
                        'valid_thresholds': valid_thresholds
                    }
                
                if not isinstance(value, (int, float)) or value < 0 or value > 100:
                    return {
                        'success': False,
                        'error': f'Invalid threshold value for {key}: {value}',
                        'valid_range': '0-100'
                    }
            
            # Update thresholds
            self.alert_thresholds.update(thresholds)
            
            return {
                'success': True,
                'message': 'Alert thresholds updated',
                'updated_thresholds': self.alert_thresholds
            }
            
        except Exception as e:
            logger.error(f"Error setting alert thresholds: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_alert_handler(self, handler: callable) -> Dict[str, Any]:
        """Add custom alert handler."""
        try:
            self.alert_handlers.append(handler)
            
            return {
                'success': True,
                'message': 'Alert handler added',
                'total_handlers': len(self.alert_handlers)
            }
            
        except Exception as e:
            logger.error(f"Error adding alert handler: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _start_system_monitoring(self):
        """Start system resource monitoring."""
        try:
            # This would start a background thread to monitor system resources
            # For now, simulate with current values
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('/')
            
            self.performance_metrics['system_resources']['cpu_usage'] = cpu_percent
            self.performance_metrics['system_resources']['memory_usage'] = memory_info.percent
            self.performance_metrics['system_resources']['disk_usage'] = disk_info.percent
            
            logger.debug(f"System resources - CPU: {cpu_percent}%, Memory: {memory_info.percent}%, Disk: {disk_info.percent}%")
            
        except Exception as e:
            logger.error(f"Error starting system monitoring: {e}")
    
    def _start_integration_monitoring(self):
        """Start integration performance monitoring."""
        try:
            # This would start monitoring integration executions
            # For now, just log that monitoring started
            logger.info("Integration performance monitoring started")
            
        except Exception as e:
            logger.error(f"Error starting integration monitoring: {e}")
    
    def _start_alert_monitoring(self):
        """Start alert monitoring."""
        try:
            # This would start checking for alerts based on thresholds
            # For now, just log that alert monitoring started
            logger.info("Alert monitoring started")
            
        except Exception as e:
            logger.error(f"Error starting alert monitoring: {e}")
    
    def _check_performance_alerts(self, integration_id: str, execution_time_ms: float, 
                                   success: bool, error: Optional[str]):
        """Check for performance alerts."""
        try:
            alerts = []
            
            # Check execution time alert
            if execution_time_ms > self.alert_thresholds['response_time_ms']:
                alerts.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'message': f'Execution time {execution_time_ms}ms exceeds threshold {self.alert_thresholds["response_time_ms"]}ms',
                    'integration_id': integration_id,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Check error rate alert
            if self.performance_metrics['integration_performance']['error_rate'] > self.alert_thresholds['error_rate']:
                alerts.append({
                    'type': 'error_rate',
                    'severity': 'critical',
                    'message': f'Error rate {self.performance_metrics["integration_performance"]["error_rate"]}% exceeds threshold {self.alert_thresholds["error_rate"]}%',
                    'integration_id': integration_id,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Trigger alert handlers
            for alert in alerts:
                for handler in self.alert_handlers:
                    try:
                        handler(alert)
                    except Exception as e:
                        logger.error(f"Error in alert handler: {e}")
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
    
    def _save_performance_snapshot(self):
        """Save performance snapshot to history."""
        try:
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'metrics': self.performance_metrics.copy(),
                'alert_thresholds': self.alert_thresholds.copy()
            }
            
            self.performance_history.append(snapshot)
            
            # Keep only last 1000 entries
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]
            
            logger.info("Performance snapshot saved to history")
            
        except Exception as e:
            logger.error(f"Error saving performance snapshot: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on performance monitor."""
        try:
            # Check system resource availability
            system_healthy = self._check_system_resources()
            
            # Check monitoring status
            monitoring_healthy = self.monitoring_active
            
            # Check alert handlers
            handlers_healthy = len(self.alert_handlers) > 0
            
            overall_healthy = system_healthy and monitoring_healthy and handlers_healthy
            
            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'system_resources': system_healthy,
                'monitoring_active': monitoring_healthy,
                'alert_handlers': handlers_healthy,
                'current_metrics': self.performance_metrics,
                'alert_thresholds': self.alert_thresholds,
                'history_entries': len(self.performance_history),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in performance monitor health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_system_resources(self) -> bool:
        """Check if system resources are accessible."""
        try:
            # Test CPU monitoring
            psutil.cpu_percent(interval=0.1)
            
            # Test memory monitoring
            psutil.virtual_memory()
            
            # Test disk monitoring
            psutil.disk_usage('/')
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return False
    
    def reset_metrics(self) -> Dict[str, Any]:
        """Reset performance metrics."""
        try:
            self.performance_metrics = {
                'system_resources': {
                    'cpu_usage': 0.0,
                    'memory_usage': 0.0,
                    'disk_usage': 0.0,
                    'network_io': 0.0
                },
                'integration_performance': {
                    'total_executions': 0,
                    'successful_executions': 0,
                    'failed_executions': 0,
                    'avg_execution_time_ms': 0.0,
                    'max_execution_time_ms': 0.0,
                    'min_execution_time_ms': 0.0,
                    'error_rate': 0.0
                },
                'throughput_metrics': {
                    'requests_per_second': 0.0,
                    'responses_per_second': 0.0,
                    'bytes_per_second': 0.0,
                    'concurrent_connections': 0
                },
                'latency_metrics': {
                    'avg_response_time_ms': 0.0,
                    'p50_response_time_ms': 0.0,
                    'p95_response_time_ms': 0.0,
                    'p99_response_time_ms': 0.0
                }
            }
            
            return {
                'success': True,
                'message': 'Performance metrics reset',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting performance metrics: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global instance
performance_monitor = PerformanceMonitor()
