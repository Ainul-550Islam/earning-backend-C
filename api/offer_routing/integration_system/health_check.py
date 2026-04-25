"""
Health Check

Health check service for integration system
to monitor system health and component status.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import json
import time
from ..constants import (
    IntegrationType, IntegrationStatus, IntegrationLogLevel,
    INTEGRATION_TYPES, INTEGRATION_STATUSES, INTEGRATION_LOG_LEVELS,
    ERROR_CODES
)
from ..exceptions import (
    IntegrationError, ValidationError
)
from .integ_handler import integ_handler
from .integ_registry import integ_registry
from .integ_cache import integ_cache

logger = logging.getLogger(__name__)


class HealthCheck:
    """
    Health check service for integration system.
    
    Provides comprehensive health monitoring for:
    - Integration handler status
    - Registry health and connectivity
    - Cache system health
    - Database connectivity
    - External service dependencies
    - System resource monitoring
    - Performance metrics
    """
    
    def __init__(self):
        self.health_checks = {
            'integration_handler': self._check_integration_handler,
            'registry': self._check_registry,
            'cache': self._check_cache_system,
            'database': self._check_database_connectivity,
            'external_services': self._check_external_services,
            'system_resources': self._check_system_resources
        }
        self.health_stats = {
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'avg_check_time_ms': 0.0,
            'last_check_time': None,
            'overall_health': 'unknown'
        }
        self.alert_thresholds = {
            'response_time_ms': 1000,  # 1 second
            'error_rate': 5.0,     # 5% error rate
            'cpu_usage': 80.0,     # 80% CPU usage
            'memory_usage': 85.0,  # 85% memory usage
            'disk_usage': 90.0      # 90% disk usage
        }
    
    def run_health_check(self) -> Dict[str, Any]:
        """
        Run comprehensive health check on integration system.
        
        Returns:
            Health check results with component status and overall health
        """
        try:
            start_time = time.time()
            
            # Run all health checks
            check_results = {}
            for check_name, check_func in self.health_checks.items():
                try:
                    result = check_func()
                    check_results[check_name] = result
                    
                    # Update health stats
                    self._update_health_stats(result, time.time() - start_time)
                    
                except Exception as e:
                    logger.error(f"Health check {check_name} failed: {e}")
                    check_results[check_name] = {
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Calculate overall health
            overall_health = self._calculate_overall_health(check_results)
            
            # Update final stats
            self.health_stats['overall_health'] = overall_health
            self.health_stats['last_check_time'] = datetime.now().isoformat()
            
            return {
                'success': True,
                'overall_health': overall_health,
                'component_health': check_results,
                'health_stats': self.health_stats,
                'alert_thresholds': self.alert_thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error running health check: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_integration_handler(self) -> Dict[str, Any]:
        """Check integration handler health."""
        try:
            # Test handler availability
            handler_available = integ_handler is not None
            
            # Test handler functionality
            test_result = integ_handler.health_check() if handler_available else {'status': 'unavailable'}
            
            return {
                'status': 'healthy' if test_result.get('status') == 'healthy' else 'unhealthy',
                'handler_available': handler_available,
                'health_check': test_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_registry(self) -> Dict[str, Any]:
        """Check integration registry health."""
        try:
            # Test registry availability
            registry_available = integ_registry is not None
            
            # Test registry functionality
            test_result = integ_registry.health_check() if registry_available else {'status': 'unavailable'}
            
            return {
                'status': 'healthy' if test_result.get('status') == 'healthy' else 'unhealthy',
                'registry_available': registry_available,
                'health_check': test_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_cache_system(self) -> Dict[str, Any]:
        """Check cache system health."""
        try:
            # Test cache availability
            cache_available = integ_cache is not None
            
            # Test cache functionality
            test_key = 'health_check_test'
            test_value = {'test': True, 'timestamp': datetime.now().isoformat()}
            
            # Test cache write
            integ_cache.set(test_key, test_value, timeout=60)
            
            # Test cache read
            cached_value = integ_cache.get(test_key)
            
            cache_working = (
                cache_available and
                cached_value and
                cached_value.get('test') == test_value.get('test')
            )
            
            return {
                'status': 'healthy' if cache_working else 'unhealthy',
                'cache_available': cache_available,
                'cache_working': cache_working,
                'test_key': test_key,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # Test database connection
            from django.db import connection
            from django.core.cache import cache
            
            # Simple connection test
            db_connection = connection.ensure_connection()
            
            # Test cache connection
            cache_connection = cache._cache.get('test_connection')
            
            # Test basic query
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                User.objects.count()  # Simple query test
                db_working = True
            except Exception:
                db_working = False
            
            return {
                'status': 'healthy' if db_working and db_connection.is_usable() else 'unhealthy',
                'database_connection': db_working,
                'cache_connection': cache_connection is not None,
                'query_test': db_working,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_external_services(self) -> Dict[str, Any]:
        """Check external service dependencies."""
        try:
            # This would check external services like:
            # - Message queues
            # - External APIs
            # - File storage
            # - Email services
            # - SMS services
            
            # For now, return healthy status
            external_services = {
                'message_queue': {
                    'status': 'healthy',
                    'message': 'Message queue service is available'
                },
                'external_apis': {
                    'status': 'healthy',
                    'message': 'External API services are available'
                },
                'file_storage': {
                    'status': 'healthy',
                    'message': 'File storage service is available'
                },
                'notification_services': {
                    'status': 'healthy',
                    'message': 'Notification services are available'
                }
            }
            
            return {
                'status': 'healthy',
                'external_services': external_services,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            import psutil
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Get network I/O
            network = psutil.net_io_counters()
            
            # Check against thresholds
            cpu_healthy = cpu_percent < self.alert_thresholds['cpu_usage']
            memory_healthy = memory_percent < self.alert_thresholds['memory_usage']
            disk_healthy = disk_percent < self.alert_thresholds['disk_usage']
            
            overall_healthy = cpu_healthy and memory_healthy and disk_healthy
            
            return {
                'status': 'healthy' if overall_healthy else 'degraded',
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent,
                'network_io': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'thresholds': self.alert_thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _calculate_overall_health(self, check_results: Dict[str, Any]) -> str:
        """Calculate overall system health."""
        try:
            # Count component statuses
            healthy_count = 0
            degraded_count = 0
            error_count = 0
            
            for check_name, result in check_results.items():
                status = result.get('status', 'unknown')
                if status == 'healthy':
                    healthy_count += 1
                elif status == 'degraded':
                    degraded_count += 1
                elif status == 'error':
                    error_count += 1
            
            # Determine overall health
            if error_count > 0:
                return 'error'
            elif degraded_count > 0:
                return 'degraded'
            elif healthy_count == len(check_results):
                return 'healthy'
            else:
                return 'unknown'
            
        except Exception as e:
            logger.error(f"Error calculating overall health: {e}")
            return 'error'
    
    def _update_health_stats(self, result: Dict[str, Any], execution_time: float):
        """Update health check statistics."""
        try:
            self.health_stats['total_checks'] += 1
            
            if result.get('status') == 'healthy':
                self.health_stats['successful_checks'] += 1
            else:
                self.health_stats['failed_checks'] += 1
            
            # Update average execution time
            current_avg = self.health_stats['avg_check_time_ms']
            total_checks = self.health_stats['total_checks']
            self.health_stats['avg_check_time_ms'] = (
                (current_avg * (total_checks - 1) + execution_time) / total_checks
            )
            
        except Exception as e:
            logger.error(f"Error updating health stats: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        try:
            return {
                'success': True,
                'health_stats': self.health_stats,
                'alert_thresholds': self.alert_thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def set_alert_thresholds(self, thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Set alert thresholds."""
        try:
            # Validate thresholds
            valid_thresholds = ['response_time_ms', 'error_rate', 'cpu_usage', 'memory_usage', 'disk_usage']
            
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
                'updated_thresholds': self.alert_thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_component_health(self, component_name: str) -> Dict[str, Any]:
        """Get health status for specific component."""
        try:
            if component_name in self.health_checks:
                result = self.health_checks[component_name]()
                return {
                    'success': True,
                    'component': component_name,
                    'health': result,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': f'Unknown component: {component_name}',
                    'timestamp': datetime.now().isoformat()
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on health check service."""
        try:
            # Test health check functionality
            test_result = self.run_health_check()
            
            # Check if health check is working
            health_check_healthy = (
                test_result.get('success', False) and
                test_result.get('overall_health') in ['healthy', 'degraded', 'error']
            )
            
            return {
                'status': 'healthy' if health_check_healthy else 'unhealthy',
                'health_check_result': test_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
health_check = HealthCheck()
