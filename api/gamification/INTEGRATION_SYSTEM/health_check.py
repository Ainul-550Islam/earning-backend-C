"""
Health Check System — Comprehensive health monitoring and diagnostics.

This module provides health check capabilities for monitoring system health,
component status, and integration availability.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import IntegrationError, ServiceUnavailableError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health Check Types
# ---------------------------------------------------------------------------

class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Check type enumeration."""
    CONNECTIVITY = "connectivity"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    CUSTOM = "custom"


class Severity(Enum):
    """Severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Health Check Data Classes
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    """Result of a health check."""
    
    check_name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if result is healthy."""
        return self.status == HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "metrics": self.metrics,
            "tags": self.tags,
            "is_healthy": self.is_healthy
        }


@dataclass
class HealthCheck:
    """Health check definition."""
    
    name: str
    check_type: CheckType
    description: str = ""
    enabled: bool = True
    timeout: float = 10.0
    interval: float = 60.0  # seconds
    severity: Severity = Severity.MEDIUM
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Other check names
    thresholds: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.check_type.value,
            "description": self.description,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "interval": self.interval,
            "severity": self.severity.value,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "thresholds": self.thresholds,
            "metadata": self.metadata
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    
    component_name: str
    status: HealthStatus
    checks: List[HealthCheckResult] = field(default_factory=list)
    last_check: Optional[datetime] = None
    uptime_percentage: float = 100.0
    total_checks: int = 0
    failed_checks: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_checks == 0:
            return 1.0
        return (self.total_checks - self.failed_checks) / self.total_checks
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component_name": self.component_name,
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "uptime_percentage": self.uptime_percentage,
            "total_checks": self.total_checks,
            "failed_checks": self.failed_checks,
            "success_rate": self.success_rate,
            "metrics": self.metrics
        }


@dataclass
class SystemHealth:
    """Overall system health."""
    
    status: HealthStatus
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def healthy_components(self) -> int:
        """Count healthy components."""
        return len([c for c in self.components.values() if c.status == HealthStatus.HEALTHY])
    
    @property
    def total_components(self) -> int:
        """Count total components."""
        return len(self.components)
    
    @property
    def health_percentage(self) -> float:
        """Calculate overall health percentage."""
        if self.total_components == 0:
            return 100.0
        return (self.healthy_components / self.total_components) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "components": {name: health.to_dict() for name, health in self.components.items()},
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "healthy_components": self.healthy_components,
                "total_components": self.total_components,
                "health_percentage": self.health_percentage
            },
            "overall_metrics": self.summary
        }


# ---------------------------------------------------------------------------
# Abstract Health Checker
# ---------------------------------------------------------------------------

class BaseHealthChecker(ABC):
    """Abstract base class for health checkers."""
    
    @abstractmethod
    def check(self, check: HealthCheck) -> HealthCheckResult:
        """Perform health check."""
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[CheckType]:
        """Get supported check types."""
        pass


# ---------------------------------------------------------------------------
# Built-in Health Checkers
# ---------------------------------------------------------------------------

class ConnectivityHealthChecker(BaseHealthChecker):
    """Checker for connectivity health."""
    
    def check(self, check: HealthCheck) -> HealthCheckResult:
        """Check connectivity."""
        start_time = time.time()
        
        try:
            # This would perform actual connectivity checks
            # For now, we'll simulate a check
            endpoint = check.metadata.get("endpoint")
            if endpoint:
                # Simulate HTTP check
                import requests
                
                response = requests.get(endpoint, timeout=check.timeout)
                
                if response.status_code < 400:
                    status = HealthStatus.HEALTHY
                    message = f"Connectivity to {endpoint} successful"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"HTTP {response.status_code} from {endpoint}"
                
                metrics = {
                    "response_time": response.elapsed.total_seconds(),
                    "status_code": response.status_code
                }
                
            else:
                status = HealthStatus.UNKNOWN
                message = "No endpoint specified"
                metrics = {}
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                duration=duration,
                metrics=metrics
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connectivity check failed: {str(e)}",
                duration=duration,
                error=str(e)
            )
    
    def get_supported_types(self) -> List[CheckType]:
        return [CheckType.CONNECTIVITY]


class PerformanceHealthChecker(BaseHealthChecker):
    """Checker for performance health."""
    
    def check(self, check: HealthCheck) -> HealthCheckResult:
        """Check performance."""
        start_time = time.time()
        
        try:
            # This would perform actual performance checks
            # For now, we'll simulate with system metrics
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / 1024 / 1024
            }
            
            # Evaluate thresholds
            status = HealthStatus.HEALTHY
            message = "Performance metrics within normal range"
            
            cpu_threshold = check.thresholds.get("cpu_percent", 80.0)
            memory_threshold = check.thresholds.get("memory_percent", 80.0)
            
            if cpu_percent > cpu_threshold or memory.percent > memory_threshold:
                status = HealthStatus.DEGRADED
                message = "Performance metrics degraded"
            
            if cpu_percent > 95 or memory.percent > 95:
                status = HealthStatus.UNHEALTHY
                message = "Performance metrics critical"
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                duration=duration,
                metrics=metrics
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Performance check failed: {str(e)}",
                duration=duration,
                error=str(e)
            )
    
    def get_supported_types(self) -> List[CheckType]:
        return [CheckType.PERFORMANCE]


