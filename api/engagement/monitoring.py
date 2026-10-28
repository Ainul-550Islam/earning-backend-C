# engagement/monitoring.py
"""
Monitoring system for engagement gamification.
Provides health checks, metrics collection, and alerting.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Metric data structure."""
    name: str
    value: Union[int, float, str]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=timezone.now)
    labels: Dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    unit: str = ""


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    duration_ms: float = 0.0


class BaseMonitor(ABC):
    """Base monitor class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def collect_metrics(self) -> List[Metric]:
        """Collect metrics."""
        pass
    
    @abstractmethod
    def health_check(self) -> HealthCheck:
        """Perform health check."""
        pass


class DatabaseMonitor(BaseMonitor):
    """Database health monitor."""
    
    def __init__(self):
        super().__init__("database")
    
    def collect_metrics(self) -> List[Metric]:
        """Collect database metrics."""
        metrics = []
        
        try:
            # Get database connection metrics
            with connection.cursor() as cursor:
                # Check number of connections
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")
                active_connections = cursor.fetchone()[0]
                metrics.append(Metric(
                    name="database_active_connections",
                    value=active_connections,
                    metric_type=MetricType.GAUGE,
                    help_text="Number of active database connections"
                ))
                
                # Check slow queries
                cursor.execute("""
                    SELECT count(*) 
                    FROM pg_stat_statements 
                    WHERE mean_exec_time > 1000
                """)
                slow_queries = cursor.fetchone()[0]
                metrics.append(Metric(
                    name="database_slow_queries",
                    value=slow_queries,
                    metric_type=MetricType.COUNTER,
                    help_text="Number of slow queries (>1s)"
                ))
                
                # Get table sizes
                cursor.execute("""
                    SELECT schemaname, tablename, 
                           pg_size_pretty(schemaname||'.'||tablename) AS size
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)
                table_sizes = cursor.fetchall()
                
                for schema, table, size in table_sizes:
                    metrics.append(Metric(
                        name="database_table_size",
                        value=size,
                        metric_type=MetricType.GAUGE,
                        labels={"table": f"{schema}.{table}"},
                        help_text=f"Size of {schema}.{table}"
                    ))
        
        except Exception as exc:
            self.logger.error(f"Failed to collect database metrics: {exc}")
            metrics.append(Metric(
                name="database_error",
                value=1,
                metric_type=MetricType.COUNTER,
                help_text="Database metric collection error"
            ))
        
        return metrics
    
    def health_check(self) -> HealthCheck:
        """Perform database health check."""
        start_time = time.time()
        
        try:
            with connection.cursor() as cursor:
                # Simple connectivity test
                cursor.execute("SELECT 1")
                
                # Check connection count
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")
                connections = cursor.fetchone()[0]
                
                max_connections = getattr(settings, 'DATABASES', {}).get('default', {}).get('OPTIONS', {}).get('MAX_CONNS', 100)
                
                if connections > max_connections * 0.8:
                    status = "degraded"
                    message = f"High database connection usage: {connections}/{max_connections}"
                else:
                    status = "healthy"
                    message = f"Database connections normal: {connections}/{max_connections}"
                
                # Check slow query count
                cursor.execute("""
                    SELECT count(*) 
                    FROM pg_stat_statements 
                    WHERE mean_exec_time > 1000
                """)
                slow_queries = cursor.fetchone()[0]
                
                details = {
                    "active_connections": connections,
                    "max_connections": max_connections,
                    "slow_queries": slow_queries,
                    "connection_utilization": connections / max_connections
                }
                
                duration_ms = (time.time() - start_time) * 1000
                
                return HealthCheck(
                    name=self.name,
                    status=status,
                    message=message,
                    details=details,
                    duration_ms=duration_ms
                )
                
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Database health check failed: {exc}")
            
            return HealthCheck(
                name=self.name,
                status="unhealthy",
                message=f"Database connection failed: {str(exc)}",
                details={"error": str(exc)},
                duration_ms=duration_ms
            )


