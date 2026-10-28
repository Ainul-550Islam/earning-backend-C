"""
performance_monitor.py – Performance monitoring for postback module.

Provides comprehensive performance monitoring functionality including:
- Real-time performance metrics
- Resource usage monitoring
- Performance alerts and thresholds
- Performance analytics and reporting
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import time
import psutil
import gc
from collections import defaultdict, deque

from django.utils import timezone
from django.core.cache import cache
from django.db import connection

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type enumeration."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    METER = "meter"


class AlertSeverity(Enum):
    """Alert severity enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PerformanceStatus(Enum):
    """Performance status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Metric data structure."""
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=timezone.now)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'type': self.metric_type.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'labels': self.labels,
            'unit': self.unit,
            'description': self.description,
        }


@dataclass
class PerformanceAlert:
    """Performance alert data structure."""
    id: str
    metric_name: str
    severity: AlertSeverity
    message: str
    threshold: float
    current_value: float
    timestamp: datetime = field(default_factory=timezone.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'severity': self.severity.value,
            'message': self.message,
            'threshold': self.threshold,
            'current_value': self.current_value,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'metadata': self.metadata,
        }


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""
    metric_name: str
    warning_threshold: float
    error_threshold: float
    critical_threshold: float
    comparison: str = "greater_than"  # greater_than, less_than, equals
    enabled: bool = True
    cooldown_period: int = 300  # seconds
    
    def check_alert(self, current_value: float) -> Optional[AlertSeverity]:
        """Check if threshold is breached."""
        if not self.enabled:
            return None
        
        if self.comparison == "greater_than":
            if current_value >= self.critical_threshold:
                return AlertSeverity.CRITICAL
            elif current_value >= self.error_threshold:
                return AlertSeverity.ERROR
            elif current_value >= self.warning_threshold:
                return AlertSeverity.WARNING
        elif self.comparison == "less_than":
            if current_value <= self.critical_threshold:
                return AlertSeverity.CRITICAL
            elif current_value <= self.error_threshold:
                return AlertSeverity.ERROR
            elif current_value <= self.warning_threshold:
                return AlertSeverity.WARNING
        
        return None


class MetricsCollector:
    """
    Metrics collector for performance monitoring.
    
    Collects and manages various performance metrics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment counter metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
            
            metric = Metric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=self.counters[key],
                labels=labels or {}
            )
            self.metrics[key].append(metric)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set gauge metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            
            metric = Metric(
                name=name,
                metric_type=MetricType.GAUGE,
                value=value,
                labels=labels or {}
            )
            self.metrics[key].append(metric)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record histogram metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            
            # Keep only last 1000 values
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            
            metric = Metric(
                name=name,
                metric_type=MetricType.HISTOGRAM,
                value=value,
                labels=labels or {}
            )
            self.metrics[key].append(metric)
    
    def record_timer(self, name: str, duration: float, labels: Dict[str, str] = None):
        """Record timer metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.timers[key].append(duration)
            
            # Keep only last 1000 values
            if len(self.timers[key]) > 1000:
                self.timers[key] = self.timers[key][-1000:]
            
            metric = Metric(
                name=name,
                metric_type=MetricType.TIMER,
                value=duration,
                labels=labels or {}
            )
            self.metrics[key].append(metric)
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"
    
    def get_metric(self, name: str, labels: Dict[str, str] = None) -> Optional[Metric]:
        """Get latest metric."""
        key = self._make_key(name, labels)
        metrics = self.metrics.get(key)
        return metrics[-1] if metrics else None
    
    def get_metrics(self, name: str, labels: Dict[str, str] = None, limit: int = 100) -> List[Metric]:
        """Get metrics history."""
        key = self._make_key(name, labels)
        metrics = self.metrics.get(key, deque())
        return list(metrics)[-limit:]
    
    def get_statistics(self, name: str, labels: Dict[str, str] = None) -> Dict[str, Any]:
        """Get metric statistics."""
        key = self._make_key(name, labels)
        
        if key in self.counters:
            return {
                'type': 'counter',
                'value': self.counters[key],
            }
        elif key in self.gauges:
            return {
                'type': 'gauge',
                'value': self.gauges[key],
            }
        elif key in self.histograms:
            values = self.histograms[key]
            if not values:
                return {'type': 'histogram', 'count': 0}
            
            return {
                'type': 'histogram',
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'sum': sum(values),
            }
        elif key in self.timers:
            durations = self.timers[key]
            if not durations:
                return {'type': 'timer', 'count': 0}
            
            return {
                'type': 'timer',
                'count': len(durations),
                'min': min(durations),
                'max': max(durations),
                'avg': sum(durations) / len(durations),
                'sum': sum(durations),
                'p50': self._percentile(durations, 50),
                'p95': self._percentile(durations, 95),
                'p99': self._percentile(durations, 99),
            }
        
        return {}
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]