class ResourceHealthChecker(BaseHealthChecker):
    """Checker for resource health."""
    
    def check(self, check: HealthCheck) -> HealthCheckResult:
        """Check resource availability."""
        start_time = time.time()
        
        try:
            # This would check specific resources
            # For now, we'll simulate disk space check
            import psutil
            
            disk = psutil.disk_usage('/')
            
            metrics = {
                "disk_usage_percent": disk.percent,
                "disk_free_gb": disk.free / 1024 / 1024 / 1024,
                "disk_used_gb": disk.used / 1024 / 1024 / 1024
            }
            
            # Evaluate thresholds
            status = HealthStatus.HEALTHY
            message = "Resource usage within normal range"
            
            disk_threshold = check.thresholds.get("disk_usage_percent", 80.0)
            
            if disk.percent > disk_threshold:
                status = HealthStatus.DEGRADED
                message = "Disk space running low"
            
            if disk.percent > 95:
                status = HealthStatus.UNHEALTHY
                message = "Disk space critical"
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                duration=duration,
                metrics=metrics
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Resource check failed: {str(e)}",
                duration=duration,
                error=str(e)
            )
    
    def get_supported_types(self) -> List[CheckType]:
        return [CheckType.RESOURCE]


class DependencyHealthChecker(BaseHealthChecker):
    """Checker for dependency health."""
    
    def check(self, check: HealthCheck) -> HealthCheckResult:
        """Check dependency health."""
        start_time = time.time()
        
        try:
            dependencies = check.metadata.get("dependencies", [])
            
            if not dependencies:
                return HealthCheckResult(
                    check_name=check.name,
                    status=HealthStatus.HEALTHY,
                    message="No dependencies to check",
                    duration=time.time() - start_time
                )
            
            all_healthy = True
            failed_deps = []
            
            for dep in dependencies:
                # This would check actual dependency health
                # For now, we'll simulate
                dep_healthy = True  # Would check actual dependency
                
                if not dep_healthy:
                    all_healthy = False
                    failed_deps.append(dep)
            
            status = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY
            message = f"Dependencies {'healthy' if all_healthy else f'unhealthy: {failed_deps}'}"
            
            metrics = {
                "total_dependencies": len(dependencies),
                "healthy_dependencies": len(dependencies) - len(failed_deps),
                "failed_dependencies": len(failed_deps)
            }
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=status,
                message=message,
                duration=duration,
                metrics=metrics
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            return HealthCheckResult(
                check_name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Dependency check failed: {str(e)}",
                duration=duration,
                error=str(e)
            )
    
    def get_supported_types(self) -> List[CheckType]:
        return [CheckType.DEPENDENCY]


# ---------------------------------------------------------------------------
# Health Manager Implementation
# ---------------------------------------------------------------------------