class CacheMonitor(BaseMonitor):
    """Cache health monitor."""
    
    def __init__(self):
        super().__init__("cache")
    
    def collect_metrics(self) -> List[Metric]:
        """Collect cache metrics."""
        metrics = []
        
        try:
            # Test cache performance
            start_time = time.time()
            cache.set("health_check_test", "test_value", timeout=1)
            cache_get_time = time.time() - start_time
            
            cache.delete("health_check_test")
            
            metrics.append(Metric(
                name="cache_get_time_seconds",
                value=cache_get_time,
                metric_type=MetricType.TIMER,
                help_text="Cache get operation time"
            ))
            
            # Get cache info if Redis is used
            try:
                cache_info = cache._cache.get_info()
                if cache_info:
                    metrics.append(Metric(
                        name="cache_memory_usage_bytes",
                        value=cache_info.get('used_memory', 0),
                        metric_type=MetricType.GAUGE,
                        help_text="Cache memory usage in bytes"
                    ))
                    
                    metrics.append(Metric(
                        name="cache_connected_clients",
                        value=cache_info.get('connected_clients', 0),
                        metric_type=MetricType.GAUGE,
                        help_text="Number of connected cache clients"
                    ))
            except:
                pass  # Cache backend doesn't support get_info
            
        except Exception as exc:
            self.logger.error(f"Failed to collect cache metrics: {exc}")
            metrics.append(Metric(
                name="cache_error",
                value=1,
                metric_type=MetricType.COUNTER,
                help_text="Cache metric collection error"
            ))
        
        return metrics
    
    def health_check(self) -> HealthCheck:
        """Perform cache health check."""
        start_time = time.time()
        
        try:
            # Test cache operations
            test_key = f"health_check_{int(time.time())}"
            test_value = f"test_value_{timezone.now().isoformat()}"
            
            # Test set
            cache.set(test_key, test_value, timeout=1)
            
            # Test get
            retrieved_value = cache.get(test_key)
            
            if retrieved_value != test_value:
                raise ValueError("Cache get/set mismatch")
            
            # Test delete
            cache.delete(test_key)
            
            # Verify deletion
            if cache.get(test_key) is not None:
                raise ValueError("Cache deletion failed")
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name=self.name,
                status="healthy",
                message="Cache operations working correctly",
                details={
                    "test_completed": True,
                    "cache_backend": cache._cache.__class__.__name__
                },
                duration_ms=duration_ms
            )
            
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Cache health check failed: {exc}")
            
            return HealthCheck(
                name=self.name,
                status="unhealthy",
                message=f"Cache operations failed: {str(exc)}",
                details={"error": str(exc)},
                duration_ms=duration_ms
            )


