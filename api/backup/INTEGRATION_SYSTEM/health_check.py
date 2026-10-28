"""
Health Check
Comprehensive health monitoring for integration system
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
from abc import ABC, abstractmethod

from .integ_exceptions import IntegrationException, HealthCheckException

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check types"""
    CONNECTIVITY = "connectivity"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    RESOURCE = "resource"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    CUSTOM = "custom"


class CheckSeverity(Enum):
    """Check severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Health check result"""
    check_name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: CheckSeverity = CheckSeverity.MEDIUM
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'check_name': self.check_name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'tags': self.tags,
            'metadata': self.metadata
        }


@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    check_name: str
    check_type: CheckType
    enabled: bool = True
    interval_seconds: int = 60
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    severity: CheckSeverity = CheckSeverity.MEDIUM
    tags: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class SystemHealthReport:
    """System health report"""
    timestamp: datetime
    overall_status: HealthStatus
    total_checks: int
    healthy_checks: int
    degraded_checks: int
    unhealthy_checks: int
    unknown_checks: int
    check_results: List[HealthCheckResult]
    summary: str
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'overall_status': self.overall_status.value,
            'total_checks': self.total_checks,
            'healthy_checks': self.healthy_checks,
            'degraded_checks': self.degraded_checks,
            'unhealthy_checks': self.unhealthy_checks,
            'unknown_checks': self.unknown_checks,
            'check_results': [result.to_dict() for result in self.check_results],
            'summary': self.summary,
            'recommendations': self.recommendations,
            'metadata': self.metadata
        }


class BaseHealthChecker(ABC):
    """Abstract base class for health checkers"""
    
    @abstractmethod
    async def check_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Perform health check"""
        pass
    
    @abstractmethod
    def can_handle(self, check_type: CheckType) -> bool:
        """Check if checker can handle check type"""
        pass


class ConnectivityHealthChecker(BaseHealthChecker):
    """Connectivity health checker"""
    
    def can_handle(self, check_type: CheckType) -> bool:
        return check_type == CheckType.CONNECTIVITY
    
    async def check_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check connectivity health"""
        start_time = time.time()
        
        try:
            target_url = config.parameters.get('url')
            timeout = config.parameters.get('timeout', config.timeout_seconds)
            
            if not target_url:
                return HealthCheckResult(
                    check_name=config.check_name,
                    status=HealthStatus.UNHEALTHY,
                    message="No target URL configured",
                    severity=config.severity,
                    tags=config.tags
                )
            
            # Perform connectivity check
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                try:
                    async with session.get(target_url) as response:
                        if response.status < 400:
                            status = HealthStatus.HEALTHY
                            message = f"Connectivity OK (HTTP {response.status})"
                        elif response.status < 500:
                            status = HealthStatus.DEGRADED
                            message = f"Connectivity degraded (HTTP {response.status})"
                        else:
                            status = HealthStatus.UNHEALTHY
                            message = f"Connectivity failed (HTTP {response.status})"
                        
                        details = {
                            'url': target_url,
                            'status_code': response.status,
                            'response_time_ms': (time.time() - start_time) * 1000,
                            'headers': dict(response.headers)
                        }
                        
                except asyncio.TimeoutError:
                    status = HealthStatus.UNHEALTHY
                    message = "Connectivity timeout"
                    details = {'url': target_url, 'timeout': timeout}
                
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Connectivity check failed: {str(e)}"
            details = {'error': str(e)}
        
        duration_ms = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
            severity=config.severity,
            tags=config.tags
        )