class ResourceMonitor:
    """
    Resource usage monitor.
    
    Monitors CPU, memory, disk, and network usage.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics_collector = MetricsCollector()
        self.monitoring = False
        self.monitor_thread = None
        self.interval = 30  # seconds
    
    def start_monitoring(self):
        """Start resource monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Resource monitoring stopped")
    
    def _monitor_loop(self):
        """Resource monitoring loop."""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                self._collect_database_metrics()
                self._collect_cache_metrics()
                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {str(e)}")
                time.sleep(5)
    
    def _collect_system_metrics(self):
        """Collect system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics_collector.set_gauge("system_cpu_usage", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics_collector.set_gauge("system_memory_usage", memory.percent)
            self.metrics_collector.set_gauge("system_memory_used_gb", memory.used / (1024**3))
            self.metrics_collector.set_gauge("system_memory_available_gb", memory.available / (1024**3))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.metrics_collector.set_gauge("system_disk_usage", disk.percent)
            self.metrics_collector.set_gauge("system_disk_used_gb", disk.used / (1024**3))
            self.metrics_collector.set_gauge("system_disk_free_gb", disk.free / (1024**3))
            
            # Network I/O
            network = psutil.net_io_counters()
            self.metrics_collector.set_gauge("system_network_bytes_sent", network.bytes_sent)
            self.metrics_collector.set_gauge("system_network_bytes_recv", network.bytes_recv)
            
            # Process info
            process = psutil.Process()
            self.metrics_collector.set_gauge("process_cpu_usage", process.cpu_percent())
            self.metrics_collector.set_gauge("process_memory_usage", process.memory_percent())
            self.metrics_collector.set_gauge("process_memory_mb", process.memory_info().rss / (1024**2))
            self.metrics_collector.set_gauge("process_threads", process.num_threads())
            self.metrics_collector.set_gauge("process_fds", process.num_fds())
        
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {str(e)}")
    
    def _collect_database_metrics(self):
        """Collect database metrics."""
        try:
            # Database connections
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
                self.metrics_collector.set_gauge("database_active_connections", active_connections)
                
                cursor.execute("SELECT count(*) FROM pg_stat_activity")
                total_connections = cursor.fetchone()[0]
                self.metrics_collector.set_gauge("database_total_connections", total_connections)
        
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {str(e)}")
    
    def _collect_cache_metrics(self):
        """Collect cache metrics."""
        try:
            # Django cache stats
            cache_info = cache._cache.info() if hasattr(cache, '_cache') else {}
            
            for backend_name, info in cache_info.items():
                if isinstance(info, dict):
                    hits = info.get('hits', 0)
                    misses = info.get('misses', 0)
                    max_size = info.get('max_entries', 0)
                    curr_size = info.get('curr_size', 0)
                    
                    total_requests = hits + misses
                    hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
                    
                    self.metrics_collector.set_gauge(
                        f"cache_hit_rate",
                        hit_rate,
                        {'backend': backend_name}
                    )
                    self.metrics_collector.set_gauge(
                        f"cache_size",
                        curr_size,
                        {'backend': backend_name}
                    )
                    self.metrics_collector.set_gauge(
                        f"cache_max_size",
                        max_size,
                        {'backend': backend_name}
                    )
        
        except Exception as e:
            self.logger.error(f"Error collecting cache metrics: {str(e)}")
    
    def get_resource_metrics(self) -> Dict[str, Any]:
        """Get current resource metrics."""
        return {
            'cpu': self.metrics_collector.get_statistics("system_cpu_usage"),
            'memory': self.metrics_collector.get_statistics("system_memory_usage"),
            'disk': self.metrics_collector.get_statistics("system_disk_usage"),
            'database': {
                'active_connections': self.metrics_collector.get_statistics("database_active_connections"),
                'total_connections': self.metrics_collector.get_statistics("database_total_connections"),
            },
            'cache': self.metrics_collector.get_statistics("cache_hit_rate"),
        }


class PerformanceMonitor:
    """
    Main performance monitor.
    
    Orchestrates performance monitoring, alerts,
    and reporting.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics_collector = MetricsCollector()
        self.resource_monitor = ResourceMonitor()
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        self.alerts: List[PerformanceAlert] = []
        self.alert_handlers: List[Callable] = []
        self.monitoring = False
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """Setup default performance thresholds."""
        default_thresholds = [
            PerformanceThreshold(
                metric_name="system_cpu_usage",
                warning_threshold=70.0,
                error_threshold=85.0,
                critical_threshold=95.0,
                comparison="greater_than"
            ),
            PerformanceThreshold(
                metric_name="system_memory_usage",
                warning_threshold=75.0,
                error_threshold=85.0,
                critical_threshold=95.0,
                comparison="greater_than"
            ),
            PerformanceThreshold(
                metric_name="system_disk_usage",
                warning_threshold=80.0,
                error_threshold=90.0,
                critical_threshold=95.0,
                comparison="greater_than"
            ),
            PerformanceThreshold(
                metric_name="database_active_connections",
                warning_threshold=50.0,
                error_threshold=80.0,
                critical_threshold=100.0,
                comparison="greater_than"
            ),
            PerformanceThreshold(
                metric_name="cache_hit_rate",
                warning_threshold=80.0,
                error_threshold=60.0,
                critical_threshold=40.0,
                comparison="less_than"
            ),
        ]
        
        for threshold in default_thresholds:
            self.thresholds[threshold.metric_name] = threshold
    
    def start_monitoring(self):
        """Start performance monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.resource_monitor.start_monitoring()
        self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.monitoring:
            return
        
        self.monitoring = False
        self.resource_monitor.stop_monitoring()
        self.logger.info("Performance monitoring stopped")
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """Add performance threshold."""
        self.thresholds[threshold.metric_name] = threshold
        self.logger.info(f"Threshold added: {threshold.metric_name}")
    
    def remove_threshold(self, metric_name: str):
        """Remove performance threshold."""
        if metric_name in self.thresholds:
            del self.thresholds[metric_name]
            self.logger.info(f"Threshold removed: {metric_name}")
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler."""
        self.alert_handlers.append(handler)
        self.logger.info("Alert handler added")
    
    def check_thresholds(self) -> List[PerformanceAlert]:
        """Check all thresholds and generate alerts."""
        alerts = []
        
        for metric_name, threshold in self.thresholds.items():
            try:
                metric = self.metrics_collector.get_metric(metric_name)
                if not metric:
                    continue
                
                severity = threshold.check_alert(metric.value)
                if severity:
                    alert = PerformanceAlert(
                        id=f"alert_{int(time.time() * 1000)}",
                        metric_name=metric_name,
                        severity=severity,
                        message=f"{metric_name} is {metric.value:.2f} (threshold: {threshold.warning_threshold})",
                        threshold=threshold.warning_threshold,
                        current_value=metric.value
                    )
                    alerts.append(alert)
                    self.alerts.append(alert)
                    
                    # Trigger alert handlers
                    for handler in self.alert_handlers:
                        try:
                            handler(alert)
                        except Exception as e:
                            self.logger.error(f"Alert handler error: {str(e)}")
            
            except Exception as e:
                self.logger.error(f"Error checking threshold {metric_name}: {str(e)}")
        
        return alerts
    
    def record_request_time(self, endpoint: str, duration: float, status_code: int = None):
        """Record request timing."""
        labels = {'endpoint': endpoint}
        if status_code:
            labels['status_code'] = str(status_code)
        
        self.metrics_collector.record_timer("request_duration", duration, labels)
        self.metrics_collector.increment_counter("request_count", 1.0, labels)
    
    def record_error(self, error_type: str, error_message: str = None):
        """Record error occurrence."""
        labels = {'error_type': error_type}
        if error_message:
            labels['error_message'] = error_message[:50]  # Truncate long messages
        
        self.metrics_collector.increment_counter("error_count", 1.0, labels)
    
    def record_business_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record business metric."""
        self.metrics_collector.set_gauge(name, value, labels)
    
    def get_performance_status(self) -> PerformanceStatus:
        """Get overall performance status."""
        alerts = self.check_thresholds()
        
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        error_alerts = [a for a in alerts if a.severity == AlertSeverity.ERROR]
        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
        
        if critical_alerts:
            return PerformanceStatus.CRITICAL
        elif error_alerts:
            return PerformanceStatus.UNHEALTHY
        elif warning_alerts:
            return PerformanceStatus.DEGRADED
        else:
            return PerformanceStatus.HEALTHY
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            'performance_status': self.get_performance_status().value,
            'total_metrics': len(self.metrics_collector.metrics),
            'active_thresholds': len([t for t in self.thresholds.values() if t.enabled]),
            'active_alerts': len([a for a in self.alerts if not a.resolved]),
            'resource_metrics': self.resource_monitor.get_resource_metrics(),
        }
    
    def get_alerts(self, resolved: bool = None, severity: AlertSeverity = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get performance alerts."""
        alerts = self.alerts
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        return [alert.to_dict() for alert in alerts[:limit]]
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = timezone.now()
                self.logger.info(f"Alert resolved: {alert_id}")
                return True
        return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        status = self.get_performance_status()
        
        return {
            'overall_status': status.value,
            'monitoring_active': self.monitoring,
            'metrics_collected': len(self.metrics_collector.metrics),
            'active_alerts': len([a for a in self.alerts if not a.resolved]),
            'resource_monitoring': self.resource_monitor.monitoring,
            'timestamp': timezone.now().isoformat(),
        }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# Decorators for performance monitoring
