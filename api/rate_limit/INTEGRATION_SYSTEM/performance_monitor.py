"""
Performance Monitor - Real-time Performance Monitoring

Real-time performance monitoring system for tracking metrics,
analyzing performance trends, and detecting anomalies.
"""

import logging
import time
import threading
import psutil
import gc
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from queue import Queue, Empty
from django.core.cache import cache
from django.utils import timezone
from django.db import connection

from .integ_constants import IntegrationEvent, IntegrationStatus
from .integ_exceptions import IntegrationError
from .event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    AVERAGE = "average"
    RATE = "rate"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Metric data structure."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=timezone.now)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""


@dataclass
class MetricDefinition:
    """Metric definition."""
    name: str
    metric_type: MetricType
    description: str
    unit: str = ""
    labels: List[str] = field(default_factory=list)
    buckets: List[float] = field(default_factory=list)  # For histograms
    aggregation: str = "sum"  # sum, avg, min, max


@dataclass
class PerformanceAlert:
    """Performance alert."""
    alert_id: str
    metric_name: str
    condition: str
    threshold: float
    current_value: float
    severity: AlertSeverity
    message: str
    triggered_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Performance snapshot."""
    timestamp: datetime = field(default_factory=timezone.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    active_connections: int = 0
    request_count: int = 0
    error_count: int = 0
    average_response_time: float = 0.0
    cache_hit_rate: float = 0.0
    queue_sizes: Dict[str, int] = field(default_factory=dict)
    custom_metrics: Dict[str, float] = field(default_factory=dict)


class PerformanceMonitor:
    """Real-time performance monitoring system."""
    
    def __init__(self):
        self.metrics: Dict[str, MetricDefinition] = {}
        self.metric_values: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: Dict[str, PerformanceAlert] = {}
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        self.snapshots: deque = deque(maxlen=1440)  # 24 hours of minute snapshots
        self.statistics = {
            'total_metrics': 0,
            'total_alerts': 0,
            'active_alerts': 0,
            'monitoring_start_time': timezone.now(),
            'last_snapshot_time': None
        }
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._alert_thread: Optional[threading.Thread] = None
        self._metric_handlers: Dict[str, Callable] = {}
        
        # Initialize default metrics
        self._initialize_default_metrics()
        self._initialize_alert_rules()
        
        # Start monitoring
        self._start_monitoring()
    
    def _initialize_default_metrics(self):
        """Initialize default metrics."""
        default_metrics = [
            # System metrics
            MetricDefinition("system.cpu_percent", MetricType.GAUGE, "CPU usage percentage", "%"),
            MetricDefinition("system.memory_percent", MetricType.GAUGE, "Memory usage percentage", "%"),
            MetricDefinition("system.memory_used_mb", MetricType.GAUGE, "Memory usage in MB", "MB"),
            MetricDefinition("system.disk_usage_percent", MetricType.GAUGE, "Disk usage percentage", "%"),
            
            # Application metrics
            MetricDefinition("app.request_count", MetricType.COUNTER, "Total number of requests", "count"),
            MetricDefinition("app.error_count", MetricType.COUNTER, "Total number of errors", "count"),
            MetricDefinition("app.response_time", MetricType.HISTOGRAM, "Request response time", "ms", 
                           buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]),
            MetricDefinition("app.active_connections", MetricType.GAUGE, "Active database connections", "count"),
            MetricDefinition("app.cache_hit_rate", MetricType.GAUGE, "Cache hit rate", "%"),
            
            # Integration metrics
            MetricDefinition("integration.requests_total", MetricType.COUNTER, "Total integration requests", "count"),
            MetricDefinition("integration.requests_failed", MetricType.COUNTER, "Failed integration requests", "count"),
            MetricDefinition("integration.request_duration", MetricType.HISTOGRAM, "Integration request duration", "ms",
                           buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000]),
            MetricDefinition("integration.circuit_breaker_state", MetricType.GAUGE, "Circuit breaker state", "state"),
            
            # Queue metrics
            MetricDefinition("queue.size", MetricType.GAUGE, "Queue size", "count"),
            MetricDefinition("queue.processing_rate", MetricType.RATE, "Queue processing rate", "rate"),
            MetricDefinition("queue.error_rate", MetricType.RATE, "Queue error rate", "rate"),
        ]
        
        for metric_def in default_metrics:
            self.register_metric(metric_def)
    
    def _initialize_alert_rules(self):
        """Initialize default alert rules."""
        self.alert_rules = {
            'high_cpu_usage': {
                'metric': 'system.cpu_percent',
                'condition': '>',
                'threshold': 80.0,
                'severity': AlertSeverity.WARNING,
                'duration': 300,  # 5 minutes
                'message': 'High CPU usage detected'
            },
            'critical_cpu_usage': {
                'metric': 'system.cpu_percent',
                'condition': '>',
                'threshold': 95.0,
                'severity': AlertSeverity.CRITICAL,
                'duration': 60,  # 1 minute
                'message': 'Critical CPU usage detected'
            },
            'high_memory_usage': {
                'metric': 'system.memory_percent',
                'condition': '>',
                'threshold': 85.0,
                'severity': AlertSeverity.WARNING,
                'duration': 300,
                'message': 'High memory usage detected'
            },
            'critical_memory_usage': {
                'metric': 'system.memory_percent',
                'condition': '>',
                'threshold': 95.0,
                'severity': AlertSeverity.CRITICAL,
                'duration': 60,
                'message': 'Critical memory usage detected'
            },
            'high_error_rate': {
                'metric': 'app.error_rate',
                'condition': '>',
                'threshold': 0.1,  # 10%
                'severity': AlertSeverity.ERROR,
                'duration': 300,
                'message': 'High error rate detected'
            },
            'slow_response_time': {
                'metric': 'app.response_time_p95',
                'condition': '>',
                'threshold': 1000.0,  # 1 second
                'severity': AlertSeverity.WARNING,
                'duration': 300,
                'message': 'Slow response time detected'
            },
            'low_cache_hit_rate': {
                'metric': 'app.cache_hit_rate',
                'condition': '<',
                'threshold': 80.0,  # 80%
                'severity': AlertSeverity.WARNING,
                'duration': 600,
                'message': 'Low cache hit rate detected'
            }
        }
    
    def _start_monitoring(self):
        """Start monitoring threads."""
        self._running = True
        
        # Start system monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="PerformanceMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        # Start alert checking thread
        self._alert_thread = threading.Thread(
            target=self._alert_loop,
            name="AlertMonitor",
            daemon=True
        )
        self._alert_thread.start()
        
        logger.info("Started performance monitoring system")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                
                # Collect application metrics
                self._collect_application_metrics()
                
                # Create performance snapshot
                snapshot = self._create_snapshot()
                self.snapshots.append(snapshot)
                
                self.statistics['last_snapshot_time'] = timezone.now()
                
                # Sleep for 1 minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {str(e)}")
                time.sleep(60)
    
    def _alert_loop(self):
        """Alert checking loop."""
        while self._running:
            try:
                # Check alert rules
                self._check_alert_rules()
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Alert loop error: {str(e)}")
                time.sleep(30)
    
    def _collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("system.cpu_percent", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric("system.memory_percent", memory.percent)
            self.record_metric("system.memory_used_mb", memory.used / (1024 * 1024))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.record_metric("system.disk_usage_percent", disk.percent)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
    
    def _collect_application_metrics(self):
        """Collect application-level metrics."""
        try:
            # Database connections
            if hasattr(connection, 'connections'):
                active_connections = len([c for c in connection.connections.values() if c.connection])
                self.record_metric("app.active_connections", active_connections)
            
            # Cache hit rate (simplified)
            # This would integrate with actual cache metrics
            cache_hit_rate = self._calculate_cache_hit_rate()
            self.record_metric("app.cache_hit_rate", cache_hit_rate)
            
            # Error rate
            error_rate = self._calculate_error_rate()
            self.record_metric("app.error_rate", error_rate)
            
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {str(e)}")
    
    def _create_snapshot(self) -> PerformanceSnapshot:
        """Create performance snapshot."""
        snapshot = PerformanceSnapshot()
        
        # Get current metric values
        snapshot.cpu_percent = self._get_current_metric_value("system.cpu_percent", 0.0)
        snapshot.memory_percent = self._get_current_metric_value("system.memory_percent", 0.0)
        snapshot.memory_used_mb = self._get_current_metric_value("system.memory_used_mb", 0.0)
        snapshot.disk_usage_percent = self._get_current_metric_value("system.disk_usage_percent", 0.0)
        snapshot.active_connections = int(self._get_current_metric_value("app.active_connections", 0))
        snapshot.request_count = int(self._get_current_metric_value("app.request_count", 0))
        snapshot.error_count = int(self._get_current_metric_value("app.error_count", 0))
        snapshot.average_response_time = self._get_current_metric_value("app.response_time_avg", 0.0)
        snapshot.cache_hit_rate = self._get_current_metric_value("app.cache_hit_rate", 0.0)
        
        return snapshot
    
    def _get_current_metric_value(self, metric_name: str, default: float = 0.0) -> float:
        """Get current metric value."""
        values = self.metric_values.get(metric_name)
        if values and len(values) > 0:
            return values[-1].value
        return default
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        # This would integrate with actual cache metrics
        # For now, return a simulated value
        return 85.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate."""
        requests = self._get_current_metric_value("app.request_count", 1.0)
        errors = self._get_current_metric_value("app.error_count", 0.0)
        
        if requests > 0:
            return errors / requests
        return 0.0
    
    def _check_alert_rules(self):
        """Check alert rules and trigger alerts."""
        current_time = timezone.now()
        
        for rule_name, rule in self.alert_rules.items():
            try:
                metric_name = rule['metric']
                condition = rule['condition']
                threshold = rule['threshold']
                severity = rule['severity']
                duration = rule['duration']
                
                # Get current metric value
                current_value = self._get_current_metric_value(metric_name)
                
                # Check condition
                triggered = self._evaluate_condition(current_value, condition, threshold)
                
                # Check if alert already exists
                alert = self.alerts.get(rule_name)
                
                if triggered and not alert:
                    # Create new alert
                    alert = PerformanceAlert(
                        alert_id=f"alert_{rule_name}_{int(current_time.timestamp())}",
                        metric_name=metric_name,
                        condition=condition,
                        threshold=threshold,
                        current_value=current_value,
                        severity=severity,
                        message=rule['message']
                    )
                    
                    self.alerts[rule_name] = alert
                    self.statistics['total_alerts'] += 1
                    self.statistics['active_alerts'] += 1
                    
                    logger.warning(f"Alert triggered: {rule_name} - {rule['message']}")
                    
                    # Publish alert event
                    self._publish_alert_event(alert)
                    
                elif triggered and alert and alert.is_active:
                    # Check duration
                    if (current_time - alert.triggered_at).total_seconds() >= duration:
                        # Alert has been active for required duration
                        pass  # Alert is already active
                
                elif not triggered and alert and alert.is_active:
                    # Resolve alert
                    alert.is_active = False
                    alert.resolved_at = current_time
                    self.statistics['active_alerts'] -= 1
                    
                    logger.info(f"Alert resolved: {rule_name}")
                    
                    # Publish alert resolution event
                    self._publish_alert_event(alert)
                
            except Exception as e:
                logger.error(f"Alert rule check failed for {rule_name}: {str(e)}")
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition."""
        if condition == '>':
            return value > threshold
        elif condition == '<':
            return value < threshold
        elif condition == '>=':
            return value >= threshold
        elif condition == '<=':
            return value <= threshold
        elif condition == '==':
            return value == threshold
        elif condition == '!=':
            return value != threshold
        else:
            return False
    
    def _publish_alert_event(self, alert: PerformanceAlert):
        """Publish alert event to event bus."""
        try:
            import asyncio
            
            event_data = {
                'alert_id': alert.alert_id,
                'metric_name': alert.metric_name,
                'condition': alert.condition,
                'threshold': alert.threshold,
                'current_value': alert.current_value,
                'severity': alert.severity.value,
                'message': alert.message,
                'triggered_at': alert.triggered_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'is_active': alert.is_active
            }
            
            event_type = "performance.alert.resolved" if not alert.is_active else "performance.alert.triggered"
            
            asyncio.create_task(event_bus.publish(
                Event(event_type, event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish alert event: {str(e)}")
    
    def register_metric(self, metric_def: MetricDefinition):
        """Register a new metric."""
        with self._lock:
            self.metrics[metric_def.name] = metric_def
            self.statistics['total_metrics'] += 1
            logger.info(f"Registered metric: {metric_def.name}")
    
    def record_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric value."""
        try:
            metric_def = self.metrics.get(name)
            if not metric_def:
                # Auto-register metric if not exists
                metric_def = MetricDefinition(name, MetricType.GAUGE, f"Auto-registered metric: {name}")
                self.register_metric(metric_def)
            
            metric = Metric(
                name=name,
                value=value,
                metric_type=metric_def.metric_type,
                labels=labels or {},
                unit=metric_def.unit,
                description=metric_def.description
            )
            
            # Store metric value
            self.metric_values[name].append(metric)
            
            # Call custom handler if exists
            if name in self._metric_handlers:
                try:
                    self._metric_handlers[name](metric)
                except Exception as e:
                    logger.error(f"Metric handler failed for {name}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to record metric {name}: {str(e)}")
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        current_value = self._get_current_metric_value(name, 0.0)
        self.record_metric(name, current_value + value, labels)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        self.record_metric(name, value, labels)
    
    def record_timer(self, name: str, duration: float, labels: Dict[str, str] = None):
        """Record a timer metric."""
        self.record_metric(name, duration, labels)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram metric."""
        self.record_metric(name, value, labels)
    
    def get_metric_values(self, name: str, since: datetime = None, limit: int = 100) -> List[Metric]:
        """Get metric values."""
        values = list(self.metric_values.get(name, []))
        
        # Filter by time
        if since:
            values = [v for v in values if v.timestamp >= since]
        
        # Sort by timestamp (newest first)
        values.sort(key=lambda v: v.timestamp, reverse=True)
        
        return values[:limit]
    
    def get_metric_statistics(self, name: str, since: datetime = None) -> Dict[str, Any]:
        """Get metric statistics."""
        values = self.get_metric_values(name, since)
        
        if not values:
            return {}
        
        numeric_values = [v.value for v in values]
        
        return {
            'count': len(numeric_values),
            'min': min(numeric_values),
            'max': max(numeric_values),
            'avg': sum(numeric_values) / len(numeric_values),
            'sum': sum(numeric_values),
            'latest': numeric_values[-1] if numeric_values else None,
            'first_timestamp': values[0].timestamp.isoformat() if values else None,
            'last_timestamp': values[-1].timestamp.isoformat() if values else None
        }
    
    def get_current_snapshot(self) -> Optional[PerformanceSnapshot]:
        """Get current performance snapshot."""
        return self.snapshots[-1] if self.snapshots else None
    
    def get_snapshots(self, since: datetime = None, limit: int = 100) -> List[PerformanceSnapshot]:
        """Get performance snapshots."""
        snapshots = list(self.snapshots)
        
        # Filter by time
        if since:
            snapshots = [s for s in snapshots if s.timestamp >= since]
        
        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        
        return snapshots[:limit]
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get active alerts."""
        return [alert for alert in self.alerts.values() if alert.is_active]
    
    def get_alert_history(self, limit: int = 100) -> List[PerformanceAlert]:
        """Get alert history."""
        all_alerts = list(self.alerts.values())
        all_alerts.sort(key=lambda a: a.triggered_at, reverse=True)
        return all_alerts[:limit]
    
    def register_metric_handler(self, name: str, handler: Callable):
        """Register custom metric handler."""
        self._metric_handlers[name] = handler
        logger.info(f"Registered metric handler: {name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'total_metric_definitions': len(self.metrics),
                'total_metric_values': sum(len(values) for values in self.metric_values.values()),
                'total_snapshots': len(self.snapshots),
                'total_alert_rules': len(self.alert_rules),
                'uptime_hours': (timezone.now() - stats['monitoring_start_time']).total_seconds() / 3600,
                'metrics_by_type': self._get_metrics_by_type()
            })
            return stats
    
    def _get_metrics_by_type(self) -> Dict[str, int]:
        """Get metrics count by type."""
        counts = defaultdict(int)
        for metric_def in self.metrics.values():
            counts[metric_def.metric_type.value] += 1
        return dict(counts)
    
    def export_metrics(self, format: str = "prometheus") -> str:
        """Export metrics in specified format."""
        if format == "prometheus":
            return self._export_prometheus_format()
        elif format == "json":
            return self._export_json_format()
        else:
            raise IntegrationError(f"Unsupported export format: {format}")
    
    def _export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for name, metric_def in self.metrics.items():
            values = self.get_metric_values(name, limit=1)
            if values:
                latest_value = values[0]
                
                # Create metric name and labels
                metric_line = name
                if latest_value.labels:
                    label_str = ",".join([f'{k}="{v}"' for k, v in latest_value.labels.items()])
                    metric_line += f"{{{label_str}}}"
                
                metric_line += f" {latest_value.value}"
                lines.append(metric_line)
        
        return "\n".join(lines)
    
    def _export_json_format(self) -> str:
        """Export metrics in JSON format."""
        import json
        
        data = {
            'timestamp': timezone.now().isoformat(),
            'metrics': {}
        }
        
        for name, metric_def in self.metrics.items():
            values = self.get_metric_values(name, limit=1)
            if values:
                latest_value = values[0]
                data['metrics'][name] = {
                    'value': latest_value.value,
                    'timestamp': latest_value.timestamp.isoformat(),
                    'labels': latest_value.labels,
                    'type': metric_def.metric_type.value,
                    'unit': metric_def.unit
                }
        
        return json.dumps(data, indent=2)
    
    def shutdown(self):
        """Shutdown performance monitor."""
        logger.info("Shutting down performance monitor...")
        
        self._running = False
        
        # Wait for threads to finish
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        if self._alert_thread:
            self._alert_thread.join(timeout=5)
        
        logger.info("Performance monitor shutdown complete")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# Decorators for performance monitoring
