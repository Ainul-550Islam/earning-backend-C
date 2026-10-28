# api/rate_limit/health_check.py
"""
Health check system for rate limit module.

Provides comprehensive health monitoring and status reporting.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.contrib.auth import get_user_model
import psutil
import time

from api.rate_limit.integ_handler import integration_handler
from api.rate_limit.circuit_breaker import circuit_breaker_manager
from api.rate_limit.performance_monitor import performance_monitor
from api.rate_limit.message_queue import message_queue_manager
from api.rate_limit.data_bridge import data_bridge_manager

logger = logging.getLogger(__name__)
User = get_user_model()


class HealthStatus:
    """Health status constants."""
    
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'
    
    CHOICES = [
        (HEALTHY, 'Healthy'),
        (DEGRADED, 'Degraded'),
        (UNHEALTHY, 'Unhealthy'),
        (UNKNOWN, 'Unknown'),
    ]


class HealthCheck:
    """Represents a health check."""
    
    def __init__(self, name: str, check_function: Callable, timeout: float = 30.0,
                 critical: bool = False, description: str = ''):
        self.name = name
        self.check_function = check_function
        self.timeout = timeout
        self.critical = critical
        self.description = description
        self.last_check = None
        self.last_status = HealthStatus.UNKNOWN
        self.last_error = None
        self.check_count = 0
        self.failure_count = 0
    
    def execute(self) -> Dict[str, Any]:
        """Execute the health check."""
        try:
            start_time = time.time()
            self.check_count += 1
            
            # Execute with timeout
            result = self.check_function()
            
            execution_time = time.time() - start_time
            self.last_check = timezone.now()
            
            if result.get('healthy', False):
                self.last_status = HealthStatus.HEALTHY
                self.last_error = None
            else:
                self.last_status = HealthStatus.UNHEALTHY
                self.last_error = result.get('error', 'Unknown error')
                self.failure_count += 1
            
            return {
                'name': self.name,
                'status': self.last_status,
                'healthy': result.get('healthy', False),
                'execution_time': execution_time,
                'description': self.description,
                'details': result.get('details', {}),
                'error': self.last_error,
                'checked_at': self.last_check.isoformat(),
                'critical': self.critical
            }
            
        except Exception as e:
            self.last_check = timezone.now()
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = str(e)
            self.failure_count += 1
            
            return {
                'name': self.name,
                'status': self.last_status,
                'healthy': False,
                'execution_time': self.timeout,
                'description': self.description,
                'error': self.last_error,
                'checked_at': self.last_check.isoformat(),
                'critical': self.critical
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get check statistics."""
        success_rate = ((self.check_count - self.failure_count) / max(self.check_count, 1)) * 100
        
        return {
            'name': self.name,
            'check_count': self.check_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'last_status': self.last_status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'critical': self.critical
        }