class EngagementMonitor(BaseMonitor):
    """Engagement system monitor."""
    
    def __init__(self):
        super().__init__("engagement")
    
    def collect_metrics(self) -> List[Metric]:
        """Collect engagement metrics."""
        metrics = []
        
        try:
            from .models.checkin import DailyCheckIn
            from .models.spinwheel import SpinWheel
            from .models.quest import UserQuest
            from .models.achievement import UserAchievement
            
            # Daily check-ins today
            today = timezone.now().date()
            checkins_today = DailyCheckIn.objects.filter(date=today).count()
            metrics.append(Metric(
                name="daily_checkins_today",
                value=checkins_today,
                metric_type=MetricType.COUNTER,
                help_text="Number of check-ins today"
            ))
            
            # Spins today
            spins_today = SpinWheel.objects.filter(spun_at__date=today).count()
            metrics.append(Metric(
                name="daily_spins_today",
                value=spins_today,
                metric_type=MetricType.COUNTER,
                help_text="Number of spins today"
            ))
            
            # Active users today
            active_users_today = DailyCheckIn.objects.filter(date=today).values('user').distinct().count()
            metrics.append(Metric(
                name="daily_active_users",
                value=active_users_today,
                metric_type=MetricType.COUNTER,
                help_text="Number of active users today"
            ))
            
            # Total achievements unlocked
            total_achievements = UserAchievement.objects.filter(unlocked_at__isnull=False).count()
            metrics.append(Metric(
                name="total_achievements_unlocked",
                value=total_achievements,
                metric_type=MetricType.COUNTER,
                help_text="Total number of achievements unlocked"
            ))
            
            # Quest completion rate
            total_quests = UserQuest.objects.count()
            completed_quests = UserQuest.objects.filter(status='completed').count()
            completion_rate = (completed_quests / total_quests * 100) if total_quests > 0 else 0
            metrics.append(Metric(
                name="quest_completion_rate",
                value=completion_rate,
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="Quest completion rate percentage"
            ))
            
            # Error rates
            error_metrics = self._get_error_metrics()
            metrics.extend(error_metrics)
            
        except Exception as exc:
            self.logger.error(f"Failed to collect engagement metrics: {exc}")
            metrics.append(Metric(
                name="engagement_error",
                value=1,
                metric_type=MetricType.COUNTER,
                help_text="Engagement metric collection error"
            ))
        
        return metrics
    
    def health_check(self) -> HealthCheck:
        """Perform engagement system health check."""
        start_time = time.time()
        
        try:
            # Check database connectivity
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Check cache connectivity
            cache.set("health_check", "ok", timeout=1)
            cache.delete("health_check")
            
            # Check model accessibility
            from .models.checkin import DailyCheckIn
            DailyCheckIn.objects.count()
            
            # Check recent activity
            today = timezone.now().date()
            checkins_today = DailyCheckIn.objects.filter(date=today).count()
            
            # Determine health status
            if checkins_today == 0:
                status = "degraded"
                message = "No engagement activity today"
            else:
                status = "healthy"
                message = f"Engagement system working normally ({checkins_today} check-ins today)"
            
            details = {
                "checkins_today": checkins_today,
                "database_connected": True,
                "cache_connected": True,
                "models_accessible": True
            }
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name=self.name,
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms
            )
            
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Engagement health check failed: {exc}")
            
            return HealthCheck(
                name=self.name,
                status="unhealthy",
                message=f"Engagement system health check failed: {str(exc)}",
                details={"error": str(exc)},
                duration_ms=duration_ms
            )
    
    def _get_error_metrics(self) -> List[Metric]:
        """Get error-related metrics."""
        metrics = []
        
        try:
            # This would integrate with your error tracking system
            # For now, it's a placeholder
            
            # Mock error rates
            metrics.append(Metric(
                name="checkin_error_rate",
                value=0.5,  # Mock value
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="Check-in error rate percentage"
            ))
            
            metrics.append(Metric(
                name="spin_error_rate",
                value=0.3,  # Mock value
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="Spin wheel error rate percentage"
            ))
            
            metrics.append(Metric(
                name="quest_error_rate",
                value=0.2,  # Mock value
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="Quest error rate percentage"
            ))
            
        except Exception as exc:
            self.logger.error(f"Failed to get error metrics: {exc}")
        
        return metrics


