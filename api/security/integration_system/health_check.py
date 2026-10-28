"""
Health Check Module
Health check system for integration components
"""

import logging
import time
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import HealthStatus

User = get_user_model()
logger = logging.getLogger('security.integration.health_check')


class HealthCheck:
    """Base health check"""
    
    def __init__(self, name: str, component_type: str):
        self.name = name
        self.component_type = component_type
        self.status = HealthStatus.UNKNOWN
        self.last_check = None
        self.check_interval = 60  # seconds
        self.timeout = 30  # seconds
        self.enabled = True
        self.dependencies = []
        self.metrics = {}
        self.alert_thresholds = {}
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute health check - override in subclasses"""
        raise NotImplementedError("Subclasses must implement execute_check")
    
    def can_execute(self) -> bool:
        """Check if health check can be executed"""
        return self.enabled
    
    def update_status(self, status: HealthStatus, metrics: Dict[str, Any] = None):
        """Update health status"""
        self.status = status
        self.last_check = timezone.now()
        
        if metrics:
            self.metrics.update(metrics)
        
        # Check alert thresholds
        self._check_alert_thresholds()
    
    def _check_alert_thresholds(self):
        """Check if alert thresholds are exceeded"""
        for metric_name, threshold_config in self.alert_thresholds.items():
            current_value = self.metrics.get(metric_name)
            
            if current_value is not None:
                if 'max' in threshold_config and current_value > threshold_config['max']:
                    self._trigger_alert(metric_name, 'max_threshold', current_value, threshold_config['max'])
                
                if 'min' in threshold_config and current_value < threshold_config['min']:
                    self._trigger_alert(metric_name, 'min_threshold', current_value, threshold_config['min'])
    
    def _trigger_alert(self, metric_name: str, alert_type: str, value: float, threshold: float):
        """Trigger health alert"""
        # Create security incident for critical health issues
        if self.status == HealthStatus.CRITICAL:
            SecurityIncident.objects.create(
                title=f"Health Alert: {self.name}",
                incident_type='health_check',
                severity='high',
                priority='medium',
                description=f"Health check failed: {self.name} - {metric_name} {alert_type}",
                metadata={
                    'component_name': self.name,
                    'component_type': self.component_type,
                    'metric_name': metric_name,
                    'alert_type': alert_type,
                    'value': value,
                    'threshold': threshold,
                    'health_status': self.status.value
                }
            )
        
        # Log health alert
        SecurityLog.objects.create(
            security_type='health_check',
            severity='warning',
            description=f"Health alert: {self.name} - {metric_name} {alert_type}",
            metadata={
                'component_name': self.name,
                'component_type': self.component_type,
                'metric_name': metric_name,
                'alert_type': alert_type,
                'value': value,
                'threshold': threshold,
                'health_status': self.status.value
            }
        )
        
        logger.warning(f"Health alert triggered: {self.name} - {metric_name} {alert_type} - {value} vs {threshold}")
    
    def add_dependency(self, component_name: str):
        """Add dependency"""
        if component_name not in self.dependencies:
            self.dependencies.append(component_name)
    
    def set_alert_threshold(self, metric_name: str, min_threshold: float = None, 
                           max_threshold: float = None):
        """Set alert threshold for metric"""
        if metric_name not in self.alert_thresholds:
            self.alert_thresholds[metric_name] = {}
        
        if min_threshold is not None:
            self.alert_thresholds[metric_name]['min'] = min_threshold
        
        if max_threshold is not None:
            self.alert_thresholds[metric_name]['max'] = max_threshold
    
    def get_status(self) -> Dict[str, Any]:
        """Get health check status"""
        return {
            'name': self.name,
            'component_type': self.component_type,
            'status': self.status.value,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'enabled': self.enabled,
            'dependencies': self.dependencies,
            'metrics': self.metrics,
            'alert_thresholds': self.alert_thresholds
        }
    
    def enable(self):
        """Enable health check"""
        self.enabled = True
    
    def disable(self):
        """Disable health check"""
        self.enabled = False


class DatabaseHealthCheck(HealthCheck):
    """Database health check"""
    
    def __init__(self, connection_name: str = 'default'):
        super().__init__(f"database_{connection_name}", "database")
        self.connection_name = connection_name
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute database health check"""
        try:
            from django.db import connections
            
            start_time = time.time()
            
            # Test connection
            with connections[self.connection_name].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Get connection pool info
            connection = connections[self.connection_name]
            pool_info = getattr(connection, 'pool', None)
            
            metrics = {
                'response_time_ms': response_time,
                'connection_alive': True,
                'pool_size': getattr(pool_info, 'size', 0) if pool_info else 0,
                'pool_used': getattr(pool_info, 'used', 0) if pool_info else 0
            }
            
            # Determine health status
            if response_time > 5000:  # 5 seconds
                status = HealthStatus.CRITICAL
            elif response_time > 2000:  # 2 seconds
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            self.update_status(status, metrics)
            
            return {
                'status': status.value,
                'response_time_ms': response_time,
                'connection_alive': True,
                'pool_info': metrics
            }
        
        except Exception as e:
            metrics = {
                'response_time_ms': None,
                'connection_alive': False,
                'error': str(e)
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e),
                'connection_alive': False
            }


