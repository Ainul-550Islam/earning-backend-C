"""
🔍 Backup System Monitoring Module

This module provides comprehensive monitoring capabilities for the backup system.
It includes health checks, performance monitoring, alerting, and system status
tracking to ensure the backup system operates optimally.

Features:
- System health monitoring
- Performance metrics collection
- Alert management and notifications
- Resource usage monitoring
- Backup operation monitoring
- Storage monitoring
- Database connectivity checks
- Service availability monitoring
"""
from django.db import models

import logging
import time
import datetime
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.core.management import call_command
from django.db.models import Q

# Import backup models and services
from .models import Backup, BackupStorageLocation, BackupSchedule, BackupAlert
from .services.factory import get_backup_service_factory
from .utils import TimeUtils, FileUtils

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Enumeration of health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MonitorType(Enum):
    """Enumeration of monitor types."""
    SYSTEM = "system"
    DATABASE = "database"
    STORAGE = "storage"
    BACKUP = "backup"
    SCHEDULE = "schedule"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    SERVICE = "service"


class AlertSeverity(Enum):
    """Enumeration of alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime.datetime = field(default_factory=timezone.now)
    duration_ms: Optional[float] = None
    error: Optional[Exception] = None


@dataclass
class MetricData:
    """Metric data point."""
    name: str
    value: Union[int, float, str]
    unit: Optional[str] = None
    timestamp: datetime.datetime = field(default_factory=timezone.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemAlert:
    """System alert definition."""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    component: str
    timestamp: datetime.datetime = field(default_factory=timezone.now)
    resolved: bool = False
    resolved_at: Optional[datetime.datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Base class for health checkers."""
    
    def __init__(self, name: str):
        self.name = name
        self.last_check = None
        self.check_history = deque(maxlen=100)  # Keep last 100 checks
    
    def check(self) -> HealthCheckResult:
        """Perform health check."""
        start_time = time.time()
        try:
            result = self._perform_check()
            result.duration_ms = (time.time() - start_time) * 1000
            self.check_history.append(result)
            self.last_check = result
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"Health check failed: {str(e)}",
                error=e,
                duration_ms=duration_ms
            )
            self.check_history.append(result)
            self.last_check = result
            return result
    
    def _perform_check(self) -> HealthCheckResult:
        """Override this method to implement specific health check logic."""
        raise NotImplementedError("Subclasses must implement _perform_check method")