class SystemMonitor(BaseMonitor):
    """System resource monitor."""
    
    def __init__(self):
        super().__init__("system")
    
    def collect_metrics(self) -> List[Metric]:
        """Collect system metrics."""
        metrics = []
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(Metric(
                name="system_cpu_usage_percent",
                value=cpu_percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="System CPU usage percentage"
            ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics.append(Metric(
                name="system_memory_usage_percent",
                value=memory.percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="System memory usage percentage"
            ))
            
            metrics.append(Metric(
                name="system_memory_available_gb",
                value=memory.available / (1024**3),
                metric_type=MetricType.GAUGE,
                unit="GB",
                help_text="Available system memory in GB"
            ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics.append(Metric(
                name="system_disk_usage_percent",
                value=disk.percent,
                metric_type=MetricType.GAUGE,
                unit="percent",
                help_text="System disk usage percentage"
            ))
            
            # Load average
            load_avg = psutil.getloadavg()
            metrics.append(Metric(
                name="system_load_1min",
                value=load_avg[0],
                metric_type=MetricType.GAUGE,
                help_text="System load average (1 minute)"
            ))
            
            metrics.append(Metric(
                name="system_load_5min",
                value=load_avg[1],
                metric_type=MetricType.GAUGE,
                help_text="System load average (5 minutes)"
            ))
            
            metrics.append(Metric(
                name="system_load_15min",
                value=load_avg[2],
                metric_type=MetricType.GAUGE,
                help_text="System load average (15 minutes)"
            ))
            
        except ImportError:
            # psutil not available, skip system metrics
            self.logger.warning("psutil not available, skipping system metrics")
        except Exception as exc:
            self.logger.error(f"Failed to collect system metrics: {exc}")
            metrics.append(Metric(
                name="system_error",
                value=1,
                metric_type=MetricType.COUNTER,
                help_text="System metric collection error"
            ))
        
        return metrics
    
    def health_check(self) -> HealthCheck:
        """Perform system health check."""
        start_time = time.time()
        
        try:
            import psutil
            
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                cpu_status = "degraded"
                cpu_message = f"High CPU usage: {cpu_percent}%"
            else:
                cpu_status = "healthy"
                cpu_message = f"CPU usage normal: {cpu_percent}%"
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                memory_status = "degraded"
                memory_message = f"High memory usage: {memory.percent}%"
            else:
                memory_status = "healthy"
                memory_message = f"Memory usage normal: {memory.percent}%"
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                disk_status = "degraded"
                disk_message = f"High disk usage: {disk.percent}%"
            else:
                disk_status = "healthy"
                disk_message = f"Disk usage normal: {disk.percent}%"
            
            # Determine overall status
            statuses = [cpu_status, memory_status, disk_status]
            if "unhealthy" in statuses:
                overall_status = "unhealthy"
                overall_message = "System resources critically low"
            elif "degraded" in statuses:
                overall_status = "degraded"
                overall_message = "System resources elevated"
            else:
                overall_status = "healthy"
                overall_message = "System resources normal"
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "cpu_status": cpu_status,
                "memory_status": memory_status,
                "disk_status": disk_status
            }
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name=self.name,
                status=overall_status,
                message=overall_message,
                details=details,
                duration_ms=duration_ms
            )
            
        except ImportError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name=self.name,
                status="degraded",
                message="psutil not available for detailed system monitoring",
                details={"psutil_available": False},
                duration_ms=duration_ms
            )
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"System health check failed: {exc}")
            
            return HealthCheck(
                name=self.name,
                status="unhealthy",
                message=f"System health check failed: {str(exc)}",
                details={"error": str(exc)},
                duration_ms=duration_ms
            )