class APIHealthCheck(HealthCheck):
    """API health check"""
    
    def __init__(self, api_name: str, endpoint_url: str, timeout: int = 30):
        super().__init__(f"api_{api_name}", "api")
        self.endpoint_url = endpoint_url
        self.timeout = timeout
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute API health check"""
        try:
            import requests
            
            start_time = time.time()
            
            response = requests.get(
                self.endpoint_url,
                timeout=self.timeout,
                headers={'User-Agent': 'Health-Check/1.0'}
            )
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            metrics = {
                'response_time_ms': response_time,
                'status_code': response.status_code,
                'endpoint_alive': True,
                'content_length': len(response.content) if response.content else 0
            }
            
            # Determine health status
            if response.status_code >= 500:
                status = HealthStatus.CRITICAL
            elif response.status_code >= 400:
                status = HealthStatus.DEGRADED
            elif response_time > 5000:  # 5 seconds
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            self.update_status(status, metrics)
            
            return {
                'status': status.value,
                'response_time_ms': response_time,
                'status_code': response.status_code,
                'endpoint_alive': True
            }
        
        except requests.exceptions.Timeout:
            metrics = {
                'response_time_ms': None,
                'endpoint_alive': False,
                'error': 'timeout'
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': 'timeout',
                'endpoint_alive': False
            }
        
        except Exception as e:
            metrics = {
                'response_time_ms': None,
                'endpoint_alive': False,
                'error': str(e)
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e),
                'endpoint_alive': False
            }


class CacheHealthCheck(HealthCheck):
    """Cache health check"""
    
    def __init__(self, cache_name: str = 'default'):
        super().__init__(f"cache_{cache_name}", "cache")
        self.cache_name = cache_name
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute cache health check"""
        try:
            test_key = f"health_check_{self.cache_name}_{int(time.time())}"
            test_value = "health_check_value"
            
            start_time = time.time()
            
            # Test set
            cache.set(test_key, test_value, timeout=60)
            
            # Test get
            retrieved_value = cache.get(test_key)
            
            # Clean up
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            metrics = {
                'response_time_ms': response_time,
                'cache_working': retrieved_value == test_value,
                'test_passed': True
            }
            
            # Determine health status
            if not retrieved_value == test_value:
                status = HealthStatus.CRITICAL
            elif response_time > 1000:  # 1 second
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            self.update_status(status, metrics)
            
            return {
                'status': status.value,
                'response_time_ms': response_time,
                'cache_working': retrieved_value == test_value
            }
        
        except Exception as e:
            metrics = {
                'response_time_ms': None,
                'cache_working': False,
                'error': str(e)
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e),
                'cache_working': False
            }