class DatabaseHealthChecker(HealthChecker):
    """Health checker for database connectivity."""
    
    def __init__(self):
        super().__init__("database")
    
    def _perform_check(self) -> HealthCheckResult:
        """Check database connectivity and performance."""
        try:
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Check connection pool
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables")
                cursor.fetchone()
            query_time = (time.time() - start_time) * 1000
            
            # Check database size (if available)
            db_size = 0
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT SUM(data_length + index_length) 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE()
                    """)
                    result = cursor.fetchone()
                    db_size = result[0] if result and result[0] else 0
            except Exception:
                pass  # Database size query not supported
            
            status = HealthStatus.HEALTHY
            message = "Database is healthy"
            
            if query_time > 1000:  # 1 second threshold
                status = HealthStatus.WARNING
                message = f"Database query slow: {query_time:.2f}ms"
            elif query_time > 5000:  # 5 second threshold
                status = HealthStatus.CRITICAL
                message = f"Database query very slow: {query_time:.2f}ms"
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={
                    "query_time_ms": query_time,
                    "database_size_bytes": db_size,
                    "connection_pool_size": getattr(settings, 'DATABASES', {}).get('default', {}).get('CONN_MAX_AGE', 0)
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                error=e
            )


class StorageHealthChecker(HealthChecker):
    """Health checker for storage systems."""
    
    def __init__(self):
        super().__init__("storage")
    
    def _perform_check(self) -> HealthCheckResult:
        """Check storage system health."""
        try:
            factory = get_backup_service_factory()
            storage_locations = BackupStorageLocation.objects.filter(is_active=True)
            
            total_locations = storage_locations.count()
            healthy_locations = 0
            failed_locations = []
            storage_details = {}
            
            for location in storage_locations:
                try:
                    # Test storage connectivity based on type
                    if location.storage_type == 'local':
                        # Check local directory
                        import os
                        if os.path.exists(location.backup_path or '/tmp'):
                            healthy_locations += 1
                            storage_details[location.storage_type] = storage_details.get(location.storage_type, 0) + 1
                        else:
                            failed_locations.append(location.storage_type)
                    
                    elif location.storage_type == 's3':
                        # Check S3 connectivity
                        try:
                            s3_service = factory.get_storage_service('s3')
                            # Test with a simple operation
                            s3_service.list_backups()
                            healthy_locations += 1
                            storage_details[location.storage_type] = storage_details.get(location.storage_type, 0) + 1
                        except Exception:
                            failed_locations.append(location.storage_type)
                    
                    else:
                        # For other storage types, assume healthy for now
                        healthy_locations += 1
                        storage_details[location.storage_type] = storage_details.get(location.storage_type, 0) + 1
                
                except Exception as e:
                    failed_locations.append(location.storage_type)
                    logger.error(f"Storage health check failed for {location.storage_type}: {e}")
            
            # Determine overall status
            if total_locations == 0:
                status = HealthStatus.WARNING
                message = "No active storage locations configured"
            elif healthy_locations == total_locations:
                status = HealthStatus.HEALTHY
                message = "All storage systems are healthy"
            elif healthy_locations > 0:
                status = HealthStatus.WARNING
                message = f"Some storage systems failed: {', '.join(failed_locations)}"
            else:
                status = HealthStatus.CRITICAL
                message = "All storage systems failed"
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={
                    "total_locations": total_locations,
                    "healthy_locations": healthy_locations,
                    "failed_locations": failed_locations,
                    "storage_details": storage_details
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"Storage health check failed: {str(e)}",
                error=e
            )


class SystemResourceHealthChecker(HealthChecker):
    """Health checker for system resources."""
    
    def __init__(self):
        super().__init__("system_resources")
    
    def _perform_check(self) -> HealthCheckResult:
        """Check system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Load average (Unix systems)
            load_avg = None
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                pass  # Not available on Windows
            
            # Determine status based on thresholds
            status = HealthStatus.HEALTHY
            issues = []
            
            if cpu_percent > 90:
                status = HealthStatus.CRITICAL
                issues.append(f"High CPU usage: {cpu_percent}%")
            elif cpu_percent > 75:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated CPU usage: {cpu_percent}%")
            
            if memory_percent > 90:
                status = HealthStatus.CRITICAL
                issues.append(f"High memory usage: {memory_percent}%")
            elif memory_percent > 80:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated memory usage: {memory_percent}%")
            
            if disk_percent > 95:
                status = HealthStatus.CRITICAL
                issues.append(f"High disk usage: {disk_percent}%")
            elif disk_percent > 85:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated disk usage: {disk_percent}%")
            
            message = "System resources are healthy"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "memory_total_gb": memory.total / (1024**3),
                    "memory_used_gb": memory.used / (1024**3),
                    "disk_percent": disk_percent,
                    "disk_total_gb": disk.total / (1024**3),
                    "disk_used_gb": disk.used / (1024**3),
                    "load_average": load_avg
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"System resource check failed: {str(e)}",
                error=e
            )