class MonitoringManager:
    """Manager for all monitoring operations."""
    
    def __init__(self):
        self.monitors = {
            'database': DatabaseMonitor(),
            'cache': CacheMonitor(),
            'engagement': EngagementMonitor(),
            'system': SystemMonitor(),
        }
        self.alerts = []
        self.metrics_history = []
        self.max_history_size = 1000
    
    def collect_all_metrics(self) -> Dict[str, List[Metric]]:
        """Collect metrics from all monitors."""
        all_metrics = {}
        
        for name, monitor in self.monitors.items():
            try:
                metrics = monitor.collect_metrics()
                all_metrics[name] = metrics
                
                # Store in history
                for metric in metrics:
                    self.metrics_history.append(metric)
                
                # Limit history size
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history = self.metrics_history[-self.max_history_size:]
                
            except Exception as exc:
                self.logger.error(f"Failed to collect metrics from {name}: {exc}")
                all_metrics[name] = []
        
        return all_metrics
    
    def run_health_checks(self) -> Dict[str, HealthCheck]:
        """Run health checks for all monitors."""
        health_checks = {}
        
        for name, monitor in self.monitors.items():
            try:
                health_check = monitor.health_check()
                health_checks[name] = health_check
                
                # Check for alerts
                self._check_alerts(health_check)
                
            except Exception as exc:
                self.logger.error(f"Failed to run health check for {name}: {exc}")
                health_checks[name] = HealthCheck(
                    name=name,
                    status="unhealthy",
                    message=f"Health check failed: {str(exc)}",
                    details={"error": str(exc)}
                )
        
        return health_checks
    
    def _check_alerts(self, health_check: HealthCheck):
        """Check if health check triggers any alerts."""
        if health_check.status == "unhealthy":
            self.alerts.append({
                'level': AlertLevel.ERROR,
                'message': f"Unhealthy: {health_check.name} - {health_check.message}",
                'timestamp': timezone.now(),
                'health_check': health_check
            })
        elif health_check.status == "degraded":
            self.alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"Degraded: {health_check.name} - {health_check.message}",
                'timestamp': timezone.now(),
                'health_check': health_check
            })
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary for the last N hours."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        recent_metrics = [
            metric for metric in self.metrics_history
            if metric.timestamp >= cutoff_time
        ]
        
        summary = {
            'total_metrics': len(recent_metrics),
            'metric_types': {},
            'alerts_count': len(self.alerts),
            'alerts_by_level': {},
            'monitoring_period_hours': hours
        }
        
        # Count metric types
        metric_types = {}
        for metric in recent_metrics:
            metric_type = metric.metric_type.value
            metric_types[metric_type] = metric_types.get(metric_type, 0) + 1
        
        summary['metric_types'] = metric_types
        
        # Count alerts by level
        alerts_by_level = {}
        for alert in self.alerts:
            level = alert['level'].value
            alerts_by_level[level] = alerts_by_level.get(level, 0) + 1
        
        summary['alerts_by_level'] = alerts_by_level
        
        return summary
    
    def get_alerts(self, level: AlertLevel = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alerts with optional filtering."""
        alerts = self.alerts
        
        if level:
            alerts = [alert for alert in alerts if alert['level'] == level]
        
        # Sort by timestamp (most recent first)
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return alerts[:limit]
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts.clear()
    
    def get_health_status(self) -> str:
        """Get overall health status."""
        health_checks = self.run_health_checks()
        
        statuses = [check.status for check in health_checks.values()]
        
        if "unhealthy" in statuses:
            return "unhealthy"
        elif "degraded" in statuses:
            return "degraded"
        else:
            return "healthy"


# Global monitoring manager instance
monitoring_manager = MonitoringManager()


# ── Monitoring Decorators ─────────────────────────────────────────────────────

def monitor_performance(func):
    """Decorator to monitor function performance."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as exc:
            success = False
            error = str(exc)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record performance metric
            metric = Metric(
                name=f"function_performance_{func.__name__}",
                value=duration_ms,
                metric_type=MetricType.TIMER,
                labels={
                    'function': func.__name__,
                    'success': str(success),
                    'error': error or ''
                },
                help_text=f"Performance of {func.__name__} function"
            )
            
            # Add to monitoring manager
            monitoring_manager.metrics_history.append(metric)
            
            # Check if performance is poor
            if duration_ms > 1000:  # 1 second threshold
                monitoring_manager.alerts.append({
                    'level': AlertLevel.WARNING,
                    'message': f"Slow function: {func.__name__} took {duration_ms:.2f}ms",
                    'timestamp': timezone.now()
                })
        
        return result
    return wrapper


def monitor_errors(func):
    """Decorator to monitor function errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            # Record error metric
            metric = Metric(
                name=f"function_error_{func.__name__}",
                value=1,
                metric_type=MetricType.COUNTER,
                labels={
                    'function': func.__name__,
                    'error_type': type(exc).__name__,
                    'error_message': str(exc)
                },
                help_text=f"Error count for {func.__name__} function"
            )
            
            # Add to monitoring manager
            monitoring_manager.metrics_history.append(metric)
            
            # Add alert for critical errors
            monitoring_manager.alerts.append({
                'level': AlertLevel.ERROR,
                'message': f"Function error: {func.__name__} - {str(exc)}",
                'timestamp': timezone.now()
            })
            
            raise
    
    return wrapper


# ── Monitoring Tasks ─────────────────────────────────────────────────────

class MonitoringTasks:
    """Scheduled monitoring tasks."""
    
    @staticmethod
    def collect_metrics():
        """Collect all metrics and store them."""
        try:
            metrics = monitoring_manager.collect_all_metrics()
            
            # Store metrics in cache for quick access
            cache.set('monitoring_metrics', metrics, timeout=300)
            
            # Store summary
            summary = monitoring_manager.get_metrics_summary()
            cache.set('monitoring_summary', summary, timeout=300)
            
            logger.info(f"Collected metrics from {len(metrics)} monitors")
            
        except Exception as exc:
            logger.error(f"Failed to collect metrics: {exc}")
    
    @staticmethod
    def run_health_checks():
        """Run health checks and store results."""
        try:
            health_checks = monitoring_manager.run_health_checks()
            
            # Store health checks in cache
            cache.set('health_checks', health_checks, timeout=300)
            
            # Log any issues
            unhealthy_checks = [
                (name, check) for name, check in health_checks.items()
                if check.status in ['unhealthy', 'degraded']
            ]
            
            if unhealthy_checks:
                for name, check in unhealthy_checks:
                    level = 'ERROR' if check.status == 'unhealthy' else 'WARNING'
                    logger.log(
                        getattr(logging, level.lower(), logging.INFO),
                        f"Health check {name}: {check.message}"
                    )
            
            logger.info(f"Health checks completed: {len(health_checks)} monitors")
            
        except Exception as exc:
            logger.error(f"Failed to run health checks: {exc}")
    
    @staticmethod
    def cleanup_old_metrics():
        """Clean up old metrics data."""
        try:
            # Remove metrics older than 7 days
            cutoff_time = timezone.now() - timedelta(days=7)
            
            original_size = len(monitoring_manager.metrics_history)
            monitoring_manager.metrics_history = [
                metric for metric in monitoring_manager.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            cleaned_count = original_size - len(monitoring_manager.metrics_history)
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old metrics")
            
        except Exception as exc:
            logger.error(f"Failed to cleanup old metrics: {exc}")
    
    @staticmethod
    def generate_report():
        """Generate monitoring report."""
        try:
            metrics_summary = monitoring_manager.get_metrics_summary()
            health_checks = monitoring_manager.run_health_checks()
            alerts = monitoring_manager.get_alerts(limit=10)
            
            report = {
                'timestamp': timezone.now().isoformat(),
                'health_status': monitoring_manager.get_health_status(),
                'metrics_summary': metrics_summary,
                'health_checks': {
                    name: {
                        'status': check.status,
                        'message': check.message,
                        'duration_ms': check.duration_ms
                    }
                    for name, check in health_checks.items()
                },
                'recent_alerts': [
                    {
                        'level': alert['level'].value,
                        'message': alert['message'],
                        'timestamp': alert['timestamp'].isoformat()
                    }
                    for alert in alerts
                ]
            }
            
            return report
            
        except Exception as exc:
            logger.error(f"Failed to generate monitoring report: {exc}")
            return {'error': str(exc)}


# ── Monitoring API ─────────────────────────────────────────────────────

class MonitoringAPI:
    """API for accessing monitoring data."""
    
    @staticmethod
    def get_metrics_summary():
        """Get metrics summary."""
        summary = cache.get('monitoring_summary')
        if not summary:
            summary = monitoring_manager.get_metrics_summary()
            cache.set('monitoring_summary', summary, timeout=300)
        
        return summary
    
    @staticmethod
    def get_health_checks():
        """Get health check results."""
        health_checks = cache.get('health_checks')
        if not health_checks:
            health_checks = monitoring_manager.run_health_checks()
            cache.set('health_checks', health_checks, timeout=300)
        
        return health_checks
    
    @staticmethod
    def get_recent_alerts(limit: int = 20):
        """Get recent alerts."""
        return monitoring_manager.get_alerts(limit=limit)
    
    @staticmethod
    def get_metrics_by_type(metric_type: str, hours: int = 24):
        """Get metrics by type."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        metrics = [
            metric for metric in monitoring_manager.metrics_history
            if metric.metric_type.value == metric_type and metric.timestamp >= cutoff_time
        ]
        
        return sorted(metrics, key=lambda x: x.timestamp, reverse=True)
    
    @staticmethod
    def get_metrics_by_name(metric_name: str, hours: int = 24):
        """Get metrics by name."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        metrics = [
            metric for metric in monitoring_manager.metrics_history
            if metric.name == metric_name and metric.timestamp >= cutoff_time
        ]
        
        return sorted(metrics, key=lambda x: x.timestamp, reverse=True)