def monitor_performance(metric_name: str = None, include_args: bool = False):
    """
    Decorator for monitoring function performance.
    
    Args:
        metric_name: Custom metric name
        include_args: Include function arguments in labels
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                performance_monitor.record_error(type(e).__name__, str(e))
                raise
            finally:
                duration = time.time() - start_time
                
                # Determine metric name
                name = metric_name or f"{func.__module__}.{func.__name__}"
                
                # Create labels
                labels = {'function': func.__name__, 'status': status}
                if include_args:
                    # Add first few arguments as labels (be careful with sensitive data)
                    for i, arg in enumerate(args[:3]):
                        labels[f'arg_{i}'] = str(arg)[:50]
                
                performance_monitor.record_request_time(name, duration, 200 if status == 'success' else 500)
        
        return wrapper
    return decorator


# Convenience functions
def start_performance_monitoring():
    """Start performance monitoring."""
    performance_monitor.start_monitoring()


def stop_performance_monitoring():
    """Stop performance monitoring."""
    performance_monitor.stop_monitoring()


def record_performance_metric(name: str, value: float, labels: Dict[str, str] = None):
    """Record performance metric."""
    performance_monitor.record_business_metric(name, value, labels)


def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary."""
    return performance_monitor.get_metrics_summary()


def get_performance_alerts(resolved: bool = None, severity: AlertSeverity = None) -> List[Dict[str, Any]]:
    """Get performance alerts."""
    return performance_monitor.get_alerts(resolved, severity)


def perform_performance_health_check() -> Dict[str, Any]:
    """Perform performance health check."""
    return performance_monitor.health_check()