class BackupOperationHealthChecker(HealthChecker):
    """Health checker for backup operations."""
    
    def __init__(self):
        super().__init__("backup_operations")
    
    def _perform_check(self) -> HealthCheckResult:
        """Check backup operation health."""
        try:
            now = timezone.now()
            
            # Check recent backup success rate
            recent_backups = Backup.objects.filter(
                created_at__gte=now - datetime.timedelta(hours=24)
            )
            
            total_backups = recent_backups.count()
            successful_backups = recent_backups.filter(status='completed').count()
            failed_backups = recent_backups.filter(status='failed').count()
            
            # Check for stuck backups
            stuck_backups = Backup.objects.filter(
                status='running',
                created_at__lt=now - datetime.timedelta(hours=4)
            ).count()
            
            # Check recent backup performance
            recent_completed = recent_backups.filter(
                status='completed'
            ).exclude(duration__isnull=True)
            
            avg_duration = 0
            if recent_completed.exists():
                avg_duration = recent_completed.aggregate(
                    avg_duration=models.Avg('duration')
                )['avg_duration'] or 0
            
            # Determine status
            status = HealthStatus.HEALTHY
            issues = []
            
            if total_backups > 0:
                success_rate = (successful_backups / total_backups) * 100
                
                if success_rate < 80:
                    status = HealthStatus.CRITICAL
                    issues.append(f"Low backup success rate: {success_rate:.1f}%")
                elif success_rate < 95:
                    if status == HealthStatus.HEALTHY:
                        status = HealthStatus.WARNING
                    issues.append(f"Backup success rate below optimal: {success_rate:.1f}%")
            
            if stuck_backups > 0:
                status = HealthStatus.CRITICAL
                issues.append(f"{stuck_backups} stuck backup operations")
            
            if avg_duration > 3600:  # 1 hour
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Slow backup operations: {TimeUtils.format_duration(avg_duration)}")
            
            message = "Backup operations are healthy"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={
                    "total_backups_24h": total_backups,
                    "successful_backups_24h": successful_backups,
                    "failed_backups_24h": failed_backups,
                    "stuck_backups": stuck_backups,
                    "average_duration_seconds": avg_duration,
                    "success_rate_percent": (successful_backups / total_backups * 100) if total_backups > 0 else 0
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"Backup operation check failed: {str(e)}",
                error=e
            )


class ScheduleHealthChecker(HealthChecker):
    """Health checker for backup schedules."""
    
    def __init__(self):
        super().__init__("backup_schedules")
    
    def _perform_check(self) -> HealthCheckResult:
        """Check backup schedule health."""
        try:
            now = timezone.now()
            
            # Check active schedules
            active_schedules = BackupSchedule.objects.filter(is_active=True)
            
            # Check for missed schedules
            missed_schedules = 0
            overdue_schedules = 0
            
            for schedule in active_schedules:
                if schedule.next_run and schedule.next_run < now:
                    # Check if backup was created after the scheduled time
                    backup_exists = Backup.objects.filter(
                        backup_schedule=schedule,
                        created_at__gte=schedule.next_run
                    ).exists()
                    
                    if not backup_exists:
                        if schedule.next_run < now - datetime.timedelta(hours=2):
                            missed_schedules += 1
                        else:
                            overdue_schedules += 1
            
            # Check schedule success rates
            schedules_with_issues = 0
            for schedule in active_schedules:
                recent_backups = Backup.objects.filter(
                    backup_schedule=schedule,
                    created_at__gte=now - datetime.timedelta(days=7)
                )
                
                if recent_backups.exists():
                    success_rate = recent_backups.filter(status='completed').count() / recent_backups.count()
                    if success_rate < 0.8:  # 80% threshold
                        schedules_with_issues += 1
            
            # Determine status
            status = HealthStatus.HEALTHY
            issues = []
            
            if missed_schedules > 0:
                status = HealthStatus.CRITICAL
                issues.append(f"{missed_schedules} missed schedules")
            elif overdue_schedules > 0:
                status = HealthStatus.WARNING
                issues.append(f"{overdue_schedules} overdue schedules")
            
            if schedules_with_issues > 0:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"{schedules_with_issues} schedules with low success rate")
            
            message = "Backup schedules are healthy"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                message=message,
                details={
                    "active_schedules": active_schedules.count(),
                    "missed_schedules": missed_schedules,
                    "overdue_schedules": overdue_schedules,
                    "schedules_with_issues": schedules_with_issues
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                message=f"Schedule health check failed: {str(e)}",
                error=e
            )