def monitor_performance(metric_name: str = None):
    """Decorator to monitor function performance."""
    def decorator(func):
        name = metric_name or f"function.{func.__module__}.{func.__name__}"
        
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                performance_monitor.record_timer(f"{name}.duration", time.time() - start_time)
                performance_monitor.increment_counter(f"{name}.calls")
                return result
            except Exception as e:
                performance_monitor.record_timer(f"{name}.duration", time.time() - start_time)
                performance_monitor.increment_counter(f"{name}.errors")
                raise
        
        return wrapper
    return decorator


def track_metric(metric_name: str, metric_type: str = "gauge"):
    """Decorator to track custom metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                if metric_type == "counter":
                    performance_monitor.increment_counter(metric_name)
                elif metric_type == "gauge":
                    performance_monitor.set_gauge(metric_name, 1 if result else 0)
                elif metric_type == "timer":
                    # This would need to be implemented differently
                    pass
                
                return result
            except Exception as e:
                if metric_type == "counter":
                    performance_monitor.increment_counter(f"{metric_name}.errors")
                raise
        
        return wrapper
    return decorator


# Context manager for performance monitoring
class PerformanceContext:
    """Context manager for performance monitoring."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        performance_monitor.record_timer(f"operation.{self.operation_name}.duration", duration)
        performance_monitor.increment_counter(f"operation.{self.operation_name}.calls")
        
        if exc_type:
            performance_monitor.increment_counter(f"operation.{self.operation_name}.errors")
        
        return False  # Don't suppress exceptions
