"""
health_check.py – Health check system for postback module.

Provides comprehensive health check functionality including:
- Component health monitoring
- Health status aggregation
- Health check scheduling
- Health alerting
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import time
from abc import ABC, abstractmethod

from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from django.conf import settings

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check type enumeration."""
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL_SERVICE = "internal_service"
    SYSTEM_RESOURCE = "system_resource"
    CUSTOM = "custom"


@dataclass
class HealthCheckResult:
    """Health check result data structure."""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    response_time: float = 0.0
    timestamp: datetime = field(default_factory=timezone.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'component': self.component,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'response_time': self.response_time,
            'timestamp': self.timestamp.isoformat(),
            'error': self.error,
            'metadata': self.metadata,
        }
    
    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]


@dataclass
class HealthThreshold:
    """Health check threshold configuration."""
    component: str
    warning_threshold: float
    error_threshold: float
    critical_threshold: float
    metric_name: str
    comparison: str = "greater_than"  # greater_than, less_than
    enabled: bool = True
    
    def check_threshold(self, value: float) -> HealthStatus:
        """Check if value breaches threshold."""
        if not self.enabled:
            return HealthStatus.HEALTHY
        
        if self.comparison == "greater_than":
            if value >= self.critical_threshold:
                return HealthStatus.CRITICAL
            elif value >= self.error_threshold:
                return HealthStatus.UNHEALTHY
            elif value >= self.warning_threshold:
                return HealthStatus.DEGRADED
        elif self.comparison == "less_than":
            if value <= self.critical_threshold:
                return HealthStatus.CRITICAL
            elif value <= self.error_threshold:
                return HealthStatus.UNHEALTHY
            elif value <= self.warning_threshold:
                return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY


class HealthChecker(ABC):
    """
    Abstract base class for health checkers.
    
    Provides common interface for different
    health check implementations.
    """
    
    def __init__(self, name: str, check_type: CheckType):
        self.name = name
        self.check_type = check_type
        self.logger = logging.getLogger(f"health.{name}")
        self.enabled = True
        self.timeout = 30.0
        self.last_check: Optional[HealthCheckResult] = None
    
    @abstractmethod
    def check(self) -> HealthCheckResult:
        """
        Perform health check.
        
        Returns:
            Health check result
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if health checker is enabled."""
        return self.enabled
    
    def enable(self):
        """Enable health checker."""
        self.enabled = True
        self.logger.info(f"Health checker enabled: {self.name}")
    
    def disable(self):
        """Disable health checker."""
        self.enabled = False
        self.logger.info(f"Health checker disabled: {self.name}")