class PerformanceHealthChecker(BaseHealthChecker):
    """Performance health checker"""
    
    def can_handle(self, check_type: CheckType) -> bool:
        return check_type == CheckType.PERFORMANCE
    
    async def check_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check performance health"""
        start_time = time.time()
        
        try:
            # Get performance metrics
            import psutil
            
            cpu_threshold = config.parameters.get('cpu_threshold', 80.0)
            memory_threshold = config.parameters.get('memory_threshold', 85.0)
            disk_threshold = config.parameters.get('disk_threshold', 90.0)
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine status
            issues = []
            
            if cpu_percent > cpu_threshold:
                issues.append(f"High CPU usage: {cpu_percent}%")
            
            if memory.percent > memory_threshold:
                issues.append(f"High memory usage: {memory.percent}%")
            
            if disk.percent > disk_threshold:
                issues.append(f"High disk usage: {disk.percent}%")
            
            if not issues:
                status = HealthStatus.HEALTHY
                message = "Performance metrics are healthy"
            elif len(issues) == 1:
                status = HealthStatus.DEGRADED
                message = issues[0]
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Multiple performance issues: {'; '.join(issues)}"
            
            details = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'memory_available': memory.available,
                'disk_free': disk.free,
                'thresholds': {
                    'cpu': cpu_threshold,
                    'memory': memory_threshold,
                    'disk': disk_threshold
                }
            }
            
        except Exception as e:
            status = HealthStatus.UNKNOWN
            message = f"Performance check failed: {str(e)}"
            details = {'error': str(e)}
        
        duration_ms = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
            severity=config.severity,
            tags=config.tags
        )


class AvailabilityHealthChecker(BaseHealthChecker):
    """Availability health checker"""
    
    def can_handle(self, check_type: CheckType) -> bool:
        return check_type == CheckType.AVAILABILITY
    
    async def check_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check availability health"""
        start_time = time.time()
        
        try:
            service_name = config.parameters.get('service_name')
            check_endpoint = config.parameters.get('check_endpoint')
            
            if not service_name:
                return HealthCheckResult(
                    check_name=config.check_name,
                    status=HealthStatus.UNHEALTHY,
                    message="No service name configured",
                    severity=config.severity,
                    tags=config.tags
                )
            
            # Check service availability
            if check_endpoint:
                # Use connectivity checker for endpoint
                connectivity_config = HealthCheckConfig(
                    check_name=f"{config.check_name}_endpoint",
                    check_type=CheckType.CONNECTIVITY,
                    parameters={'url': check_endpoint},
                    severity=config.severity,
                    tags=config.tags + ['availability']
                )
                
                connectivity_checker = ConnectivityHealthChecker()
                endpoint_result = await connectivity_checker.check_health(connectivity_config)
                
                if endpoint_result.status == HealthStatus.HEALTHY:
                    status = HealthStatus.HEALTHY
                    message = f"Service {service_name} is available"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"Service {service_name} is unavailable: {endpoint_result.message}"
                
                details = {
                    'service_name': service_name,
                    'check_endpoint': check_endpoint,
                    'endpoint_check': endpoint_result.to_dict()
                }
            else:
                # Check process availability
                import psutil
                
                processes = [p for p in psutil.process_iter(['name']) 
                           if service_name.lower() in p.info['name'].lower()]
                
                if processes:
                    status = HealthStatus.HEALTHY
                    message = f"Service {service_name} is running ({len(processes)} processes)"
                    details = {
                        'service_name': service_name,
                        'process_count': len(processes),
                        'processes': [{'pid': p.pid, 'name': p.info['name']} for p in processes[:5]]
                    }
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"Service {service_name} is not running"
                    details = {
                        'service_name': service_name,
                        'process_count': 0
                    }
            
        except Exception as e:
            status = HealthStatus.UNKNOWN
            message = f"Availability check failed: {str(e)}"
            details = {'error': str(e)}
        
        duration_ms = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
            severity=config.severity,
            tags=config.tags
        )


