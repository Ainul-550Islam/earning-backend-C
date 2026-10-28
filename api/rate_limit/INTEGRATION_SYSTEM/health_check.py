"""
Health Check System - Comprehensive Health Monitoring

Comprehensive health monitoring system for checking system health,
dependency status, and providing detailed health reports.
"""

import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.core.cache import cache
from django.utils import timezone
from django.db import connection
from django.core.management import call_command

from .integ_constants import IntegrationStatus
from .integ_exceptions import IntegrationError
from .performance_monitor import performance_monitor
from .circuit_breaker import circuit_breaker_manager
from .event_bus import event_bus

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check types."""
    DATABASE = "database"
    CACHE = "cache"
    REDIS = "redis"
    EXTERNAL_API = "external_api"
    DISK_SPACE = "disk_space"
    MEMORY = "memory"
    CPU = "cpu"
    SERVICE = "service"
    DEPENDENCY = "dependency"
    CUSTOM = "custom"


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_type: CheckType
    description: str
    timeout: int = 30
    interval: int = 60  # seconds
    enabled: bool = True
    critical: bool = False
    threshold: Optional[float] = None
    custom_check: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Health check result."""
    check_name: str
    status: HealthStatus
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=timezone.now)
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    score: float  # 0-100
    checks: Dict[str, HealthCheckResult] = field(default_factory=dict)
    summary: str = ""
    timestamp: datetime = field(default_factory=timezone.now)
    uptime_seconds: float = 0.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class HealthChecker:
    """Comprehensive health checking system."""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.check_results: Dict[str, HealthCheckResult] = {}
        self.custom_checkers: Dict[str, Callable] = {}
        self.system_start_time = timezone.now()
        self._lock = threading.RLock()
        self._running = False
        self._check_thread: Optional[threading.Thread] = None
        self.statistics = {
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'critical_failures': 0,
            'last_check_time': None,
            'average_check_time': 0.0
        }
        
        # Initialize default health checks
        self._initialize_default_checks()
        self._register_default_checkers()
        
        # Start health checking
        self._start_health_checking()
    
    def _initialize_default_checks(self):
        """Initialize default health checks."""
        default_checks = [
            HealthCheck(
                name="database",
                check_type=CheckType.DATABASE,
                description="Database connectivity and performance",
                timeout=10,
                interval=60,
                critical=True
            ),
            HealthCheck(
                name="cache",
                check_type=CheckType.CACHE,
                description="Cache system functionality",
                timeout=5,
                interval=30,
                critical=False
            ),
            HealthCheck(
                name="memory",
                check_type=CheckType.MEMORY,
                description="System memory usage",
                timeout=5,
                interval=60,
                threshold=85.0,  # 85% memory usage
                critical=False
            ),
            HealthCheck(
                name="disk_space",
                check_type=CheckType.DISK_SPACE,
                description="Disk space availability",
                timeout=5,
                interval=300,
                threshold=90.0,  # 90% disk usage
                critical=True
            ),
            HealthCheck(
                name="cpu",
                check_type=CheckType.CPU,
                description="CPU usage",
                timeout=5,
                interval=60,
                threshold=80.0,  # 80% CPU usage
                critical=False
            ),
            HealthCheck(
                name="rate_limit_service",
                check_type=CheckType.SERVICE,
                description="Rate limiting service health",
                timeout=10,
                interval=30,
                critical=True
            ),
            HealthCheck(
                name="integration_system",
                check_type=CheckType.SERVICE,
                description="Integration system health",
                timeout=10,
                interval=60,
                critical=False
            )
        ]
        
        for check in default_checks:
            self.health_checks[check.name] = check
    
    def _register_default_checkers(self):
        """Register default health checkers."""
        self.custom_checkers.update({
            'database': self._check_database,
            'cache': self._check_cache,
            'memory': self._check_memory,
            'disk_space': self._check_disk_space,
            'cpu': self._check_cpu,
            'rate_limit_service': self._check_rate_limit_service,
            'integration_system': self._check_integration_system
        })
    
    def _start_health_checking(self):
        """Start health checking thread."""
        self._running = True
        
        self._check_thread = threading.Thread(
            target=self._health_check_loop,
            name="HealthChecker",
            daemon=True
        )
        self._check_thread.start()
        
        logger.info("Started health checking system")
    
    def _health_check_loop(self):
        """Main health checking loop."""
        while self._running:
            try:
                # Run all enabled health checks
                self._run_all_checks()
                
                # Sleep until next check
                min_interval = min(
                    (check.interval for check in self.health_checks.values() if check.enabled),
                    default=60
                )
                
                time.sleep(min_interval)
                
            except Exception as e:
                logger.error(f"Health check loop error: {str(e)}")
                time.sleep(60)
    
    def _run_all_checks(self):
        """Run all enabled health checks."""
        for check_name, check in self.health_checks.items():
            if not check.enabled:
                continue
            
            # Check if this check should run now
            if not self._should_run_check(check):
                continue
            
            # Run the check
            result = self._run_health_check(check)
            
            # Store result
            with self._lock:
                self.check_results[check_name] = result
                self._update_statistics(result)
    
    def _should_run_check(self, check: HealthCheck) -> bool:
        """Check if health check should run now."""
        if not check.enabled:
            return False
        
        # Get last check time
        last_result = self.check_results.get(check.name)
        if not last_result:
            return True
        
        # Check if enough time has passed
        time_since_last = timezone.now() - last_result.timestamp
        return time_since_last.total_seconds() >= check.interval
    
    def _run_health_check(self, check: HealthCheck) -> HealthCheckResult:
        """Run a single health check."""
        start_time = timezone.now()
        
        try:
            # Get checker function
            checker = self.custom_checkers.get(check.name)
            if not checker:
                return HealthCheckResult(
                    check_name=check.name,
                    status=HealthStatus.UNKNOWN,
                    message=f"No checker found for {check.name}",
                    execution_time=(timezone.now() - start_time).total_seconds()
                )
            
            # Execute check with timeout
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Health check timeout: {check.name}")
            
            # Set timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(check.timeout)
            
            try:
                result = checker(check)
                signal.alarm(0)  # Cancel timeout
                
                if not isinstance(result, HealthCheckResult):
                    # Convert simple boolean result to HealthCheckResult
                    if isinstance(result, bool):
                        result = HealthCheckResult(
                            check_name=check.name,
                            status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                            message="Check passed" if result else "Check failed"
                        )
                    elif isinstance(result, dict):
                        result = HealthCheckResult(
                            check_name=check.name,
                            status=HealthStatus(result.get('status', 'unknown')),
                            message=result.get('message', ''),
                            value=result.get('value'),
                            threshold=result.get('threshold'),
                            details=result.get('details', {})
                        )
                
                # Set execution time
                result.execution_time = (timezone.now() - start_time).total_seconds()
                
                return result
                
            except TimeoutError:
                signal.alarm(0)
                return HealthCheckResult(
                    check_name=check.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check timeout after {check.timeout} seconds",
                    execution_time=(timezone.now() - start_time).total_seconds()
                )
                
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                execution_time=(timezone.now() - start_time).total_seconds(),
                error=str(e)
            )
    
    def _update_statistics(self, result: HealthCheckResult):
        """Update health check statistics."""
        self.statistics['total_checks'] += 1
        self.statistics['last_check_time'] = result.timestamp
        
        if result.status in [HealthStatus.HEALTHY]:
            self.statistics['passed_checks'] += 1
        else:
            self.statistics['failed_checks'] += 1
        
        # Update average check time
        total_checks = self.statistics['total_checks']
        if total_checks == 1:
            self.statistics['average_check_time'] = result.execution_time
        else:
            current_avg = self.statistics['average_check_time']
            self.statistics['average_check_time'] = (
                (current_avg * (total_checks - 1) + result.execution_time) / total_checks
            )
    
    # Default health check implementations
    def _check_database(self, check: HealthCheck) -> HealthCheckResult:
        """Check database connectivity and performance."""
        try:
            # Test database connection
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check response time
            if response_time > 1000:  # 1 second
                status = HealthStatus.DEGRADED
                message = f"Database response time is slow: {response_time:.2f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = f"Database is healthy (response time: {response_time:.2f}ms)"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=response_time,
                threshold=1000.0,
                details={'response_time_ms': response_time}
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                error=str(e)
            )
    
    def _check_cache(self, check: HealthCheck) -> HealthCheckResult:
        """Check cache system functionality."""
        try:
            # Test cache set/get
            test_key = f"health_check_{int(time.time())}"
            test_value = "test_value"
            
            start_time = time.time()
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if retrieved_value == test_value:
                status = HealthStatus.HEALTHY
                message = f"Cache is healthy (response time: {response_time:.2f}ms)"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Cache set/get test failed"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=response_time,
                details={'response_time_ms': response_time}
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Cache check failed: {str(e)}",
                error=str(e)
            )
    
    def _check_memory(self, check: HealthCheck) -> HealthCheckResult:
        """Check system memory usage."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Determine status based on threshold
            if check.threshold and memory_percent >= check.threshold:
                status = HealthStatus.DEGRADED if memory_percent < 95 else HealthStatus.CRITICAL
                message = f"High memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage is normal: {memory_percent:.1f}%"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=memory_percent,
                threshold=check.threshold,
                details={
                    'memory_percent': memory_percent,
                    'memory_used_mb': memory.used / (1024 * 1024),
                    'memory_total_mb': memory.total / (1024 * 1024),
                    'memory_available_mb': memory.available / (1024 * 1024)
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                error=str(e)
            )
    
    def _check_disk_space(self, check: HealthCheck) -> HealthCheckResult:
        """Check disk space availability."""
        try:
            import psutil
            
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Determine status based on threshold
            if check.threshold and disk_percent >= check.threshold:
                status = HealthStatus.DEGRADED if disk_percent < 95 else HealthStatus.CRITICAL
                message = f"Low disk space: {disk_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space is adequate: {disk_percent:.1f}% used"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=disk_percent,
                threshold=check.threshold,
                details={
                    'disk_percent': disk_percent,
                    'disk_used_gb': disk.used / (1024 ** 3),
                    'disk_total_gb': disk.total / (1024 ** 3),
                    'disk_free_gb': disk.free / (1024 ** 3)
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNKNOWN,
                message=f"Disk space check failed: {str(e)}",
                error=str(e)
            )
    
    def _check_cpu(self, check: HealthCheck) -> HealthCheckResult:
        """Check CPU usage."""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Determine status based on threshold
            if check.threshold and cpu_percent >= check.threshold:
                status = HealthStatus.DEGRADED if cpu_percent < 95 else HealthStatus.CRITICAL
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage is normal: {cpu_percent:.1f}%"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=cpu_percent,
                threshold=check.threshold,
                details={'cpu_percent': cpu_percent}
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNKNOWN,
                message=f"CPU check failed: {str(e)}",
                error=str(e)
            )
    
    def _check_rate_limit_service(self, check: HealthCheck) -> HealthCheckResult:
        """Check rate limiting service health."""
        try:
            # Check if rate limit service is responding
            from api.rate_limit.services.RateLimitService import RateLimitService
            
            start_time = time.time()
            is_limited, remaining, metadata = RateLimitService.is_rate_limited(
                identifier="health_check",
                limit_type="test",
                max_requests=100
            )
            response_time = (time.time() - start_time) * 1000
            
            status = HealthStatus.HEALTHY
            message = f"Rate limit service is healthy (response time: {response_time:.2f}ms)"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                value=response_time,
                details={
                    'response_time_ms': response_time,
                    'is_limited': is_limited,
                    'remaining': remaining,
                    'metadata': metadata
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Rate limit service check failed: {str(e)}",
                error=str(e)
            )
    
    def _check_integration_system(self, check: HealthCheck) -> HealthCheckResult:
        """Check integration system health."""
        try:
            # Check event bus health
            event_bus_health = event_bus.health_check()
            
            # Check circuit breaker health
            circuit_breaker_health = circuit_breaker_manager.health_check()
            
            # Check performance monitor
            perf_stats = performance_monitor.get_statistics()
            
            # Determine overall status
            if (event_bus_health.get('status') == 'healthy' and
                circuit_breaker_health.get('healthy_bridges', 0) > 0):
                status = HealthStatus.HEALTHY
                message = "Integration system is healthy"
            else:
                status = HealthStatus.DEGRADED
                message = "Integration system has issues"
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                details={
                    'event_bus_health': event_bus_health,
                    'circuit_breaker_health': circuit_breaker_health,
                    'performance_stats': perf_stats
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNKNOWN,
                message=f"Integration system check failed: {str(e)}",
                error=str(e)
            )
    
    def register_health_check(self, check: HealthCheck):
        """Register a new health check."""
        self.health_checks[check.name] = check
        logger.info(f"Registered health check: {check.name}")
    
    def register_custom_checker(self, name: str, checker: Callable):
        """Register custom health checker."""
        self.custom_checkers[name] = checker
        logger.info(f"Registered custom health checker: {name}")
    
    def run_check(self, check_name: str) -> HealthCheckResult:
        """Run a specific health check."""
        check = self.health_checks.get(check_name)
        if not check:
            raise IntegrationError(f"Health check not found: {check_name}")
        
        return self._run_health_check(check)
    
    def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        current_time = timezone.now()
        
        # Get all check results
        all_results = dict(self.check_results)
        
        # Calculate overall status
        critical_failures = 0
        unhealthy_checks = 0
        degraded_checks = 0
        healthy_checks = 0
        
        for result in all_results.values():
            if result.status == HealthStatus.CRITICAL:
                critical_failures += 1
            elif result.status == HealthStatus.UNHEALTHY:
                unhealthy_checks += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_checks += 1
            elif result.status == HealthStatus.HEALTHY:
                healthy_checks += 1
        
        # Determine overall status
        if critical_failures > 0:
            overall_status = HealthStatus.CRITICAL
        elif unhealthy_checks > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_checks > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Calculate health score
        total_checks = len(all_results)
        if total_checks == 0:
            health_score = 50.0  # Unknown
        else:
            health_score = (healthy_checks / total_checks) * 100
        
        # Generate summary
        if overall_status == HealthStatus.HEALTHY:
            summary = "All systems are operating normally"
        elif overall_status == HealthStatus.DEGRADED:
            summary = f"System performance is degraded ({degraded_checks} checks degraded)"
        elif overall_status == HealthStatus.UNHEALTHY:
            summary = f"System has issues ({unhealthy_checks} checks unhealthy)"
        else:
            summary = f"System has critical issues ({critical_failures} critical failures)"
        
        # Generate issues and recommendations
        issues = []
        recommendations = []
        
        for check_name, result in all_results.items():
            if result.status != HealthStatus.HEALTHY:
                issues.append(f"{check_name}: {result.message}")
                
                # Add recommendations based on check type
                if check_name == "memory":
                    recommendations.append("Consider increasing memory or optimizing memory usage")
                elif check_name == "disk_space":
                    recommendations.append("Free up disk space or add more storage")
                elif check_name == "cpu":
                    recommendations.append("Optimize CPU usage or scale up resources")
                elif check_name == "database":
                    recommendations.append("Check database performance and connectivity")
                elif check_name == "cache":
                    recommendations.append("Verify cache configuration and connectivity")
        
        # Calculate uptime
        uptime_seconds = (current_time - self.system_start_time).total_seconds()
        
        return SystemHealth(
            status=overall_status,
            score=health_score,
            checks=all_results,
            summary=summary,
            timestamp=current_time,
            uptime_seconds=uptime_seconds,
            issues=issues,
            recommendations=recommendations
        )
    
    def get_check_results(self, check_name: str = None) -> Dict[str, HealthCheckResult]:
        """Get health check results."""
        if check_name:
            return {check_name: self.check_results.get(check_name)}
        return dict(self.check_results)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health check statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'total_health_checks': len(self.health_checks),
                'enabled_health_checks': len([c for c in self.health_checks.values() if c.enabled]),
                'critical_health_checks': len([c for c in self.health_checks.values() if c.critical]),
                'running': self._running,
                'uptime_hours': (timezone.now() - self.system_start_time).total_seconds() / 3600
            })
            return stats
    
    def enable_check(self, check_name: str):
        """Enable a health check."""
        if check_name in self.health_checks:
            self.health_checks[check_name].enabled = True
            logger.info(f"Enabled health check: {check_name}")
    
    def disable_check(self, check_name: str):
        """Disable a health check."""
        if check_name in self.health_checks:
            self.health_checks[check_name].enabled = False
            logger.info(f"Disabled health check: {check_name}")
    
    def shutdown(self):
        """Shutdown health checking system."""
        logger.info("Shutting down health checking system...")
        
        self._running = False
        
        # Wait for thread to finish
        if self._check_thread:
            self._check_thread.join(timeout=5)
        
        logger.info("Health checking system shutdown complete")


# Global health checker instance
health_checker = HealthChecker()


# Decorator for health checking
def health_check(check_name: str, timeout: int = 30):
    """Decorator to add health checking to functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                # Update health check result
                health_result = HealthCheckResult(
                    check_name=check_name,
                    status=HealthStatus.HEALTHY,
                    message=f"Function {func.__name__} executed successfully",
                    value=execution_time,
                    details={'execution_time_ms': execution_time}
                )
                
                health_checker.check_results[check_name] = health_result
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                # Update health check result
                health_result = HealthCheckResult(
                    check_name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Function {func.__name__} failed: {str(e)}",
                    value=execution_time,
                    details={'execution_time_ms': execution_time},
                    error=str(e)
                )
                
                health_checker.check_results[check_name] = health_result
                raise
        
        return wrapper
    return decorator


# Convenience functions
def create_health_check(name: str, check_type: CheckType, description: str,
                        timeout: int = 30, interval: int = 60, **kwargs) -> HealthCheck:
    """Create a health check."""
    return HealthCheck(
        name=name,
        check_type=check_type,
        description=description,
        timeout=timeout,
        interval=interval,
        **kwargs
    )


def is_system_healthy() -> bool:
    """Check if system is healthy."""
    health = health_checker.get_system_health()
    return health.status == HealthStatus.HEALTHY


def get_health_summary() -> str:
    """Get health summary."""
    health = health_checker.get_system_health()
    return f"System Status: {health.status.value.upper()} (Score: {health.score:.1f}/100)"