class HealthChecker:
    """
    Main health checker for the rate limit module.
    """
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.check_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        self._initialize_default_checks()
    
    def _initialize_default_checks(self):
        """Initialize default health checks."""
        
        # Database health check
        self.add_check(HealthCheck(
            name='database',
            check_function=self._check_database,
            critical=True,
            description='Database connectivity and performance'
        ))
        
        # Cache health check
        self.add_check(HealthCheck(
            name='cache',
            check_function=self._check_cache,
            critical=True,
            description='Cache connectivity and performance'
        ))
        
        # Rate limit service health check
        self.add_check(HealthCheck(
            name='rate_limit_service',
            check_function=self._check_rate_limit_service,
            critical=True,
            description='Rate limiting service functionality'
        ))
        
        # Integration health check
        self.add_check(HealthCheck(
            name='integrations',
            check_function=self._check_integrations,
            critical=False,
            description='External integration connectivity'
        ))
        
        # Circuit breaker health check
        self.add_check(HealthCheck(
            name='circuit_breakers',
            check_function=self._check_circuit_breakers,
            critical=False,
            description='Circuit breaker status'
        ))
        
        # Message queue health check
        self.add_check(HealthCheck(
            name='message_queue',
            check_function=self._check_message_queue,
            critical=False,
            description='Message queue functionality'
        ))
        
        # System resources health check
        self.add_check(HealthCheck(
            name='system_resources',
            check_function=self._check_system_resources,
            critical=False,
            description='System resource usage'
        ))
        
        # Performance health check
        self.add_check(HealthCheck(
            name='performance',
            check_function=self._check_performance,
            critical=False,
            description='Performance metrics'
        ))
    
    def add_check(self, check: HealthCheck):
        """Add a health check."""
        self.checks[check.name] = check
        logger.info(f"Added health check: {check.name}")
    
    def remove_check(self, name: str):
        """Remove a health check."""
        if name in self.checks:
            del self.checks[name]
            logger.info(f"Removed health check: {name}")
    
    def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check."""
        check = self.checks.get(name)
        if not check:
            return {
                'name': name,
                'status': HealthStatus.UNKNOWN,
                'healthy': False,
                'error': f'Health check not found: {name}',
                'checked_at': timezone.now().isoformat()
            }
        
        result = check.execute()
        self._add_to_history(result)
        
        return result
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        critical_failures = 0
        
        for name, check in self.checks.items():
            try:
                result = check.execute()
                results[name] = result
                self._add_to_history(result)
                
                # Update overall status
                if result['status'] == HealthStatus.UNHEALTHY:
                    if check.critical:
                        critical_failures += 1
                        overall_status = HealthStatus.UNHEALTHY
                    elif overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                elif result['status'] == HealthStatus.DEGRADED:
                    if overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                        
            except Exception as e:
                logger.error(f"Health check {name} failed: {str(e)}")
                results[name] = {
                    'name': name,
                    'status': HealthStatus.UNHEALTHY,
                    'healthy': False,
                    'error': str(e),
                    'checked_at': timezone.now().isoformat(),
                    'critical': check.critical
                }
                
                if check.critical:
                    critical_failures += 1
                    overall_status = HealthStatus.UNHEALTHY
                elif overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        return {
            'overall_status': overall_status,
            'critical_failures': critical_failures,
            'total_checks': len(self.checks),
            'healthy_checks': len([r for r in results.values() if r['healthy']]),
            'checked_at': timezone.now().isoformat(),
            'checks': results
        }
    
    def _add_to_history(self, result: Dict[str, Any]):
        """Add result to history."""
        self.check_history.append(result)
        
        # Maintain history size
        if len(self.check_history) > self.max_history_size:
            self.check_history = self.check_history[-self.max_history_size:]
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            start_time = time.time()
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            connection_time = time.time() - start_time
            
            # Check connection pool
            from django.db import connections
            connection_info = {
                'max_connections': getattr(settings, 'DATABASES', {}).get('default', {}).get('CONN_MAX_AGE', 0),
                'connection_time': connection_time
            }
            
            # Check slow queries (simplified)
            slow_query_threshold = 1.0  # 1 second
            slow_queries = connection_time > slow_query_threshold
            
            return {
                'healthy': True,
                'details': {
                    'connection_time': connection_time,
                    'slow_queries': slow_queries,
                    'connection_info': connection_info
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check cache health."""
        try:
            start_time = time.time()
            
            # Test cache set/get
            test_key = 'health_check_test'
            test_value = f'test_value_{timezone.now().timestamp()}'
            
            cache.set(test_key, test_value, timeout=60)
            retrieved_value = cache.get(test_key)
            
            cache_time = time.time() - start_time
            
            # Clean up
            cache.delete(test_key)
            
            if retrieved_value != test_value:
                return {
                    'healthy': False,
                    'error': 'Cache value mismatch'
                }
            
            # Check cache performance
            slow_cache_threshold = 0.1  # 100ms
            slow_cache = cache_time > slow_cache_threshold
            
            return {
                'healthy': True,
                'details': {
                    'cache_time': cache_time,
                    'slow_cache': slow_cache,
                    'backend': getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'unknown')
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_rate_limit_service(self) -> Dict[str, Any]:
        """Check rate limit service health."""
        try:
            from api.rate_limit.services import RateLimitService
            
            service = RateLimitService()
            
            # Test basic functionality
            test_identifier = 'health_check_test'
            is_limited, remaining, metadata = service.is_rate_limited(
                identifier=test_identifier,
                limit_type='test',
                max_requests=100
            )
            
            if is_limited is None:
                return {
                    'healthy': False,
                    'error': 'Rate limit service returned None'
                }
            
            # Check system health
            health_status = service.get_system_health()
            
            return {
                'healthy': True,
                'details': {
                    'test_result': not is_limited,
                    'remaining': remaining,
                    'system_health': health_status
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_integrations(self) -> Dict[str, Any]:
        """Check integration health."""
        try:
            integration_health = integration_handler.health_check()
            
            if not integration_health.get('success', False):
                return {
                    'healthy': False,
                    'error': integration_health.get('error', 'Integration health check failed')
                }
            
            results = integration_health.get('results', {})
            healthy_count = len([r for r in results.values() if r.get('healthy', False)])
            total_count = len(results)
            
            return {
                'healthy': healthy_count == total_count,
                'details': {
                    'total_integrations': total_count,
                    'healthy_integrations': healthy_count,
                    'results': results
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_circuit_breakers(self) -> Dict[str, Any]:
        """Check circuit breaker health."""
        try:
            circuit_health = circuit_breaker_manager.health_check()
            
            if circuit_health['health_score'] < 60:
                return {
                    'healthy': False,
                    'error': f'Low health score: {circuit_health["health_score"]}%'
                }
            
            return {
                'healthy': True,
                'details': circuit_health
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_message_queue(self) -> Dict[str, Any]:
        """Check message queue health."""
        try:
            queue_status = message_queue_manager.get_queue_status()
            
            if not queue_status['is_running']:
                return {
                    'healthy': False,
                    'error': 'Message queue worker is not running'
                }
            
            # Check queue size
            max_queue_size = queue_status['max_queue_size']
            current_size = queue_status['queue_size']
            
            if current_size > max_queue_size * 0.8:  # 80% threshold
                return {
                    'healthy': False,
                    'error': f'Queue size too high: {current_size}/{max_queue_size}'
                }
            
            return {
                'healthy': True,
                'details': queue_status
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource health."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Determine health
            thresholds = {
                'cpu': 80,
                'memory': 85,
                'disk': 90
            }
            
            issues = []
            if cpu_percent > thresholds['cpu']:
                issues.append(f'High CPU usage: {cpu_percent}%')
            
            if memory_percent > thresholds['memory']:
                issues.append(f'High memory usage: {memory_percent}%')
            
            if disk_percent > thresholds['disk']:
                issues.append(f'High disk usage: {disk_percent}%')
            
            return {
                'healthy': len(issues) == 0,
                'details': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent,
                    'issues': issues
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def _check_performance(self) -> Dict[str, Any]:
        """Check performance metrics."""
        try:
            monitor_status = performance_monitor.get_status()
            
            if not monitor_status['is_monitoring']:
                return {
                    'healthy': False,
                    'error': 'Performance monitoring is not active'
                }
            
            # Get recent metrics
            dashboard_data = performance_monitor.get_dashboard_data()
            recent_alerts = dashboard_data.get('recent_alerts', [])
            
            # Check for critical alerts
            critical_alerts = [a for a in recent_alerts if a.get('severity') == 'critical']
            
            if len(critical_alerts) > 5:  # Too many critical alerts
                return {
                    'healthy': False,
                    'error': f'Too many critical alerts: {len(critical_alerts)}'
                }
            
            return {
                'healthy': True,
                'details': {
                    'monitoring_status': monitor_status,
                    'recent_alerts_count': len(recent_alerts),
                    'critical_alerts_count': len(critical_alerts)
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def get_check_history(self, check_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health check history."""
        history = self.check_history
        
        if check_name:
            history = [h for h in history if h.get('name') == check_name]
        
        # Sort by timestamp (most recent first)
        history.sort(key=lambda h: h.get('checked_at', ''), reverse=True)
        
        return history[:limit]
    
    def get_check_statistics(self) -> Dict[str, Any]:
        """Get health check statistics."""
        stats = {}
        
        for name, check in self.checks.items():
            stats[name] = check.get_statistics()
        
        return stats
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        try:
            # Get latest check results
            latest_results = {}
            for name in self.checks:
                history = self.get_check_history(name, limit=1)
                if history:
                    latest_results[name] = history[0]
            
            # Calculate summary
            total_checks = len(latest_results)
            healthy_checks = len([r for r in latest_results.values() if r.get('healthy', False)])
            critical_failures = len([
                r for r in latest_results.values() 
                if not r.get('healthy', False) and r.get('critical', False)
            ])
            
            # Determine overall status
            if critical_failures > 0:
                overall_status = HealthStatus.UNHEALTHY
            elif healthy_checks == total_checks:
                overall_status = HealthStatus.HEALTHY
            else:
                overall_status = HealthStatus.DEGRADED
            
            return {
                'overall_status': overall_status,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'failed_checks': total_checks - healthy_checks,
                'critical_failures': critical_failures,
                'health_score': (healthy_checks / max(total_checks, 1)) * 100,
                'last_updated': timezone.now().isoformat(),
                'latest_results': latest_results
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {str(e)}")
            return {
                'overall_status': HealthStatus.UNKNOWN,
                'error': str(e)
            }


# Global health checker instance
health_checker = HealthChecker()


# Health check endpoint data
def get_health_check_response(detailed: bool = False) -> Dict[str, Any]:
    """
    Get health check response for API endpoints.
    
    Args:
        detailed: Whether to include detailed results
        
    Returns:
        Health check response
    """
    try:
        if detailed:
            results = health_checker.run_all_checks()
        else:
            summary = health_checker.get_health_summary()
            results = {
                'status': summary['overall_status'],
                'healthy': summary['overall_status'] == HealthStatus.HEALTHY,
                'health_score': summary['health_score'],
                'checked_at': summary['last_updated']
            }
        
        return results
        
    except Exception as e:
        logger.error(f"Health check endpoint failed: {str(e)}")
        return {
            'status': HealthStatus.UNHEALTHY,
            'healthy': False,
            'error': str(e),
            'checked_at': timezone.now().isoformat()
        }


# Export classes and functions
__all__ = [
    'HealthStatus',
    'HealthCheck',
    'HealthChecker',
    'health_checker',
    'get_health_check_response'
]
