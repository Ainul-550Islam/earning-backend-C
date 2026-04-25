"""Health Check System

This module provides comprehensive health checking for integration system
with detailed component monitoring and status reporting.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_constants import HealthStatus
from .integ_exceptions import IntegrationError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class HealthCheck:
    """Base health check class."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        """Initialize the health check."""
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load health check configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.interval = self.config.get('interval', 60)  # seconds
            self.failure_threshold = self.config.get('failure_threshold', 3)
            self.recovery_threshold = self.config.get('recovery_threshold', 2)
            
            # State tracking
            self.status = HealthStatus.HEALTHY
            self.last_check = None
            self.failure_count = 0
            self.recovery_count = 0
            self.total_checks = 0
            self.total_failures = 0
            
        except Exception as e:
            self.logger.error(f"Error loading health check configuration: {str(e)}")
            self.enabled = True
            self.timeout = 30
            self.interval = 60
            self.failure_threshold = 3
            self.recovery_threshold = 2
    
    def check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health check result
        """
        raise NotImplementedError("Subclasses must implement check method")
    
    def execute_check(self) -> Dict[str, Any]:
        """
        Execute health check with state tracking.
        
        Returns:
            Health check result
        """
        try:
            if not self.enabled:
                return {
                    'name': self.name,
                    'status': HealthStatus.DISABLED,
                    'message': 'Health check is disabled',
                    'checked_at': timezone.now().isoformat()
                }
            
            self.total_checks += 1
            self.last_check = timezone.now()
            
            # Perform actual check
            result = self.check()
            
            # Update state based on result
            new_status = result.get('status', HealthStatus.HEALTHY)
            self._update_status(new_status)
            
            # Add metadata
            result.update({
                'name': self.name,
                'checked_at': self.last_check.isoformat(),
                'failure_count': self.failure_count,
                'recovery_count': self.recovery_count,
                'total_checks': self.total_checks,
                'total_failures': self.total_failures
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing health check {self.name}: {str(e)}")
            self.total_failures += 1
            self.failure_count += 1
            
            return {
                'name': self.name,
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat(),
                'failure_count': self.failure_count,
                'total_checks': self.total_checks,
                'total_failures': self.total_failures
            }
    
    def _update_status(self, new_status: str):
        """Update health check status."""
        try:
            old_status = self.status
            self.status = new_status
            
            # Update counters
            if new_status == HealthStatus.UNHEALTHY:
                self.failure_count += 1
                self.recovery_count = 0
                self.total_failures += 1
            elif new_status == HealthStatus.HEALTHY:
                self.recovery_count += 1
                self.failure_count = 0
            
            # Log status changes
            if old_status != new_status:
                self.logger.info(f"Health check {self.name} status changed: {old_status} -> {new_status}")
                
        except Exception as e:
            self.logger.error(f"Error updating status: {str(e)}")
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get health check status information."""
        return {
            'name': self.name,
            'status': self.status,
            'enabled': self.enabled,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'failure_count': self.failure_count,
            'recovery_count': self.recovery_count,
            'total_checks': self.total_checks,
            'total_failures': self.total_failures,
            'failure_threshold': self.failure_threshold,
            'recovery_threshold': self.recovery_threshold
        }


class DatabaseHealthCheck(HealthCheck):
    """Database health check."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the database health check."""
        super().__init__('database', config)
    
    def check(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            from django.db import connection
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Check connection pool
            connection.close()
            
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'Database connection successful',
                'details': {
                    'connection_test': 'passed'
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Database connection failed',
                'error': str(e),
                'details': {
                    'connection_test': 'failed'
                }
            }


class CacheHealthCheck(HealthCheck):
    """Cache health check."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the cache health check."""
        super().__init__('cache', config)
    
    def check(self) -> Dict[str, Any]:
        """Check cache health."""
        try:
            # Test cache operations
            test_key = 'health_check_test'
            test_value = {'test': True, 'timestamp': timezone.now().isoformat()}
            
            # Set test value
            cache.set(test_key, test_value, timeout=10)
            
            # Get test value
            retrieved = cache.get(test_key)
            
            # Delete test key
            cache.delete(test_key)
            
            if retrieved == test_value:
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': 'Cache operations successful',
                    'details': {
                        'set_test': 'passed',
                        'get_test': 'passed',
                        'delete_test': 'passed'
                    }
                }
            else:
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'message': 'Cache operations failed',
                    'details': {
                        'set_test': 'passed',
                        'get_test': 'failed',
                        'delete_test': 'failed'
                    }
                }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Cache health check failed',
                'error': str(e),
                'details': {
                    'set_test': 'failed',
                    'get_test': 'failed',
                    'delete_test': 'failed'
                }
            }