class DatabaseHealthChecker(HealthChecker):
    """Database health checker."""
    
    def __init__(self, name: str = "database"):
        super().__init__(name, CheckType.DATABASE)
    
    def check(self) -> HealthCheckResult:
        """Check database health."""
        start_time = time.time()
        
        try:
            with connection.cursor() as cursor:
                # Test basic connectivity
                cursor.execute("SELECT 1")
                
                # Check connection count
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
                
                # Check database size (PostgreSQL specific)
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """)
                db_size = cursor.fetchone()[0]
                
                details = {
                    'active_connections': active_connections,
                    'database_size': db_size,
                    'connection_test': 'passed',
                }
                
                # Determine status based on connection count
                max_connections = getattr(settings, 'DATABASES', {}).get('default', {}).get('OPTIONS', {}).get('MAXCONN', 100)
                
                if active_connections >= max_connections * 0.9:
                    status = HealthStatus.CRITICAL
                    message = f"Database connections near limit: {active_connections}/{max_connections}"
                elif active_connections >= max_connections * 0.8:
                    status = HealthStatus.UNHEALTHY
                    message = f"High database connections: {active_connections}/{max_connections}"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Database is healthy"
                
                response_time = time.time() - start_time
                
                result = HealthCheckResult(
                    component=self.name,
                    status=status,
                    message=message,
                    details=details,
                    response_time=response_time
                )
                
                self.last_check = result
                return result
        
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message="Database connection failed",
                error=str(e),
                response_time=response_time
            )
            
            self.last_check = result
            return result


class CacheHealthChecker(HealthChecker):
    """Cache health checker."""
    
    def __init__(self, name: str = "cache"):
        super().__init__(name, CheckType.CACHE)
    
    def check(self) -> HealthCheckResult:
        """Check cache health."""
        start_time = time.time()
        
        try:
            # Test cache connectivity
            test_key = f"health_check_{int(time.time())}"
            test_value = "test_value"
            
            # Write test
            cache.set(test_key, test_value, timeout=10)
            
            # Read test
            cached_value = cache.get(test_key)
            
            # Clean up
            cache.delete(test_key)
            
            # Get cache info
            cache_info = {}
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'info'):
                cache_info = cache._cache.info()
            
            details = {
                'read_test': cached_value == test_value,
                'write_test': True,
                'cache_info': cache_info,
            }
            
            if cached_value == test_value:
                status = HealthStatus.HEALTHY
                message = "Cache is healthy"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Cache read/write test failed"
            
            response_time = time.time() - start_time
            
            result = HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details=details,
                response_time=response_time
            )
            
            self.last_check = result
            return result
        
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message="Cache health check failed",
                error=str(e),
                response_time=response_time
            )
            
            self.last_check = result
            return result


class ExternalServiceHealthChecker(HealthChecker):
    """External service health checker."""
    
    def __init__(self, name: str, url: str, timeout: float = 10.0):
        super().__init__(name, CheckType.EXTERNAL_SERVICE)
        self.url = url
        self.timeout = timeout
    
    def check(self) -> HealthCheckResult:
        """Check external service health."""
        start_time = time.time()
        
        try:
            import requests
            
            response = requests.get(
                self.url,
                timeout=self.timeout,
                headers={'User-Agent': 'HealthCheck/1.0'}
            )
            
            response_time = time.time() - start_time
            
            details = {
                'url': self.url,
                'status_code': response.status_code,
                'response_time': response_time,
                'headers': dict(response.headers),
            }
            
            if response.status_code == 200:
                status = HealthStatus.HEALTHY
                message = f"External service is healthy (HTTP {response.status_code})"
            elif response.status_code < 500:
                status = HealthStatus.DEGRADED
                message = f"External service degraded (HTTP {response.status_code})"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"External service unhealthy (HTTP {response.status_code})"
            
            result = HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details=details,
                response_time=response_time
            )
            
            self.last_check = result
            return result
        
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message="External service check failed",
                error=str(e),
                response_time=response_time
            )
            
            self.last_check = result
            return result


class SystemResourceHealthChecker(HealthChecker):
    """System resource health checker."""
    
    def __init__(self, name: str = "system_resources"):
        super().__init__(name, CheckType.SYSTEM_RESOURCE)
    
    def check(self) -> HealthCheckResult:
        """Check system resource health."""
        start_time = time.time()
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            details = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_free_gb': disk.free / (1024**3),
            }
            
            # Determine overall status
            critical_thresholds = [cpu_percent, memory_percent, disk_percent]
            if any(metric >= 95 for metric in critical_thresholds):
                status = HealthStatus.CRITICAL
                message = "Critical resource usage detected"
            elif any(metric >= 85 for metric in critical_thresholds):
                status = HealthStatus.UNHEALTHY
                message = "High resource usage detected"
            elif any(metric >= 70 for metric in critical_thresholds):
                status = HealthStatus.DEGRADED
                message = "Elevated resource usage detected"
            else:
                status = HealthStatus.HEALTHY
                message = "System resources are healthy"
            
            response_time = time.time() - start_time
            
            result = HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details=details,
                response_time=response_time
            )
            
            self.last_check = result
            return result
        
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message="System resource check failed",
                error=str(e),
                response_time=response_time
            )
            
            self.last_check = result
            return result


class CustomHealthChecker(HealthChecker):
    """Custom health checker with user-defined function."""
    
    def __init__(self, name: str, check_function: Callable, **kwargs):
        super().__init__(name, CheckType.CUSTOM)
        self.check_function = check_function
        self.timeout = kwargs.get('timeout', 30.0)
    
    def check(self) -> HealthCheckResult:
        """Perform custom health check."""
        start_time = time.time()
        
        try:
            # Execute custom check function
            result_data = self.check_function()
            
            # Validate result format
            if not isinstance(result_data, dict):
                raise ValueError("Custom check function must return a dictionary")
            
            status = HealthStatus(result_data.get('status', 'unknown'))
            message = result_data.get('message', 'Custom health check completed')
            details = result_data.get('details', {})
            error = result_data.get('error')
            
            response_time = time.time() - start_time
            
            result = HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details=details,
                response_time=response_time,
                error=error
            )
            
            self.last_check = result
            return result
        
        except Exception as e:
            response_time = time.time() - start_time
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message="Custom health check failed",
                error=str(e),
                response_time=response_time
            )
            
            self.last_check = result
            return result


class HealthCheckManager:
    """
    Manager for health checks.
    
    Orchestrates health check execution,
    aggregation, and reporting.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.checkers: Dict[str, HealthChecker] = {}
        self.thresholds: Dict[str, HealthThreshold] = {}
        self.check_history: List[Dict[str, Any]] = []
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 60  # seconds
        self._setup_default_checkers()
        self._setup_default_thresholds()
    
    def _setup_default_checkers(self):
        """Setup default health checkers."""
        default_checkers = [
            DatabaseHealthChecker(),
            CacheHealthChecker(),
            SystemResourceHealthChecker(),
        ]
        
        for checker in default_checkers:
            self.register_checker(checker)
    
    def _setup_default_thresholds(self):
        """Setup default health thresholds."""
        default_thresholds = [
            HealthThreshold(
                component="database",
                warning_threshold=0.8,
                error_threshold=0.9,
                critical_threshold=0.95,
                metric_name="connection_usage",
                comparison="greater_than"
            ),
            HealthThreshold(
                component="system_resources",
                warning_threshold=70.0,
                error_threshold=85.0,
                critical_threshold=95.0,
                metric_name="resource_usage",
                comparison="greater_than"
            ),
        ]
        
        for threshold in default_thresholds:
            self.thresholds[threshold.component] = threshold
    
    def register_checker(self, checker: HealthChecker):
        """Register health checker."""
        self.checkers[checker.name] = checker
        self.logger.info(f"Health checker registered: {checker.name}")
    
    def unregister_checker(self, name: str):
        """Unregister health checker."""
        if name in self.checkers:
            del self.checkers[name]
            self.logger.info(f"Health checker unregistered: {name}")
    
    def add_custom_checker(self, name: str, check_function: Callable, **kwargs):
        """Add custom health checker."""
        checker = CustomHealthChecker(name, check_function, **kwargs)
        self.register_checker(checker)
    
    def add_threshold(self, threshold: HealthThreshold):
        """Add health threshold."""
        self.thresholds[threshold.component] = threshold
        self.logger.info(f"Health threshold added: {threshold.component}")
    
    def check_all(self) -> Dict[str, Any]:
        """Perform all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for name, checker in self.checkers.items():
            if not checker.is_enabled():
                continue
            
            try:
                result = checker.check()
                results[name] = result.to_dict()
                
                # Update overall status
                if result.status == HealthStatus.CRITICAL:
                    overall_status = HealthStatus.CRITICAL
                elif result.status == HealthStatus.UNHEALTHY and overall_status != HealthStatus.CRITICAL:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                
                # Apply thresholds if configured
                if name in self.thresholds:
                    threshold = self.thresholds[name]
                    metric_value = result.details.get(threshold.metric_name)
                    if metric_value is not None:
                        threshold_status = threshold.check_threshold(metric_value)
                        if threshold_status.value != result.status.value:
                            # Update status based on threshold
                            result.status = threshold_status
                            result.message = f"{result.message} (threshold: {threshold_status.value})"
                            results[name] = result.to_dict()
                            
                            # Update overall status again
                            if threshold_status == HealthStatus.CRITICAL:
                                overall_status = HealthStatus.CRITICAL
                            elif threshold_status == HealthStatus.UNHEALTHY and overall_status != HealthStatus.CRITICAL:
                                overall_status = HealthStatus.UNHEALTHY
                            elif threshold_status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                                overall_status = HealthStatus.DEGRADED
            
            except Exception as e:
                self.logger.error(f"Health check failed for {name}: {str(e)}")
                results[name] = {
                    'component': name,
                    'status': HealthStatus.CRITICAL.value,
                    'message': f"Health check failed: {str(e)}",
                    'error': str(e),
                    'timestamp': timezone.now().isoformat(),
                }
                overall_status = HealthStatus.CRITICAL
        
        # Record check history
        check_record = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status.value,
            'component_count': len(results),
            'healthy_count': len([r for r in results.values() if r['status'] in ['healthy', 'degraded']]),
            'unhealthy_count': len([r for r in results.values() if r['status'] in ['unhealthy', 'critical']]),
            'results': results,
        }
        
        self.check_history.append(check_record)
        
        # Keep only last 1000 records
        if len(self.check_history) > 1000:
            self.check_history = self.check_history[-1000:]
        
        return {
            'overall_status': overall_status.value,
            'timestamp': timezone.now().isoformat(),
            'components': results,
            'summary': {
                'total': len(results),
                'healthy': len([r for r in results.values() if r['status'] == 'healthy']),
                'degraded': len([r for r in results.values() if r['status'] == 'degraded']),
                'unhealthy': len([r for r in results.values() if r['status'] == 'unhealthy']),
                'critical': len([r for r in results.values() if r['status'] == 'critical']),
            }
        }
    
    def check_component(self, name: str) -> Optional[Dict[str, Any]]:
        """Check specific component."""
        checker = self.checkers.get(name)
        if not checker:
            return None
        
        if not checker.is_enabled():
            return {
                'component': name,
                'status': HealthStatus.UNKNOWN.value,
                'message': 'Health checker is disabled',
                'timestamp': timezone.now().isoformat(),
            }
        
        try:
            result = checker.check()
            return result.to_dict()
        except Exception as e:
            return {
                'component': name,
                'status': HealthStatus.CRITICAL.value,
                'message': f"Health check failed: {str(e)}",
                'error': str(e),
                'timestamp': timezone.now().isoformat(),
            }
    
    def start_monitoring(self, interval: int = None):
        """Start health monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        if interval:
            self.check_interval = interval
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"Health monitoring started (interval: {self.check_interval}s)")
    
    def stop_monitoring(self):
        """Stop health monitoring."""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("Health monitoring stopped")
    
    def _monitor_loop(self):
        """Health monitoring loop."""
        while self.monitoring:
            try:
                self.check_all()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {str(e)}")
                time.sleep(10)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        if not self.check_history:
            return {
                'current_status': 'unknown',
                'last_check': None,
                'component_count': 0,
                'monitoring_active': self.monitoring,
            }
        
        last_check = self.check_history[-1]
        
        return {
            'current_status': last_check['overall_status'],
            'last_check': last_check['timestamp'],
            'component_count': last_check['component_count'],
            'healthy_count': last_check['healthy_count'],
            'unhealthy_count': last_check['unhealthy_count'],
            'monitoring_active': self.monitoring,
            'check_interval': self.check_interval,
        }
    
    def get_check_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health check history."""
        return self.check_history[-limit:]
    
    def get_component_status(self, name: str) -> Optional[str]:
        """Get component status."""
        checker = self.checkers.get(name)
        if checker and checker.last_check:
            return checker.last_check.status.value
        return None
    
    def enable_checker(self, name: str):
        """Enable health checker."""
        checker = self.checkers.get(name)
        if checker:
            checker.enable()
    
    def disable_checker(self, name: str):
        """Disable health checker."""
        checker = self.checkers.get(name)
        if checker:
            checker.disable()


# Global health check manager instance
health_check_manager = HealthCheckManager()


# Decorators for health checking
def health_check(check_name: str = None, timeout: float = 30.0):
    """
    Decorator for health checking functions.
    
    Args:
        check_name: Health check name
        timeout: Timeout in seconds
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Create health check result
                health_result = HealthCheckResult(
                    component=check_name or func.__name__,
                    status=HealthStatus.HEALTHY,
                    message=f"{func.__name__} is healthy",
                    response_time=time.time() - start_time
                )
                
                return result
            
            except Exception as e:
                # Create health check result for failure
                health_result = HealthCheckResult(
                    component=check_name or func.__name__,
                    status=HealthStatus.CRITICAL,
                    message=f"{func.__name__} failed: {str(e)}",
                    error=str(e),
                    response_time=time.time() - start_time
                )
                
                # Store result in manager if name provided
                if check_name and check_name in health_check_manager.checkers:
                    health_check_manager.checkers[check_name].last_check = health_result
                
                raise
        
        return wrapper
    return decorator


# Convenience functions
def perform_health_check(component_name: str = None) -> Dict[str, Any]:
    """Perform health check."""
    if component_name:
        return health_check_manager.check_component(component_name)
    else:
        return health_check_manager.check_all()


def start_health_monitoring(interval: int = 60):
    """Start health monitoring."""
    health_check_manager.start_monitoring(interval)


def stop_health_monitoring():
    """Stop health monitoring."""
    health_check_manager.stop_monitoring()


def get_health_summary() -> Dict[str, Any]:
    """Get health summary."""
    return health_check_manager.get_health_summary()


def add_custom_health_checker(name: str, check_function: Callable, **kwargs):
    """Add custom health checker."""
    health_check_manager.add_custom_checker(name, check_function, **kwargs)