class MetricsCollector:
    """Collects and manages system metrics."""
    
    def __init__(self):
        self.metrics = defaultdict(deque)
        self.max_metrics_per_type = 1000  # Keep last 1000 data points per metric
    
    def collect_metric(self, name: str, value: Union[int, float, str], 
                      unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> None:
        """Collect a metric data point."""
        metric = MetricData(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        self.metrics[name].append(metric)
        
        # Keep only the most recent metrics
        if len(self.metrics[name]) > self.max_metrics_per_type:
            self.metrics[name].popleft()
    
    def get_metrics(self, name: str, limit: Optional[int] = None) -> List[MetricData]:
        """Get metrics for a specific name."""
        metrics = list(self.metrics[name])
        if limit:
            return metrics[-limit:]
        return metrics
    
    def get_latest_metric(self, name: str) -> Optional[MetricData]:
        """Get the latest metric for a specific name."""
        if self.metrics[name]:
            return self.metrics[name][-1]
        return None
    
    def get_all_metric_names(self) -> List[str]:
        """Get all available metric names."""
        return list(self.metrics.keys())


class AlertManager:
    """Manages system alerts."""
    
    def __init__(self):
        self.active_alerts = {}
        self.alert_history = deque(maxlen=1000)
        self.alert_callbacks = []
    
    def add_alert_callback(self, callback: Callable[[SystemAlert], None]) -> None:
        """Add a callback to be called when alerts are created."""
        self.alert_callbacks.append(callback)
    
    def create_alert(self, title: str, message: str, severity: AlertSeverity,
                    component: str, metadata: Optional[Dict[str, Any]] = None) -> SystemAlert:
        """Create a new alert."""
        alert = SystemAlert(
            alert_id=f"alert_{int(time.time())}_{component}",
            title=title,
            message=message,
            severity=severity,
            component=component,
            metadata=metadata or {}
        )
        
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        # Store in database
        try:
            BackupAlert.objects.create(
                alert_type=component,
                message=message,
                severity=severity.value,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Failed to store alert in database: {e}")
        
        # Call callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
        
        logger.warning(f"Alert created: {title} - {message}")
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = timezone.now()
            
            # Update database
            try:
                db_alert = BackupAlert.objects.filter(
                    alert_type=alert.component,
                    message=alert.message,
                    is_resolved=False
                ).first()
                if db_alert:
                    db_alert.is_resolved = True
                    db_alert.resolved_at = alert.resolved_at
                    db_alert.save()
            except Exception as e:
                logger.error(f"Failed to update alert in database: {e}")
            
            del self.active_alerts[alert_id]
            logger.info(f"Alert resolved: {alert.title}")
            return True
        
        return False
    
    def get_active_alerts(self, component: Optional[str] = None,
                         severity: Optional[AlertSeverity] = None) -> List[SystemAlert]:
        """Get active alerts with optional filtering."""
        alerts = list(self.active_alerts.values())
        
        if component:
            alerts = [a for a in alerts if a.component == component]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts
    
    def get_alert_count(self, severity: Optional[AlertSeverity] = None) -> int:
        """Get count of active alerts."""
        alerts = self.get_active_alerts(severity=severity)
        return len(alerts)


class BackupSystemMonitor:
    """Main backup system monitor."""
    
    def __init__(self):
        self.health_checkers = {
            'database': DatabaseHealthChecker(),
            'storage': StorageHealthChecker(),
            'system_resources': SystemResourceHealthChecker(),
            'backup_operations': BackupOperationHealthChecker(),
            'backup_schedules': ScheduleHealthChecker(),
        }
        
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.monitoring_enabled = True
        self.check_interval = getattr(settings, 'BACKUP_MONITOR_CHECK_INTERVAL', 60)  # seconds
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()
        
        # Set up default alert callback
        self.alert_manager.add_alert_callback(self._handle_alert)
    
    def _handle_alert(self, alert: SystemAlert) -> None:
        """Handle new alerts (default callback)."""
        # Log the alert
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.WARNING)
        
        logger.log(log_level, f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}")
        
        # Store metrics about alerts
        self.metrics_collector.collect_metric(
            f"alerts_{alert.severity.value}",
            1,
            unit="count",
            tags={"component": alert.component}
        )
    
    def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitoring is already running")
            return
        
        self.monitoring_enabled = True
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Backup system monitoring started")
    
    def stop_monitoring_service(self) -> None:
        """Stop background monitoring."""
        self.monitoring_enabled = False
        self.stop_monitoring.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Backup system monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self.stop_monitoring.wait(self.check_interval):
            if not self.monitoring_enabled:
                continue
            
            try:
                self._perform_health_checks()
                self._collect_system_metrics()
                self._check_alert_conditions()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    def _perform_health_checks(self) -> None:
        """Perform all health checks."""
        for name, checker in self.health_checkers.items():
            try:
                result = checker.check()
                
                # Store health check metrics
                self.metrics_collector.collect_metric(
                    f"health_check_{name}",
                    1 if result.status == HealthStatus.HEALTHY else 0,
                    unit="status",
                    tags={"status": result.status.value},
                    metadata={"message": result.message, "duration_ms": result.duration_ms}
                )
                
                # Create alerts for critical issues
                if result.status == HealthStatus.CRITICAL:
                    self.alert_manager.create_alert(
                        title=f"Critical: {name} health check failed",
                        message=result.message,
                        severity=AlertSeverity.CRITICAL,
                        component=name,
                        metadata={"error": str(result.error) if result.error else None}
                    )
                elif result.status == HealthStatus.WARNING:
                    self.alert_manager.create_alert(
                        title=f"Warning: {name} health check issue",
                        message=result.message,
                        severity=AlertSeverity.MEDIUM,
                        component=name,
                        metadata={"details": result.details}
                    )
                
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                self.alert_manager.create_alert(
                    title=f"Health check error: {name}",
                    message=f"Health check failed: {str(e)}",
                    severity=AlertSeverity.HIGH,
                    component=name,
                    metadata={"error": str(e)}
                )
    
    def _collect_system_metrics(self) -> None:
        """Collect system metrics."""
        try:
            # System resource metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            self.metrics_collector.collect_metric("system_cpu_percent", cpu_percent, unit="%")
            self.metrics_collector.collect_metric("system_memory_percent", memory.percent, unit="%")
            self.metrics_collector.collect_metric("system_disk_percent", disk.percent, unit="%")
            self.metrics_collector.collect_metric("system_memory_used_gb", memory.used / (1024**3), unit="GB")
            self.metrics_collector.collect_metric("system_disk_used_gb", disk.used / (1024**3), unit="GB")
            
            # Backup metrics
            now = timezone.now()
            recent_backups = Backup.objects.filter(
                created_at__gte=now - datetime.timedelta(hours=24)
            )
            
            self.metrics_collector.collect_metric(
                "backups_total_24h",
                recent_backups.count(),
                unit="count"
            )
            
            self.metrics_collector.collect_metric(
                "backups_successful_24h",
                recent_backups.filter(status='completed').count(),
                unit="count"
            )
            
            self.metrics_collector.collect_metric(
                "backups_failed_24h",
                recent_backups.filter(status='failed').count(),
                unit="count"
            )
            
            # Storage metrics
            storage_locations = BackupStorageLocation.objects.filter(is_active=True)
            self.metrics_collector.collect_metric(
                "storage_locations_active",
                storage_locations.count(),
                unit="count"
            )
            
            total_storage = sum(loc.total_space or 0 for loc in storage_locations)
            used_storage = sum(loc.used_space or 0 for loc in storage_locations)
            
            if total_storage > 0:
                utilization = (used_storage / total_storage) * 100
                self.metrics_collector.collect_metric("storage_utilization_percent", utilization, unit="%")
            
            # Schedule metrics
            active_schedules = BackupSchedule.objects.filter(is_active=True)
            self.metrics_collector.collect_metric(
                "schedules_active",
                active_schedules.count(),
                unit="count"
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def _check_alert_conditions(self) -> None:
        """Check for alert conditions based on metrics."""
        try:
            # Check for high CPU usage
            cpu_metric = self.metrics_collector.get_latest_metric("system_cpu_percent")
            if cpu_metric and cpu_metric.value > 90:
                self.alert_manager.create_alert(
                    title="High CPU usage detected",
                    message=f"CPU usage is {cpu_metric.value}%",
                    severity=AlertSeverity.HIGH,
                    component="system_resources",
                    metadata={"cpu_percent": cpu_metric.value}
                )
            
            # Check for high memory usage
            memory_metric = self.metrics_collector.get_latest_metric("system_memory_percent")
            if memory_metric and memory_metric.value > 90:
                self.alert_manager.create_alert(
                    title="High memory usage detected",
                    message=f"Memory usage is {memory_metric.value}%",
                    severity=AlertSeverity.HIGH,
                    component="system_resources",
                    metadata={"memory_percent": memory_metric.value}
                )
            
            # Check for high disk usage
            disk_metric = self.metrics_collector.get_latest_metric("system_disk_percent")
            if disk_metric and disk_metric.value > 95:
                self.alert_manager.create_alert(
                    title="High disk usage detected",
                    message=f"Disk usage is {disk_metric.value}%",
                    severity=AlertSeverity.CRITICAL,
                    component="system_resources",
                    metadata={"disk_percent": disk_metric.value}
                )
            
            # Check for backup failures
            failed_backups = self.metrics_collector.get_latest_metric("backups_failed_24h")
            if failed_backups and failed_backups.value > 0:
                total_backups = self.metrics_collector.get_latest_metric("backups_total_24h")
                if total_backups and total_backups.value > 0:
                    failure_rate = (failed_backups.value / total_backups.value) * 100
                    if failure_rate > 20:  # 20% failure rate threshold
                        self.alert_manager.create_alert(
                            title="High backup failure rate",
                            message=f"Backup failure rate is {failure_rate:.1f}%",
                            severity=AlertSeverity.HIGH,
                            component="backup_operations",
                            metadata={"failure_rate": failure_rate, "failed_count": failed_backups.value}
                        )
            
        except Exception as e:
            logger.error(f"Failed to check alert conditions: {e}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_results = {}
        overall_status = HealthStatus.HEALTHY
        
        for name, checker in self.health_checkers.items():
            result = checker.last_check
            if result:
                health_results[name] = {
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "details": result.details
                }
                
                # Determine overall status
                if result.status == HealthStatus.CRITICAL:
                    overall_status = HealthStatus.CRITICAL
                elif result.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.WARNING
            else:
                health_results[name] = {
                    "status": HealthStatus.UNKNOWN.value,
                    "message": "No health check data available",
                    "timestamp": None,
                    "duration_ms": None,
                    "details": {}
                }
                overall_status = HealthStatus.WARNING
        
        return {
            "overall_status": overall_status.value,
            "timestamp": timezone.now().isoformat(),
            "components": health_results,
            "active_alerts_count": self.alert_manager.get_alert_count(),
            "monitoring_enabled": self.monitoring_enabled
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        summary = {}
        
        for metric_name in self.metrics_collector.get_all_metric_names():
            latest = self.metrics_collector.get_latest_metric(metric_name)
            if latest:
                summary[metric_name] = {
                    "latest_value": latest.value,
                    "unit": latest.unit,
                    "timestamp": latest.timestamp.isoformat(),
                    "tags": latest.tags
                }
        
        return summary
    
    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary of active alerts."""
        alerts = self.alert_manager.get_active_alerts()
        
        summary = {
            "total_alerts": len(alerts),
            "by_severity": {},
            "by_component": {},
            "recent_alerts": []
        }
        
        for alert in alerts:
            # Count by severity
            severity = alert.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # Count by component
            component = alert.component
            summary["by_component"][component] = summary["by_component"].get(component, 0) + 1
            
            # Add to recent alerts (last 10)
            if len(summary["recent_alerts"]) < 10:
                summary["recent_alerts"].append({
                    "alert_id": alert.alert_id,
                    "title": alert.title,
                    "severity": alert.severity.value,
                    "component": alert.component,
                    "timestamp": alert.timestamp.isoformat(),
                    "message": alert.message
                })
        
        return summary


# Global monitor instance
_monitor_instance: Optional[BackupSystemMonitor] = None


def get_backup_monitor() -> BackupSystemMonitor:
    """Get the global backup monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = BackupSystemMonitor()
    return _monitor_instance


def start_monitoring() -> None:
    """Start backup system monitoring."""
    monitor = get_backup_monitor()
    monitor.start_monitoring()


def stop_monitoring() -> None:
    """Stop backup system monitoring."""
    monitor = get_backup_monitor()
    monitor.stop_monitoring_service()


def get_system_health() -> Dict[str, Any]:
    """Get system health status."""
    monitor = get_backup_monitor()
    return monitor.get_system_health()


def get_metrics_summary() -> Dict[str, Any]:
    """Get metrics summary."""
    monitor = get_backup_monitor()
    return monitor.get_metrics_summary()


def get_alerts_summary() -> Dict[str, Any]:
    """Get alerts summary."""
    monitor = get_backup_monitor()
    return monitor.get_alerts_summary()


def create_alert(title: str, message: str, severity: AlertSeverity,
                 component: str, metadata: Optional[Dict[str, Any]] = None) -> SystemAlert:
    """Create a system alert."""
    monitor = get_backup_monitor()
    return monitor.alert_manager.create_alert(title, message, severity, component, metadata)