class HealthManager:
    """Main health management system."""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.checkers: Dict[CheckType, BaseHealthChecker] = {}
        self.components: Dict[str, ComponentHealth] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Register built-in checkers
        self._register_builtin_checkers()
    
    def _register_builtin_checkers(self) -> None:
        """Register built-in health checkers."""
        checkers = [
            ConnectivityHealthChecker(),
            PerformanceHealthChecker(),
            ResourceHealthChecker(),
            DependencyHealthChecker()
        ]
        
        for checker in checkers:
            for check_type in checker.get_supported_types():
                self.checkers[check_type] = checker
    
    def register_checker(self, check_type: CheckType, checker: BaseHealthChecker) -> None:
        """Register a health checker."""
        self.checkers[check_type] = checker
        self.logger.info(f"Registered health checker for type: {check_type.value}")
    
    def register_check(self, check: HealthCheck) -> None:
        """Register a health check."""
        with self._lock:
            self.checks[check.name] = check
            self.logger.info(f"Registered health check: {check.name}")
    
    def unregister_check(self, check_name: str) -> bool:
        """Unregister a health check."""
        with self._lock:
            if check_name in self.checks:
                del self.checks[check_name]
                self.logger.info(f"Unregistered health check: {check_name}")
                return True
            return False
    
    def start_monitoring(self) -> None:
        """Start health monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        self.logger.info("Health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Health monitoring stopped")
    
    def run_check(self, check_name: str) -> Optional[HealthCheckResult]:
        """Run a specific health check."""
        check = self.checks.get(check_name)
        if not check:
            raise IntegrationError(f"Health check '{check_name}' not found")
        
        if not check.enabled:
            return None
        
        checker = self.checkers.get(check.check_type)
        if not checker:
            raise IntegrationError(f"No checker found for type: {check.check_type.value}")
        
        try:
            result = checker.check(check)
            
            # Update component health
            self._update_component_health(check, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error running health check {check_name}: {e}")
            
            error_result = HealthCheckResult(
                check_name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                error=str(e)
            )
            
            self._update_component_health(check, error_result)
            return error_result
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all enabled health checks."""
        results = {}
        
        for check_name, check in self.checks.items():
            if check.enabled:
                result = self.run_check(check_name)
                if result:
                    results[check_name] = result
        
        return results
    
    def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        with self._lock:
            # Determine overall status
            if not self.components:
                overall_status = HealthStatus.UNKNOWN
            elif all(c.status == HealthStatus.HEALTHY for c in self.components.values()):
                overall_status = HealthStatus.HEALTHY
            elif any(c.status == HealthStatus.UNHEALTHY for c in self.components.values()):
                overall_status = HealthStatus.UNHEALTHY
            else:
                overall_status = HealthStatus.DEGRADED
            
            system_health = SystemHealth(
                status=overall_status,
                components=self.components.copy()
            )
            
            # Add summary statistics
            system_health.summary = {
                "healthy_components": system_health.healthy_components,
                "total_components": system_health.total_components,
                "health_percentage": system_health.health_percentage,
                "total_checks": sum(c.total_checks for c in self.components.values()),
                "failed_checks": sum(c.failed_checks for c in self.components.values())
            }
            
            return system_health
    
    def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """Get health of a specific component."""
        with self._lock:
            return self.components.get(component_name)
    
    def get_check_status(self, check_name: str) -> Dict[str, Any]:
        """Get status of a specific check."""
        check = self.checks.get(check_name)
        if not check:
            raise IntegrationError(f"Health check '{check_name}' not found")
        
        # Find component that contains this check
        component = None
        for comp in self.components.values():
            for check_result in comp.checks:
                if check_result.check_name == check_name:
                    component = comp
                    break
            if component:
                break
        
        return {
            "check": check.to_dict(),
            "component_name": component.component_name if component else None,
            "last_result": next((c.to_dict() for c in component.checks if c.check_name == check_name), None) if component else None
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        system_health = self.get_system_health()
        
        return {
            "overall_status": system_health.status.value,
            "health_percentage": system_health.health_percentage,
            "healthy_components": system_health.healthy_components,
            "total_components": system_health.total_components,
            "total_checks": len(self.checks),
            "enabled_checks": len([c for c in self.checks.values() if c.enabled]),
            "timestamp": system_health.timestamp.isoformat()
        }
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                start_time = time.time()
                
                # Run all checks
                self.run_all_checks()
                
                # Calculate monitoring time
                monitoring_time = time.time() - start_time
                
                # Sleep until next check interval
                min_interval = min((check.interval for check in self.checks.values() if check.enabled), default=60.0)
                sleep_time = max(0, min_interval - monitoring_time)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)
    
    def _update_component_health(self, check: HealthCheck, result: HealthCheckResult) -> None:
        """Update component health based on check result."""
        with self._lock:
            # Determine component name (use check tags or check name)
            component_name = check.tags[0] if check.tags else check.name.split('_')[0]
            
            if component_name not in self.components:
                self.components[component_name] = ComponentHealth(
                    component_name=component_name,
                    status=HealthStatus.UNKNOWN
                )
            
            component = self.components[component_name]
            
            # Update component's check results
            # Remove old result for this check if exists
            component.checks = [c for c in component.checks if c.check_name != check.name]
            component.checks.append(result)
            component.last_check = result.timestamp
            
            # Update statistics
            component.total_checks += 1
            if not result.is_healthy:
                component.failed_checks += 1
            
            # Determine component status based on latest checks
            if component.checks:
                latest_checks = component.checks[-5:]  # Last 5 checks
                if all(c.is_healthy for c in latest_checks):
                    component.status = HealthStatus.HEALTHY
                elif any(c.status == HealthStatus.UNHEALTHY for c in latest_checks):
                    component.status = HealthStatus.UNHEALTHY
                else:
                    component.status = HealthStatus.DEGRADED
            
            # Update component metrics
            component.metrics = {
                "last_check_duration": result.duration,
                "total_checks": component.total_checks,
                "failed_checks": component.failed_checks,
                "success_rate": component.success_rate
            }


# Global health manager instance
health_manager = HealthManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_health_check(
    name: str,
    check_type: CheckType,
    description: str = "",
    **kwargs: Any
) -> HealthCheck:
    """Create a health check."""
    check = HealthCheck(
        name=name,
        check_type=check_type,
        description=description,
        **kwargs
    )
    
    health_manager.register_check(check)
    return check


def run_health_check(check_name: str) -> Optional[HealthCheckResult]:
    """Run a specific health check."""
    return health_manager.run_check(check_name)


def get_system_health() -> SystemHealth:
    """Get overall system health."""
    return health_manager.get_system_health()


# Initialize logging
logger.info("Health check system module initialized")