class IntegrationHealthCheck(HealthCheck):
    """Integration system health check."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the integration health check."""
        super().__init__('integration', config)
    
    def check(self) -> Dict[str, Any]:
        """Check integration system health."""
        try:
            # Test integration components
            components = {}
            
            # Test handlers
            from .integ_handler import IntegrationHandler
            handler = IntegrationHandler()
            handler_health = handler.health_check()
            components['handler'] = handler_health
            
            # Test adapters
            from .integ_adapter import IntegrationAdapter
            adapter = IntegrationAdapter()
            adapter_health = adapter.health_check()
            components['adapter'] = adapter_health
            
            # Test bridges
            from .bridge import BridgeManager
            bridge_manager = BridgeManager()
            bridge_health = bridge_manager.health_check()
            components['bridge'] = bridge_health
            
            # Determine overall status
            overall_status = HealthStatus.HEALTHY
            unhealthy_components = []
            
            for component_name, component_health in components.items():
                if component_health.get('status') != HealthStatus.HEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                    unhealthy_components.append(component_name)
            
            return {
                'status': overall_status,
                'message': 'Integration system health check completed',
                'details': {
                    'components': components,
                    'unhealthy_components': unhealthy_components
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Integration health check failed',
                'error': str(e),
                'details': {}
            }


class WebhookHealthCheck(HealthCheck):
    """Webhook system health check."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the webhook health check."""
        super().__init__('webhook', config)
    
    def check(self) -> Dict[str, Any]:
        """Check webhook system health."""
        try:
            # Test webhook components
            components = {}
            
            # Test webhook integration
            from .webhooks_integration import WebhooksIntegration
            webhook_integration = WebhooksIntegration()
            webhook_health = webhook_integration.health_check()
            components['webhook_integration'] = webhook_health
            
            # Test message queue
            from .message_queue import message_queue
            queue_health = message_queue.health_check()
            components['message_queue'] = queue_health
            
            # Test event bus
            from .event_bus import event_bus
            event_bus_health = event_bus.health_check()
            components['event_bus'] = event_bus_health
            
            # Determine overall status
            overall_status = HealthStatus.HEALTHY
            unhealthy_components = []
            
            for component_name, component_health in components.items():
                if component_health.get('status') != HealthStatus.HEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                    unhealthy_components.append(component_name)
            
            return {
                'status': overall_status,
                'message': 'Webhook system health check completed',
                'details': {
                    'components': components,
                    'unhealthy_components': unhealthy_components
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Webhook health check failed',
                'error': str(e),
                'details': {}
            }


class SystemHealthCheck(HealthCheck):
    """System resource health check."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the system health check."""
        super().__init__('system', config)
    
    def check(self) -> Dict[str, Any]:
        """Check system resource health."""
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Check thresholds
            cpu_status = HealthStatus.HEALTHY
            memory_status = HealthStatus.HEALTHY
            disk_status = HealthStatus.HEALTHY
            
            if cpu_percent > 90:
                cpu_status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70:
                cpu_status = HealthStatus.DEGRADED
            
            if memory.percent > 90:
                memory_status = HealthStatus.UNHEALTHY
            elif memory.percent > 70:
                memory_status = HealthStatus.DEGRADED
            
            if disk.percent > 90:
                disk_status = HealthStatus.UNHEALTHY
            elif disk.percent > 80:
                disk_status = HealthStatus.DEGRADED
            
            # Determine overall status
            statuses = [cpu_status, memory_status, disk_status]
            if HealthStatus.UNHEALTHY in statuses:
                overall_status = HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in statuses:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
            
            return {
                'status': overall_status,
                'message': 'System resource health check completed',
                'details': {
                    'cpu': {
                        'usage_percent': cpu_percent,
                        'status': cpu_status
                    },
                    'memory': {
                        'usage_percent': memory.percent,
                        'available_gb': memory.available / (1024**3),
                        'status': memory_status
                    },
                    'disk': {
                        'usage_percent': disk.percent,
                        'free_gb': disk.free / (1024**3),
                        'status': disk_status
                    }
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'System health check failed',
                'error': str(e),
                'details': {}
            }


class HealthCheckManager:
    """
    Main health check manager for integration system.
    Coordinates multiple health checks and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the health check manager."""
        self.logger = logger
        self.monitor = PerformanceMonitor()
        
        # Health check storage
        self.health_checks = {}
        self.check_history = []
        
        # Load configuration
        self._load_configuration()
        
        # Initialize health checks
        self._initialize_health_checks()
        
        # Start background monitoring
        self._start_background_monitoring()
    
    def _load_configuration(self):
        """Load health check configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_HEALTH_CHECK_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.default_interval = self.config.get('default_interval', 60)
            self.max_history_size = self.config.get('max_history_size', 1000)
            self.alert_on_failure = self.config.get('alert_on_failure', True)
            
        except Exception as e:
            self.logger.error(f"Error loading health check configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.default_interval = 60
            self.max_history_size = 1000
            self.alert_on_failure = True
    
    def _initialize_health_checks(self):
        """Initialize health checks."""
        try:
            # Initialize built-in health checks
            health_check_configs = self.config.get('health_checks', {})
            
            self.health_checks['database'] = DatabaseHealthCheck(health_check_configs.get('database', {}))
            self.health_checks['cache'] = CacheHealthCheck(health_check_configs.get('cache', {}))
            self.health_checks['integration'] = IntegrationHealthCheck(health_check_configs.get('integration', {}))
            self.health_checks['webhook'] = WebhookHealthCheck(health_check_configs.get('webhook', {}))
            self.health_checks['system'] = SystemHealthCheck(health_check_configs.get('system', {}))
            
            self.logger.info(f"Initialized {len(self.health_checks)} health checks")
            
        except Exception as e:
            self.logger.error(f"Error initializing health checks: {str(e)}")
    
    def _start_background_monitoring(self):
        """Start background health monitoring."""
        try:
            # This would integrate with your background task system
            # For now, just log that monitoring is enabled
            self.logger.info("Background health monitoring enabled")
            
        except Exception as e:
            self.logger.error(f"Error starting background monitoring: {str(e)}")
    
    def check_health(self, check_name: str = None) -> Dict[str, Any]:
        """
        Perform health check.
        
        Args:
            check_name: Optional specific health check name
            
        Returns:
            Health check result
        """
        try:
            with self.monitor.measure_fallback('health_check') as measurement:
                if check_name:
                    if check_name in self.health_checks:
                        result = self.health_checks[check_name].execute_check()
                        self._add_to_history(result)
                        return result
                    else:
                        return {
                            'error': f'Health check {check_name} not found',
                            'checked_at': timezone.now().isoformat()
                        }
                else:
                    # Perform all health checks
                    results = {}
                    overall_status = HealthStatus.HEALTHY
                    
                    for name, health_check in self.health_checks.items():
                        try:
                            result = health_check.execute_check()
                            results[name] = result
                            
                            if result.get('status') != HealthStatus.HEALTHY:
                                overall_status = HealthStatus.UNHEALTHY
                                
                        except Exception as e:
                            self.logger.error(f"Error in health check {name}: {str(e)}")
                            results[name] = {
                                'name': name,
                                'status': HealthStatus.UNHEALTHY,
                                'error': str(e),
                                'checked_at': timezone.now().isoformat()
                            }
                            overall_status = HealthStatus.UNHEALTHY
                    
                    final_result = {
                        'overall_status': overall_status,
                        'checks': results,
                        'checked_at': timezone.now().isoformat(),
                        'performance': measurement.get_metrics()
                    }
                    
                    self._add_to_history(final_result)
                    
                    # Alert on failure if enabled
                    if self.alert_on_failure and overall_status != HealthStatus.HEALTHY:
                        self._send_alert(final_result)
                    
                    return final_result
                    
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall_status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }
    
    def _add_to_history(self, result: Dict[str, Any]):
        """Add health check result to history."""
        try:
            self.check_history.append(result)
            
            # Limit history size
            if len(self.check_history) > self.max_history_size:
                self.check_history = self.check_history[-self.max_history_size:]
                
        except Exception as e:
            self.logger.error(f"Error adding to history: {str(e)}")
    
    def _send_alert(self, result: Dict[str, Any]):
        """Send health check alert."""
        try:
            # This would integrate with your alert system
            self.logger.critical(f"Health check alert: {result['overall_status']}")
            
        except Exception as e:
            self.logger.error(f"Error sending alert: {str(e)}")
    
    def get_health_history(self, check_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get health check history.
        
        Args:
            check_name: Optional specific health check name
            limit: Maximum number of entries to return
            
        Returns:
            Health check history
        """
        try:
            history = self.check_history
            
            # Filter by check name
            if check_name:
                history = [
                    entry for entry in history
                    if 'checks' in entry and check_name in entry['checks']
                ]
            
            # Limit results
            if limit:
                history = history[-limit:]
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting health history: {str(e)}")
            return []
    
    def get_health_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get health check summary.
        
        Args:
            hours: Number of hours to summarize
            
        Returns:
            Health summary
        """
        try:
            since = timezone.now() - timedelta(hours=hours)
            
            # Get recent history
            recent_history = [
                entry for entry in self.check_history
                if timezone.parse(entry['checked_at']) >= since
            ]
            
            if not recent_history:
                return {
                    'period_hours': hours,
                    'total_checks': 0,
                    'healthy_checks': 0,
                    'unhealthy_checks': 0,
                    'degraded_checks': 0,
                    'uptime_percentage': 0
                }
            
            # Calculate summary
            total_checks = len(recent_history)
            healthy_checks = sum(1 for entry in recent_history if entry['overall_status'] == HealthStatus.HEALTHY)
            unhealthy_checks = sum(1 for entry in recent_history if entry['overall_status'] == HealthStatus.UNHEALTHY)
            degraded_checks = sum(1 for entry in recent_history if entry['overall_status'] == HealthStatus.DEGRADED)
            
            uptime_percentage = (healthy_checks / total_checks) * 100 if total_checks > 0 else 0
            
            return {
                'period_hours': hours,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': unhealthy_checks,
                'degraded_checks': degraded_checks,
                'uptime_percentage': uptime_percentage,
                'latest_check': recent_history[-1] if recent_history else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting health summary: {str(e)}")
            return {'error': str(e)}
    
    def register_health_check(self, check_name: str, health_check: HealthCheck) -> bool:
        """
        Register a custom health check.
        
        Args:
            check_name: Name of the health check
            health_check: Health check instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(health_check, HealthCheck):
                raise IntegrationError("Health check must inherit from HealthCheck")
            
            self.health_checks[check_name] = health_check
            self.logger.info(f"Health check {check_name} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering health check {check_name}: {str(e)}")
            return False
    
    def unregister_health_check(self, check_name: str) -> bool:
        """
        Unregister a health check.
        
        Args:
            check_name: Name of the health check to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if check_name in self.health_checks:
                del self.health_checks[check_name]
                self.logger.info(f"Health check {check_name} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Health check {check_name} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering health check {check_name}: {str(e)}")
            return False
    
    def get_health_check_status(self, check_name: str = None) -> Dict[str, Any]:
        """
        Get health check status.
        
        Args:
            check_name: Optional specific health check name
            
        Returns:
            Health check status information
        """
        try:
            if check_name:
                if check_name in self.health_checks:
                    return self.health_checks[check_name].get_status_info()
                else:
                    return {'error': f'Health check {check_name} not found'}
            else:
                return {
                    'total_checks': len(self.health_checks),
                    'checks': {
                        name: health_check.get_status_info()
                        for name, health_check in self.health_checks.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting health check status: {str(e)}")
            return {'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get health check system status.
        
        Returns:
            System status
        """
        try:
            return {
                'health_check_manager': {
                    'status': 'running' if self.enabled else 'disabled',
                    'total_checks': len(self.health_checks),
                    'default_interval': self.default_interval,
                    'max_history_size': self.max_history_size,
                    'alert_on_failure': self.alert_on_failure,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'health_checks': {
                    name: health_check.get_status_info()
                    for name, health_check in self.health_checks.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting health status: {str(e)}")
            return {'error': str(e)}


# Global health check manager instance
health_check_manager = HealthCheckManager()