class QueueHealthCheck(HealthCheck):
    """Queue health check"""
    
    def __init__(self, queue_name: str):
        super().__init__(f"queue_{queue_name}", "queue")
        self.queue_name = queue_name
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute queue health check"""
        try:
            from .message_queue import message_queue_manager
            
            queue = message_queue_manager.get_queue(self.queue_name)
            
            if not queue:
                metrics = {
                    'queue_exists': False,
                    'queue_size': 0,
                    'error': 'Queue not found'
                }
                
                self.update_status(HealthStatus.UNHEALTHY, metrics)
                
                return {
                    'status': HealthStatus.UNHEALTHY.value,
                    'error': 'Queue not found'
                }
            
            status = queue.get_status()
            
            metrics = {
                'queue_exists': True,
                'queue_size': status['queue_size'],
                'processing_count': status['processing_count'],
                'enabled': status['enabled'],
                'subscriber_count': status['subscriber_count']
            }
            
            # Determine health status
            if not status['enabled']:
                health_status = HealthStatus.DEGRADED
            elif status['queue_size'] > status['max_size'] * 0.9:  # 90% full
                health_status = HealthStatus.DEGRADED
            else:
                health_status = HealthStatus.HEALTHY
            
            self.update_status(health_status, metrics)
            
            return {
                'status': health_status.value,
                'queue_size': status['queue_size'],
                'processing_count': status['processing_count'],
                'enabled': status['enabled']
            }
        
        except Exception as e:
            metrics = {
                'queue_exists': False,
                'queue_size': 0,
                'error': str(e)
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e)
            }


class IntegrationHealthCheck(HealthCheck):
    """Integration health check"""
    
    def __init__(self, integration_name: str):
        super().__init__(f"integration_{integration_name}", "integration")
        self.integration_name = integration_name
    
    def execute_check(self) -> Dict[str, Any]:
        """Execute integration health check"""
        try:
            from .integ_handler import integration_handler
            
            handler_status = integration_handler.get_handler_status(self.integration_name)
            
            metrics = {
                'handler_active': handler_status['active'],
                'error_count': handler_status['error_count'],
                'last_execution_time': handler_status.get('last_execution_time'),
                'enabled': handler_status['enabled']
            }
            
            # Determine health status
            if not handler_status['enabled']:
                health_status = HealthStatus.DEGRADED
            elif handler_status['error_count'] > 10:
                health_status = HealthStatus.DEGRADED
            elif not handler_status['active']:
                health_status = HealthStatus.WARNING
            else:
                health_status = HealthStatus.HEALTHY
            
            self.update_status(health_status, metrics)
            
            return {
                'status': health_status.value,
                'handler_active': handler_status['active'],
                'error_count': handler_status['error_count'],
                'enabled': handler_status['enabled']
            }
        
        except Exception as e:
            metrics = {
                'handler_active': False,
                'error_count': 0,
                'error': str(e)
            }
            
            self.update_status(HealthStatus.UNHEALTHY, metrics)
            
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e)
            }


class HealthCheckManager:
    """Manager for health checks"""
    
    def __init__(self):
        self.health_checks = {}
        self.enabled = True
        self.check_interval = 60  # seconds
        self.alert_thresholds = {
            'critical_components': 0,
            'degraded_components': 2
        }
        self.last_global_check = None
        self.global_status = HealthStatus.HEALTHY
    
    def add_health_check(self, health_check: HealthCheck):
        """Add health check"""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Added health check: {health_check.name}")
    
    def remove_health_check(self, check_name: str) -> bool:
        """Remove health check"""
        if check_name in self.health_checks:
            del self.health_checks[check_name]
            logger.info(f"Removed health check: {check_name}")
            return True
        return False
    
    def get_health_check(self, check_name: str) -> Optional[HealthCheck]:
        """Get health check by name"""
        return self.health_checks.get(check_name)
    
    def execute_all_checks(self) -> Dict[str, Any]:
        """Execute all health checks"""
        results = {}
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.WARNING: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.CRITICAL: 0,
            HealthStatus.UNKNOWN: 0
        }
        
        for check_name, health_check in self.health_checks.items():
            if health_check.can_execute():
                try:
                    result = health_check.execute_check()
                    results[check_name] = result
                    
                    # Count statuses
                    status = HealthStatus(result.get('status', 'unknown'))
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                except Exception as e:
                    logger.error(f"Error executing health check {check_name}: {e}")
                    results[check_name] = {
                        'status': HealthStatus.UNHEALTHY.value,
                        'error': str(e)
                    }
                    status_counts[HealthStatus.UNHEALTHY] += 1
            else:
                results[check_name] = {
                    'status': HealthStatus.UNKNOWN.value,
                    'message': 'Health check disabled'
                }
                status_counts[HealthStatus.UNKNOWN] += 1
        
        # Determine global status
        self.global_status = self._determine_global_status(status_counts)
        self.last_global_check = timezone.now()
        
        # Check alert thresholds
        self._check_global_alerts(status_counts)
        
        return {
            'global_status': self.global_status.value,
            'last_check': self.last_global_check.isoformat(),
            'status_counts': {status.value: count for status, count in status_counts.items()},
            'health_checks': results
        }
    
    def _determine_global_status(self, status_counts: Dict[HealthStatus, int]) -> HealthStatus:
        """Determine global health status"""
        total_checks = sum(status_counts.values())
        
        if total_checks == 0:
            return HealthStatus.UNKNOWN
        
        critical_count = status_counts.get(HealthStatus.CRITICAL, 0)
        unhealthy_count = status_counts.get(HealthStatus.UNHEALTHY, 0)
        degraded_count = status_counts.get(HealthStatus.DEGRADED, 0)
        
        if critical_count > 0:
            return HealthStatus.CRITICAL
        elif unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count >= self.alert_thresholds['degraded_components']:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _check_global_alerts(self, status_counts: Dict[HealthStatus, int]):
        """Check global alert thresholds"""
        critical_count = status_counts.get(HealthStatus.CRITICAL, 0)
        
        if critical_count >= self.alert_thresholds['critical_components']:
            SecurityIncident.objects.create(
                title="Critical System Health Alert",
                incident_type='health_check',
                severity='critical',
                priority='critical',
                description=f"Multiple critical health issues detected: {critical_count} components",
                metadata={
                    'critical_count': critical_count,
                    'status_counts': {status.value: count for status, count in status_counts.items()},
                    'global_status': self.global_status.value
                }
            )
    
    def get_global_status(self) -> Dict[str, Any]:
        """Get global health status"""
        return {
            'enabled': self.enabled,
            'global_status': self.global_status.value,
            'last_global_check': self.last_global_check.isoformat() if self.last_global_check else None,
            'total_checks': len(self.health_checks),
            'alert_thresholds': self.alert_thresholds
        }
    
    def get_component_health(self, component_name: str) -> Dict[str, Any]:
        """Get health of specific component"""
        health_check = self.get_health_check(component_name)
        
        if health_check:
            return health_check.get_status()
        else:
            return {
                'status': HealthStatus.UNKNOWN.value,
                'message': 'Health check not found'
            }
    
    def enable_all_checks(self):
        """Enable all health checks"""
        for health_check in self.health_checks.values():
            health_check.enable()
    
    def disable_all_checks(self):
        """Disable all health checks"""
        for health_check in self.health_checks.values():
            health_check.disable()
    
    def enable(self):
        """Enable health check manager"""
        self.enabled = True
        logger.info("Health check manager enabled")
    
    def disable(self):
        """Disable health check manager"""
        self.enabled = False
        logger.info("Health check manager disabled")


# Global health check manager
health_check_manager = HealthCheckManager()


# Create default health checks
def create_default_health_checks():
    """Create default health checks"""
    
    # Database health check
    db_check = DatabaseHealthCheck('default')
    db_check.set_alert_threshold('response_time_ms', max_threshold=5000)
    health_check_manager.add_health_check(db_check)
    
    # Cache health check
    cache_check = CacheHealthCheck('default')
    cache_check.set_alert_threshold('response_time_ms', max_threshold=1000)
    health_check_manager.add_health_check(cache_check)
    
    # Queue health checks
    queue_check = QueueHealthCheck('default')
    queue_check.set_alert_threshold('queue_size', max_threshold=9000)
    health_check_manager.add_health_check(queue_check)
    
    queue_check = QueueHealthCheck('security_events')
    queue_check.set_alert_threshold('queue_size', max_threshold=900)
    health_check_manager.add_health_check(queue_check)
    
    logger.info("Created default health checks")


# Initialize default health checks
create_default_health_checks()


# Export symbols
__all__ = [
    'HealthCheck',
    'DatabaseHealthCheck',
    'APIHealthCheck',
    'CacheHealthCheck',
    'QueueHealthCheck',
    'IntegrationHealthCheck',
    'HealthCheckManager',
    'health_check_manager',
    'create_default_health_checks'
]