class ResourceHealthChecker(BaseHealthChecker):
    """Resource health checker"""
    
    def can_handle(self, check_type: CheckType) -> bool:
        return check_type == CheckType.RESOURCE
    
    async def check_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check resource health"""
        start_time = time.time()
        
        try:
            resource_type = config.parameters.get('resource_type')
            
            if resource_type == 'disk_space':
                return await self._check_disk_space(config)
            elif resource_type == 'memory':
                return await self._check_memory(config)
            elif resource_type == 'file_permissions':
                return await self._check_file_permissions(config)
            else:
                status = HealthStatus.UNKNOWN
                message = f"Unknown resource type: {resource_type}"
                details = {'resource_type': resource_type}
            
        except Exception as e:
            status = HealthStatus.UNKNOWN
            message = f"Resource check failed: {str(e)}"
            details = {'error': str(e)}
        
        duration_ms = (time.time() - start_time) * 1000
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
            severity=config.severity,
            tags=config.tags
        )
    
    async def _check_disk_space(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check disk space"""
        import psutil
        
        path = config.parameters.get('path', '/')
        threshold = config.parameters.get('threshold', 90.0)
        
        disk = psutil.disk_usage(path)
        usage_percent = (disk.used / disk.total) * 100
        
        if usage_percent < threshold:
            status = HealthStatus.HEALTHY
            message = f"Disk space OK ({usage_percent:.1f}% used)"
        elif usage_percent < 95:
            status = HealthStatus.DEGRADED
            message = f"Disk space low ({usage_percent:.1f}% used)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Disk space critical ({usage_percent:.1f}% used)"
        
        details = {
            'path': path,
            'total_bytes': disk.total,
            'used_bytes': disk.used,
            'free_bytes': disk.free,
            'usage_percent': usage_percent,
            'threshold': threshold
        }
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            severity=config.severity,
            tags=config.tags
        )
    
    async def _check_memory(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check memory"""
        import psutil
        
        threshold = config.parameters.get('threshold', 85.0)
        
        memory = psutil.virtual_memory()
        usage_percent = memory.percent
        
        if usage_percent < threshold:
            status = HealthStatus.HEALTHY
            message = f"Memory OK ({usage_percent:.1f}% used)"
        elif usage_percent < 95:
            status = HealthStatus.DEGRADED
            message = f"Memory low ({usage_percent:.1f}% used)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Memory critical ({usage_percent:.1f}% used)"
        
        details = {
            'total_bytes': memory.total,
            'available_bytes': memory.available,
            'used_bytes': memory.used,
            'usage_percent': usage_percent,
            'threshold': threshold
        }
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            severity=config.severity,
            tags=config.tags
        )
    
    async def _check_file_permissions(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check file permissions"""
        import os
        
        file_path = config.parameters.get('file_path')
        
        if not file_path or not os.path.exists(file_path):
            return HealthCheckResult(
                check_name=config.check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"File not found: {file_path}",
                details={'file_path': file_path},
                severity=config.severity,
                tags=config.tags
            )
        
        try:
            # Check read permission
            with open(file_path, 'r') as f:
                f.read(1)
            
            # Check write permission if specified
            can_write = True
            if config.parameters.get('check_write', False):
                try:
                    with open(file_path, 'a') as f:
                        f.write('')
                except:
                    can_write = False
            
            if can_write:
                status = HealthStatus.HEALTHY
                message = f"File permissions OK: {file_path}"
            else:
                status = HealthStatus.DEGRADED
                message = f"File read-only: {file_path}"
            
            details = {
                'file_path': file_path,
                'can_read': True,
                'can_write': can_write,
                'file_size': os.path.getsize(file_path),
                'file_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
        except PermissionError:
            status = HealthStatus.UNHEALTHY
            message = f"Permission denied: {file_path}"
            details = {'file_path': file_path, 'error': 'Permission denied'}
        except Exception as e:
            status = HealthStatus.UNKNOWN
            message = f"File check failed: {str(e)}"
            details = {'file_path': file_path, 'error': str(e)}
        
        return HealthCheckResult(
            check_name=config.check_name,
            status=status,
            message=message,
            details=details,
            severity=config.severity,
            tags=config.tags
        )


class HealthCheckManager:
    """
    Health check manager for integration system
    """
    
    def __init__(self):
        self.check_configs: Dict[str, HealthCheckConfig] = {}
        self.checkers: Dict[CheckType, BaseHealthChecker] = {}
        self.check_results: Dict[str, HealthCheckResult] = {}
        self.is_running = False
        self._monitoring_task = None
        
        # Initialize default checkers
        self._initialize_checkers()
        
        # Setup default health checks
        self._setup_default_checks()
    
    def _initialize_checkers(self):
        """Initialize default health checkers"""
        self.checkers[CheckType.CONNECTIVITY] = ConnectivityHealthChecker()
        self.checkers[CheckType.PERFORMANCE] = PerformanceHealthChecker()
        self.checkers[CheckType.AVAILABILITY] = AvailabilityHealthChecker()
        self.checkers[CheckType.RESOURCE] = ResourceHealthChecker()
    
    def _setup_default_checks(self):
        """Setup default health checks"""
        default_checks = [
            HealthCheckConfig(
                check_name="system_performance",
                check_type=CheckType.PERFORMANCE,
                interval_seconds=60,
                severity=CheckSeverity.HIGH,
                tags=['system', 'performance']
            ),
            HealthCheckConfig(
                check_name="disk_space",
                check_type=CheckType.RESOURCE,
                interval_seconds=300,
                severity=CheckSeverity.MEDIUM,
                parameters={
                    'resource_type': 'disk_space',
                    'threshold': 90.0
                },
                tags=['system', 'resource']
            ),
            HealthCheckConfig(
                check_name="memory_usage",
                check_type=CheckType.RESOURCE,
                interval_seconds=60,
                severity=CheckSeverity.HIGH,
                parameters={
                    'resource_type': 'memory',
                    'threshold': 85.0
                },
                tags=['system', 'resource']
            )
        ]
        
        for check in default_checks:
            self.add_check(check)
    
    def add_check(self, config: HealthCheckConfig):
        """Add a health check"""
        self.check_configs[config.check_name] = config
    
    def remove_check(self, check_name: str):
        """Remove a health check"""
        self.check_configs.pop(check_name, None)
        self.check_results.pop(check_name, None)
    
    def add_checker(self, check_type: CheckType, checker: BaseHealthChecker):
        """Add a custom health checker"""
        self.checkers[check_type] = checker
    
    async def start_monitoring(self):
        """Start health monitoring"""
        if self.is_running:
            return
        
        try:
            self.is_running = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Health monitoring started")
            
        except Exception as e:
            self.is_running = False
            logger.error(f"Failed to start health monitoring: {e}")
            raise HealthCheckException(f"Failed to start monitoring: {e}")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Health monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping health monitoring: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                # Run all enabled checks
                tasks = []
                for config in self.check_configs.values():
                    if config.enabled:
                        task = asyncio.create_task(self._run_check(config))
                        tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait for next iteration (use minimum interval)
                min_interval = min(
                    (config.interval_seconds for config in self.check_configs.values() if config.enabled),
                    default=60
                )
                await asyncio.sleep(min_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _run_check(self, config: HealthCheckConfig):
        """Run a single health check"""
        start_time = time.time()
        
        try:
            # Get checker for check type
            checker = self.checkers.get(config.check_type)
            if not checker:
                result = HealthCheckResult(
                    check_name=config.check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"No checker found for type: {config.check_type.value}",
                    severity=config.severity,
                    tags=config.tags
                )
            else:
                # Run check with retries
                result = await self._run_check_with_retries(checker, config)
            
            # Store result
            self.check_results[config.check_name] = result
            
        except Exception as e:
            result = HealthCheckResult(
                check_name=config.check_name,
                status=HealthStatus.UNKNOWN,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                severity=config.severity,
                tags=config.tags
            )
            self.check_results[config.check_name] = result
    
    async def _run_check_with_retries(self, checker: BaseHealthChecker, 
                                    config: HealthCheckConfig) -> HealthCheckResult:
        """Run health check with retries"""
        last_result = None
        
        for attempt in range(config.max_retries + 1):
            try:
                # Run check with timeout
                result = await asyncio.wait_for(
                    checker.check_health(config),
                    timeout=config.timeout_seconds
                )
                
                if result.status != HealthStatus.UNKNOWN:
                    return result
                
                last_result = result
                
            except asyncio.TimeoutError:
                last_result = HealthCheckResult(
                    check_name=config.check_name,
                    status=HealthStatus.UNHEALTHY,
                    message="Health check timeout",
                    severity=config.severity,
                    tags=config.tags
                )
            except Exception as e:
                last_result = HealthCheckResult(
                    check_name=config.check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check error: {str(e)}",
                    details={'error': str(e)},
                    severity=config.severity,
                    tags=config.tags
                )
            
            # Wait before retry
            if attempt < config.max_retries:
                await asyncio.sleep(config.retry_delay_seconds)
        
        return last_result
    
    async def run_all_checks(self) -> SystemHealthReport:
        """Run all health checks and generate report"""
        tasks = []
        for config in self.check_configs.values():
            if config.enabled:
                task = asyncio.create_task(self._run_check(config))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.generate_health_report()
    
    def generate_health_report(self) -> SystemHealthReport:
        """Generate system health report"""
        results = list(self.check_results.values())
        
        if not results:
            return SystemHealthReport(
                timestamp=datetime.utcnow(),
                overall_status=HealthStatus.UNKNOWN,
                total_checks=0,
                healthy_checks=0,
                degraded_checks=0,
                unhealthy_checks=0,
                unknown_checks=0,
                check_results=[],
                summary="No health checks configured"
            )
        
        # Count by status
        healthy = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        degraded = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        unknown = sum(1 for r in results if r.status == HealthStatus.UNKNOWN)
        
        # Determine overall status
        if unhealthy > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded > 0:
            overall_status = HealthStatus.DEGRADED
        elif unknown > 0 and healthy == 0:
            overall_status = HealthStatus.UNKNOWN
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Generate summary
        if overall_status == HealthStatus.HEALTHY:
            summary = f"All {len(results)} health checks passed"
        elif overall_status == HealthStatus.DEGRADED:
            summary = f"{degraded} of {len(results)} health checks show degraded performance"
        elif overall_status == HealthStatus.UNHEALTHY:
            summary = f"{unhealthy} of {len(results)} health checks failed"
        else:
            summary = f"{unknown} of {len(results)} health checks have unknown status"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(results)
        
        return SystemHealthReport(
            timestamp=datetime.utcnow(),
            overall_status=overall_status,
            total_checks=len(results),
            healthy_checks=healthy,
            degraded_checks=degraded,
            unhealthy_checks=unhealthy,
            unknown_checks=unknown,
            check_results=results,
            summary=summary,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, results: List[HealthCheckResult]) -> List[str]:
        """Generate health recommendations"""
        recommendations = []
        
        # Count issues by type
        performance_issues = [r for r in results if r.status != HealthStatus.HEALTHY and 'performance' in r.tags]
        resource_issues = [r for r in results if r.status != HealthStatus.HEALTHY and 'resource' in r.tags]
        connectivity_issues = [r for r in results if r.status != HealthStatus.HEALTHY and 'connectivity' in r.tags]
        
        if performance_issues:
            recommendations.append("Performance issues detected. Consider optimizing system resources or scaling up.")
        
        if resource_issues:
            recommendations.append("Resource issues detected. Check disk space, memory usage, and file permissions.")
        
        if connectivity_issues:
            recommendations.append("Connectivity issues detected. Check network connections and service availability.")
        
        # Critical issues
        critical_issues = [r for r in results if r.severity == CheckSeverity.CRITICAL and r.status != HealthStatus.HEALTHY]
        if critical_issues:
            recommendations.append(f"{len(critical_issues)} critical issues require immediate attention.")
        
        return recommendations
    
    def get_check_result(self, check_name: str) -> Optional[HealthCheckResult]:
        """Get result for a specific check"""
        return self.check_results.get(check_name)
    
    def get_all_check_results(self) -> Dict[str, HealthCheckResult]:
        """Get all check results"""
        return self.check_results.copy()


# Global health check manager instance
_health_manager = None


def get_health_manager() -> HealthCheckManager:
    """Get the global health manager instance"""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthCheckManager()
    return _health_manager


def initialize_health_manager() -> HealthCheckManager:
    """Initialize the global health manager"""
    global _health_manager
    _health_manager = HealthCheckManager()
    return _health_manager


# Export main classes and functions
__all__ = [
    'HealthCheckManager',
    'HealthCheckResult',
    'HealthCheckConfig',
    'SystemHealthReport',
    'BaseHealthChecker',
    'ConnectivityHealthChecker',
    'PerformanceHealthChecker',
    'AvailabilityHealthChecker',
    'ResourceHealthChecker',
    'HealthStatus',
    'CheckType',
    'CheckSeverity',
    'get_health_manager',
    'initialize_health_manager',
]
