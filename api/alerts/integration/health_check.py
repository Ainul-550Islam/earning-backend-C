"""
Integration Health Check - Health monitoring for integration system
Provides safe health monitoring with existing alerts architecture
"""
import logging
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_adapter import integration_adapter
from api.alerts.integration.integ_registry import integration_registry
from api.alerts.integration.integ_constants import (
    HEALTH_CHECK_TIMEOUT,
    HEALTH_CHECK_INTERVAL,
    IntegrationStatus
)

logger = logging.getLogger(__name__)


class IntegrationHealthChecker:
    """
    Health checker for integration system
    Maintains existing health check logic and adds integration-specific health monitoring
    """
    
    def __init__(self):
        self.health_status = {
            'overall': 'healthy',
            'components': {},
            'last_check': None,
            'check_duration': 0
        }
        self.health_stats = {
            'total_checks': 0,
            'healthy_checks': 0,
            'unhealthy_checks': 0,
            'last_healthy_check': None,
            'last_unhealthy_check': None
        }
    
    def check_integration_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive integration health check
        """
        try:
            start_time = time.time()
            self.health_stats['total_checks'] += 1
            
            # Initialize component status
            components = {
                'integration_handler': self._check_integration_handler(),
                'integration_adapter': self._check_integration_adapter(),
                'integration_registry': self._check_integration_registry(),
                'database': self._check_database(),
                'cache': self._check_cache(),
                'memory': self._check_memory(),
                'external_services': self._check_external_services()
            }
            
            # Determine overall health
            overall_status = self._determine_overall_status(components)
            
            # Update health status
            self.health_status = {
                'overall': overall_status,
                'components': components,
                'last_check': django_tz.now().isoformat(),
                'check_duration': time.time() - start_time
            }
            
            # Update statistics
            if overall_status == 'healthy':
                self.health_stats['healthy_checks'] += 1
                self.health_stats['last_healthy_check'] = django_tz.now().isoformat()
            else:
                self.health_stats['unhealthy_checks'] += 1
                self.health_stats['last_unhealthy_check'] = django_tz.now().isoformat()
            
            return self.health_status
            
        except Exception as e:
            logger.error(f"Error in integration health check: {e}")
            self.health_stats['unhealthy_checks'] += 1
            
            return {
                'overall': 'unhealthy',
                'error': 'Operation failed',
                'last_check': django_tz.now().isoformat(),
                'check_duration': time.time() - start_time if 'start_time' in locals() else 0
            }
    
    def _check_integration_handler(self) -> Dict[str, Any]:
        """
        Check integration handler health
        """
        try:
            # Test basic functionality
            test_data = {
                'title': 'Health Check Test',
                'severity': 'low',
                'message': 'Integration health check test',
                'channel': 'webhook',
                'webhook_url': 'https://httpbin.org/status/200'
            }
            
            result = integration_handler.process_alert_data(test_data)
            
            if result.get('success', False):
                return {
                    'status': 'healthy',
                    'message': 'Integration handler functioning properly',
                    'test_result': result
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': f'Integration handler test failed: {result.get("error", "Unknown error")}',
                    'test_result': result
                }
                
        except Exception:
            logger.exception("Unhandled error in _check_integration_handler")
            return {
                'status': 'unhealthy',
                'message': 'Integration handler error',
                'error': 'Operation failed'
            }
    
    def _check_integration_adapter(self) -> Dict[str, Any]:
        """
        Check integration adapter health
        """
        try:
            # Test adapter availability
            available_adapters = integration_adapter.get_available_adapters()
            
            if not available_adapters:
                return {
                    'status': 'unhealthy',
                    'message': 'No integration adapters available'
                }
            
            # Test adapter transformation
            test_data = {
                'title': 'Health Check Test',
                'severity': 'low',
                'message': 'Adapter health check test'
            }
            
            result = integration_adapter.adapt_external_alert('webhook', test_data)
            
            if result.get('success', False):
                return {
                    'status': 'healthy',
                    'message': f'Integration adapter functioning properly with {len(available_adapters)} adapters',
                    'available_adapters': available_adapters,
                    'test_result': result
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': f'Integration adapter test failed: {result.get("error", "Unknown error")}',
                    'test_result': result
                }
                
        except Exception:
            logger.exception("Unhandled error in _check_integration_adapter")
            return {
                'status': 'unhealthy',
                'message': 'Integration adapter error',
                'error': 'Operation failed'
            }
    
    def _check_integration_registry(self) -> Dict[str, Any]:
        """
        Check integration registry health
        """
        try:
            # Test registry functionality
            stats = integration_registry.get_registry_stats()
            
            if 'error' in stats:
                return {
                    'status': 'unhealthy',
                    'message': f'Integration registry error: {stats["error"]}',
                    'error': stats['error']
                }
            
            # Check if registry has integrations
            total_integrations = stats.get('total_integrations', 0)
            active_integrations = stats.get('active_integrations', 0)
            
            return {
                'status': 'healthy',
                'message': f'Integration registry functioning properly with {total_integrations} total, {active_integrations} active integrations',
                'registry_stats': stats
            }
            
        except Exception:
            logger.exception("Unhandled error in _check_integration_registry")
            return {
                'status': 'unhealthy',
                'message': 'Integration registry error',
                'error': 'Operation failed'
            }
    
    def _check_database(self) -> Dict[str, Any]:
        """
        Check database connectivity and performance
        """
        try:
            start_time = time.time()
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result[0] != 1:
                    return {
                        'status': 'unhealthy',
                        'message': 'Database query returned unexpected result'
                    }
                
                # Test table existence - Django introspection instead of raw
                # information_schema SQL. DATABASE() is MySQL-only and doesn't
                # exist in PostgreSQL (production), which made this raise an
                # error on every call and report the DB unhealthy regardless of
                # actual DB state. table_names() is portable across backends.
                existing_tables = set(connection.introspection.table_names())
                table_count = len(
                    existing_tables & {'alerts_alertlog', 'alerts_alertrule'}
                )
                
                # Test query performance / server time - Django's own clock
                db_time = django_tz.now()
                
                query_time = time.time() - start_time
                
                if query_time > 1.0:  # More than 1 second is slow
                    status = 'degraded'
                    message = f'Database connection slow: {query_time:.3f}s'
                else:
                    status = 'healthy'
                    message = f'Database connection healthy: {query_time:.3f}s'
                
                return {
                    'status': status,
                    'message': message,
                    'tables_found': table_count,
                    'server_time': str(db_time),
                    'query_time': query_time
                }
                
        except Exception:
            logger.exception("Unhandled error in _check_database")
            return {
                'status': 'unhealthy',
                'message': 'Database connection failed',
                'error': 'Operation failed'
            }
    
    def _check_cache(self) -> Dict[str, Any]:
        """
        Check cache connectivity and performance
        """
        try:
            start_time = time.time()
            
            # Test cache set/get
            test_key = "integration_health_check_test"
            test_value = f"test_{int(time.time())}"
            
            cache.set(test_key, test_value, timeout=10)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            cache_time = time.time() - start_time
            
            if retrieved_value != test_value:
                return {
                    'status': 'unhealthy',
                    'message': 'Cache set/get operation failed'
                }
            
            if cache_time > 0.5:  # More than 500ms is slow
                status = 'degraded'
                message = f'Cache operation slow: {cache_time:.3f}s'
            else:
                status = 'healthy'
                message = f'Cache operation healthy: {cache_time:.3f}s'
            
            return {
                'status': status,
                'message': message,
                'operation_time': cache_time
            }
            
        except Exception:
            logger.exception("Unhandled error in _check_cache")
            return {
                'status': 'unhealthy',
                'message': 'Cache check failed',
                'error': 'Operation failed'
            }
    
    def _check_memory(self) -> Dict[str, Any]:
        """
        Check memory usage
        """
        try:
            import psutil
            
            # Get memory information
            memory = psutil.virtual_memory()
            
            memory_percent = memory.percent
            
            if memory_percent > 90:
                status = 'unhealthy'
                message = f'High memory usage: {memory_percent:.1f}%'
            elif memory_percent > 80:
                status = 'degraded'
                message = f'Elevated memory usage: {memory_percent:.1f}%'
            else:
                status = 'healthy'
                message = f'Memory usage normal: {memory_percent:.1f}%'
            
            return {
                'status': status,
                'message': message,
                'memory_percent': memory_percent,
                'memory_available': memory.available,
                'memory_used': memory.used
            }
            
        except ImportError:
            return {
                'status': 'unknown',
                'message': 'psutil not available for memory monitoring'
            }
        except Exception:
            logger.exception("Unhandled error in _check_memory")
            return {
                'status': 'unhealthy',
                'message': 'Memory check failed',
                'error': 'Operation failed'
            }
    
    def _check_external_services(self) -> Dict[str, Any]:
        """
        Check external service connectivity
        """
        try:
            import requests
            
            services = {}
            
            # Test HTTP service
            try:
                response = requests.get('https://httpbin.org/status/200', timeout=5)
                services['http_service'] = {
                    'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                    'response_time': response.elapsed.total_seconds(),
                    'status_code': response.status_code
                }
            except Exception as e:
                services['http_service'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
            
            # Test DNS resolution
            try:
                import socket
                socket.gethostbyname('google.com')
                services['dns'] = {
                    'status': 'healthy',
                    'message': 'DNS resolution working'
                }
            except Exception as e:
                services['dns'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
            
            # Determine overall external services status
            unhealthy_count = sum(1 for service in services.values() if service['status'] == 'unhealthy')
            
            if unhealthy_count == 0:
                overall_status = 'healthy'
                message = 'All external services healthy'
            elif unhealthy_count == len(services):
                overall_status = 'unhealthy'
                message = 'All external services unhealthy'
            else:
                overall_status = 'degraded'
                message = f'{unhealthy_count} of {len(services)} external services unhealthy'
            
            return {
                'status': overall_status,
                'message': message,
                'services': services
            }
            
        except Exception:
            logger.exception("Unhandled error in _check_external_services")
            return {
                'status': 'unhealthy',
                'message': 'External services check failed',
                'error': 'Operation failed'
            }
    
    def _determine_overall_status(self, components: Dict[str, Any]) -> str:
        """
        Determine overall health status from component status
        """
        status_counts = {
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0,
            'unknown': 0
        }
        
        for component in components.values():
            status = component.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Determine overall status
        if status_counts['unhealthy'] > 0:
            return 'unhealthy'
        elif status_counts['degraded'] > 0:
            return 'degraded'
        elif status_counts['healthy'] == len(components):
            return 'healthy'
        else:
            return 'unknown'
    
    def get_health_statistics(self) -> Dict[str, Any]:
        """
        Get health check statistics
        """
        try:
            total_checks = self.health_stats['total_checks']
            healthy_checks = self.health_stats['healthy_checks']
            
            health_rate = (healthy_checks / max(total_checks, 1)) * 100
            
            return {
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': self.health_stats['unhealthy_checks'],
                'health_rate': health_rate,
                'last_healthy_check': self.health_stats['last_healthy_check'],
                'last_unhealthy_check': self.health_stats['last_unhealthy_check'],
                'current_status': self.health_status.get('overall', 'unknown'),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting health statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }
    
    def check_component_health(self, component_name: str) -> Dict[str, Any]:
        """
        Check health of specific component
        """
        try:
            if component_name == 'integration_handler':
                return self._check_integration_handler()
            elif component_name == 'integration_adapter':
                return self._check_integration_adapter()
            elif component_name == 'integration_registry':
                return self._check_integration_registry()
            elif component_name == 'database':
                return self._check_database()
            elif component_name == 'cache':
                return self._check_cache()
            elif component_name == 'memory':
                return self._check_memory()
            elif component_name == 'external_services':
                return self._check_external_services()
            else:
                return {
                    'status': 'unknown',
                    'message': f'Unknown component: {component_name}'
                }
                
        except Exception as e:
            logger.error(f"Error checking component health: {e}")
            return {
                'status': 'unhealthy',
                'message': 'Component health check failed',
                'error': 'Operation failed'
            }


# Global health checker instance
integration_health_checker = IntegrationHealthChecker()


# Django view functions for health endpoints
@require_http_methods(["GET"])
def integration_health_check(request):
    """
    Django view for integration health check
    """
    health_status = integration_health_checker.check_integration_health()
    
    # Set appropriate HTTP status code
    status_code = 200
    if health_status.get('overall') == 'unhealthy':
        status_code = 503
    elif health_status.get('overall') == 'degraded':
        status_code = 200  # Still serve but indicate degraded state
    
    return JsonResponse(health_status, status=status_code)


_KNOWN_INTEGRATION_COMPONENTS = [
    'integration_handler', 'integration_adapter', 'integration_registry',
    'database', 'cache', 'memory', 'external_services',
]


def integration_component_health(component_name: str = None) -> Dict[str, Any]:
    """
    Get health status for a single named component, or for every known
    component when no name is given. Used directly (not as a Django view -
    it isn't wired into urls.py) by IntegrationHealthViewSet.components().
    """
    if component_name:
        return integration_health_checker.check_component_health(component_name)
    return {
        name: integration_health_checker.check_component_health(name)
        for name in _KNOWN_INTEGRATION_COMPONENTS
    }


@require_http_methods(["GET"])
def integration_health_stats(request):
    """
    Django view for health statistics
    """
    stats = integration_health_checker.get_health_statistics()
    return JsonResponse(stats)


# Utility functions
def check_integration_health() -> Dict[str, Any]:
    """
    Check integration system health
    """
    return integration_health_checker.check_integration_health()


def get_health_statistics() -> Dict[str, Any]:
    """
    Get health check statistics
    """
    return integration_health_checker.get_health_statistics()


# URL patterns for health endpoints
"""
Add to urls.py:

from api.alerts.integration.health_check import (
    integration_health_check,
    integration_health_stats
)

urlpatterns = [
    path('api/integration/health/', integration_health_check, name='integration_health_check'),
    path('api/integration/health/stats/', integration_health_stats, name='integration_health_stats'),
]

integration_component_health(component_name=None) is a plain utility function
(not a view) - call it directly, e.g. from IntegrationHealthViewSet.components().
"""
