"""
Performance Monitor
Comprehensive performance monitoring for integration system
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
import psutil
import threading
from collections import defaultdict, deque
from statistics import mean, median, stdev

from .integ_exceptions import IntegrationException, PerformanceMonitorException

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"
    PERCENTILE = "percentile"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PerformanceLevel(Enum):
    """Performance levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class MetricValue:
    """Single metric value"""
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricDefinition:
    """Metric definition"""
    name: str
    metric_type: MetricType
    description: str
    unit: str
    labels: List[str] = field(default_factory=list)
    enabled: bool = True
    aggregation_method: str = "avg"  # avg, sum, min, max
    retention_period: int = 3600  # seconds


@dataclass
class PerformanceThreshold:
    """Performance threshold definition"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str = "greater_than"  # greater_than, less_than, equals
    enabled: bool = True
    grace_period: int = 60  # seconds


@dataclass
class PerformanceAlert:
    """Performance alert"""
    alert_id: str
    metric_name: str
    severity: AlertSeverity
    message: str
    current_value: float
    threshold_value: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Performance snapshot at a point in time"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    process_count: int
    thread_count: int
    custom_metrics: Dict[str, MetricValue] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """Performance report over a time period"""
    start_time: datetime
    end_time: datetime
    performance_level: PerformanceLevel
    metrics_summary: Dict[str, Dict[str, float]]
    alerts: List[PerformanceAlert]
    recommendations: List[str]
    snapshots: List[PerformanceSnapshot] = field(default_factory=list)


class MetricsCollector:
    """Metrics collection and storage"""
    
    def __init__(self, max_values: int = 10000):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_values))
        self.metric_definitions: Dict[str, MetricDefinition] = {}
        self.max_values = max_values
    
    def register_metric(self, definition: MetricDefinition):
        """Register a metric definition"""
        self.metric_definitions[definition.name] = definition
    
    def add_metric_value(self, metric_name: str, value: float, 
                        labels: Optional[Dict[str, str]] = None,
                        metadata: Optional[Dict[str, Any]] = None):
        """Add a metric value"""
        if metric_name not in self.metric_definitions:
            # Auto-register metric with default definition
            self.metric_definitions[metric_name] = MetricDefinition(
                name=metric_name,
                metric_type=MetricType.GAUGE,
                description=f"Auto-registered metric: {metric_name}",
                unit="value"
            )
        
        metric_value = MetricValue(
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metadata=metadata or {}
        )
        
        self.metrics[metric_name].append(metric_value)
    
    def get_metric_values(self, metric_name: str, 
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         labels: Optional[Dict[str, str]] = None) -> List[MetricValue]:
        """Get metric values with optional filtering"""
        if metric_name not in self.metrics:
            return []
        
        values = list(self.metrics[metric_name])
        
        # Filter by time range
        if start_time:
            values = [v for v in values if v.timestamp >= start_time]
        if end_time:
            values = [v for v in values if v.timestamp <= end_time]
        
        # Filter by labels
        if labels:
            values = [v for v in values if all(
                v.labels.get(k) == v for k, v in labels.items()
            )]
        
        return values
    
    def get_metric_stats(self, metric_name: str,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> Dict[str, float]:
        """Get metric statistics"""
        values = self.get_metric_values(metric_name, start_time, end_time)
        
        if not values:
            return {}
        
        numeric_values = [v.value for v in values]
        
        stats = {
            'count': len(numeric_values),
            'min': min(numeric_values),
            'max': max(numeric_values),
            'avg': mean(numeric_values),
            'sum': sum(numeric_values)
        }
        
        if len(numeric_values) > 1:
            stats['median'] = median(numeric_values)
            stats['stdev'] = stdev(numeric_values)
        
        # Add percentiles
        sorted_values = sorted(numeric_values)
        stats['p50'] = sorted_values[int(len(sorted_values) * 0.5)]
        stats['p90'] = sorted_values[int(len(sorted_values) * 0.9)]
        stats['p95'] = sorted_values[int(len(sorted_values) * 0.95)]
        stats['p99'] = sorted_values[int(len(sorted_values) * 0.99)]
        
        return stats
    
    def cleanup_old_metrics(self, retention_period: int = 3600):
        """Clean up old metric values"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=retention_period)
        
        for metric_name, values in self.metrics.items():
            # Remove old values
            while values and values[0].timestamp < cutoff_time:
                values.popleft()


class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self):
        self.monitoring_enabled = True
        self.collection_interval = 30  # seconds
        self._monitoring_thread = None
        self._stop_event = threading.Event()
    
    def start_monitoring(self, metrics_collector: MetricsCollector):
        """Start system monitoring"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitor_loop,
            args=(metrics_collector,),
            daemon=True
        )
        self._monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        if self._monitoring_thread:
            self._stop_event.set()
            self._monitoring_thread.join(timeout=5)
    
    def _monitor_loop(self, metrics_collector: MetricsCollector):
        """Main monitoring loop"""
        while not self._stop_event.is_set():
            try:
                # Collect system metrics
                self._collect_system_metrics(metrics_collector)
                
                # Wait for next collection
                self._stop_event.wait(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                self._stop_event.wait(5)  # Wait before retrying
    
    def _collect_system_metrics(self, metrics_collector: MetricsCollector):
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics_collector.add_metric_value('system.cpu.usage', cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics_collector.add_metric_value('system.memory.usage', memory.percent)
            metrics_collector.add_metric_value('system.memory.available', memory.available)
            metrics_collector.add_metric_value('system.memory.used', memory.used)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics_collector.add_metric_value('system.disk.usage', disk.percent)
            metrics_collector.add_metric_value('system.disk.free', disk.free)
            metrics_collector.add_metric_value('system.disk.used', disk.used)
            
            # Network I/O
            network = psutil.net_io_counters()
            metrics_collector.add_metric_value('system.network.bytes_sent', network.bytes_sent)
            metrics_collector.add_metric_value('system.network.bytes_recv', network.bytes_recv)
            metrics_collector.add_metric_value('system.network.packets_sent', network.packets_sent)
            metrics_collector.add_metric_value('system.network.packets_recv', network.packets_recv)
            
            # Process count
            process_count = len(psutil.pids())
            metrics_collector.add_metric_value('system.process.count', process_count)
            
            # Thread count (current process)
            thread_count = threading.active_count()
            metrics_collector.add_metric_value('system.thread.count', thread_count)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            process_count = len(psutil.pids())
            thread_count = threading.active_count()
            
            return PerformanceSnapshot(
                timestamp=datetime.utcnow(),
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_io={
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                process_count=process_count,
                thread_count=thread_count
            )
            
        except Exception as e:
            logger.error(f"Error getting performance snapshot: {e}")
            return PerformanceSnapshot(
                timestamp=datetime.utcnow(),
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                network_io={},
                process_count=0,
                thread_count=0
            )


class AlertManager:
    """Performance alert management"""
    
    def __init__(self):
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []
        self.alert_handlers: List[Callable] = []
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """Add a performance threshold"""
        self.thresholds[threshold.metric_name] = threshold
    
    def remove_threshold(self, metric_name: str):
        """Remove a performance threshold"""
        self.thresholds.pop(metric_name, None)
    
    def check_thresholds(self, metrics_collector: MetricsCollector):
        """Check all thresholds against current metrics"""
        for metric_name, threshold in self.thresholds.items():
            if not threshold.enabled:
                continue
            
            # Get latest metric value
            values = metrics_collector.get_metric_values(metric_name)
            if not values:
                continue
            
            latest_value = values[-1]
            
            # Check threshold
            alert_severity = self._evaluate_threshold(latest_value.value, threshold)
            
            if alert_severity:
                self._trigger_alert(metric_name, latest_value, threshold, alert_severity)
            else:
                self._resolve_alert(metric_name)
    
    def _evaluate_threshold(self, value: float, threshold: PerformanceThreshold) -> Optional[AlertSeverity]:
        """Evaluate value against threshold"""
        triggered = False
        severity = None
        
        if threshold.comparison == "greater_than":
            if value >= threshold.critical_threshold:
                triggered = True
                severity = AlertSeverity.CRITICAL
            elif value >= threshold.warning_threshold:
                triggered = True
                severity = AlertSeverity.WARNING
        elif threshold.comparison == "less_than":
            if value <= threshold.critical_threshold:
                triggered = True
                severity = AlertSeverity.CRITICAL
            elif value <= threshold.warning_threshold:
                triggered = True
                severity = AlertSeverity.WARNING
        
        return severity if triggered else None
    
    def _trigger_alert(self, metric_name: str, metric_value: MetricValue, 
                      threshold: PerformanceThreshold, severity: AlertSeverity):
        """Trigger a performance alert"""
        import uuid
        
        alert_id = str(uuid.uuid4())
        
        # Check if alert already exists
        if metric_name in self.active_alerts:
            existing_alert = self.active_alerts[metric_name]
            if existing_alert.severity == severity:
                return  # Same severity, don't duplicate
        
        threshold_value = threshold.warning_threshold
        if severity == AlertSeverity.CRITICAL:
            threshold_value = threshold.critical_threshold
        
        alert = PerformanceAlert(
            alert_id=alert_id,
            metric_name=metric_name,
            severity=severity,
            message=f"{metric_name} {severity.value}: {metric_value.value} (threshold: {threshold_value})",
            current_value=metric_value.value,
            threshold_value=threshold_value,
            triggered_at=metric_value.timestamp,
            labels=metric_value.labels,
            metadata=threshold.__dict__
        )
        
        self.active_alerts[metric_name] = alert
        self.alert_history.append(alert)
        
        # Notify handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    def _resolve_alert(self, metric_name: str):
        """Resolve a performance alert"""
        if metric_name in self.active_alerts:
            alert = self.active_alerts[metric_name]
            alert.resolved_at = datetime.utcnow()
            del self.active_alerts[metric_name]
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[PerformanceAlert]:
        """Get alert history"""
        return self.alert_history[-limit:]
    
    def add_alert_handler(self, handler: Callable):
        """Add an alert handler"""
        self.alert_handlers.append(handler)


class PerformanceMonitor:
    """
    Comprehensive performance monitor for integration system
    """
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.system_monitor = SystemMonitor()
        self.alert_manager = AlertManager()
        self.is_monitoring = False
        self.monitoring_interval = 30  # seconds
        self._monitoring_task = None
        
        # Register default metrics
        self._register_default_metrics()
        self._setup_default_thresholds()
    
    def _register_default_metrics(self):
        """Register default performance metrics"""
        default_metrics = [
            MetricDefinition("system.cpu.usage", MetricType.GAUGE, "CPU usage percentage", "percent"),
            MetricDefinition("system.memory.usage", MetricType.GAUGE, "Memory usage percentage", "percent"),
            MetricDefinition("system.disk.usage", MetricType.GAUGE, "Disk usage percentage", "percent"),
            MetricDefinition("system.network.bytes_sent", MetricType.COUNTER, "Network bytes sent", "bytes"),
            MetricDefinition("system.network.bytes_recv", MetricType.COUNTER, "Network bytes received", "bytes"),
            MetricDefinition("integration.request.count", MetricType.COUNTER, "Integration request count", "count"),
            MetricDefinition("integration.request.duration", MetricType.HISTOGRAM, "Integration request duration", "seconds"),
            MetricDefinition("integration.error.count", MetricType.COUNTER, "Integration error count", "count"),
            MetricDefinition("integration.success.rate", MetricType.GAUGE, "Integration success rate", "percent"),
        ]
        
        for metric in default_metrics:
            self.metrics_collector.register_metric(metric)
    
    def _setup_default_thresholds(self):
        """Setup default performance thresholds"""
        default_thresholds = [
            PerformanceThreshold("system.cpu.usage", 70.0, 90.0, "greater_than"),
            PerformanceThreshold("system.memory.usage", 80.0, 95.0, "greater_than"),
            PerformanceThreshold("system.disk.usage", 80.0, 95.0, "greater_than"),
            PerformanceThreshold("integration.success.rate", 95.0, 90.0, "less_than"),
        ]
        
        for threshold in default_thresholds:
            self.alert_manager.add_threshold(threshold)
    
    async def start_monitoring(self):
        """Start performance monitoring"""
        if self.is_monitoring:
            return
        
        try:
            # Start system monitoring
            self.system_monitor.start_monitoring(self.metrics_collector)
            
            # Start periodic monitoring
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            self.is_monitoring = True
            logger.info("Performance monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start performance monitoring: {e}")
            raise PerformanceMonitorException(f"Failed to start monitoring: {e}")
    
    async def stop_monitoring(self):
        """Stop performance monitoring"""
        if not self.is_monitoring:
            return
        
        try:
            # Stop system monitoring
            self.system_monitor.stop_monitoring()
            
            # Stop periodic monitoring
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            self.is_monitoring = False
            logger.info("Performance monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping performance monitoring: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Check thresholds
                self.alert_manager.check_thresholds(self.metrics_collector)
                
                # Clean up old metrics
                self.metrics_collector.cleanup_old_metrics()
                
                # Wait for next iteration
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    def record_metric(self, metric_name: str, value: float,
                     labels: Optional[Dict[str, str]] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """Record a custom metric"""
        self.metrics_collector.add_metric_value(metric_name, value, labels, metadata)
    
    def record_request(self, operation: str, duration: float, success: bool = True,
                      labels: Optional[Dict[str, str]] = None):
        """Record an integration request"""
        request_labels = {"operation": operation}
        if labels:
            request_labels.update(labels)
        
        # Record request count
        self.record_metric("integration.request.count", 1, request_labels)
        
        # Record request duration
        self.record_metric("integration.request.duration", duration, request_labels)
        
        # Record success/error
        if success:
            self.record_metric("integration.success.count", 1, request_labels)
        else:
            self.record_metric("integration.error.count", 1, request_labels)
    
    def get_performance_report(self, start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> PerformanceReport:
        """Generate performance report"""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.utcnow()
        
        # Get metrics summary
        metrics_summary = {}
        for metric_name in self.metrics_collector.metric_definitions:
            stats = self.metrics_collector.get_metric_stats(metric_name, start_time, end_time)
            if stats:
                metrics_summary[metric_name] = stats
        
        # Get alerts in time range
        alerts = [
            alert for alert in self.alert_manager.alert_history
            if start_time <= alert.triggered_at <= end_time
        ]
        
        # Determine performance level
        performance_level = self._calculate_performance_level(metrics_summary, alerts)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics_summary, alerts)
        
        return PerformanceReport(
            start_time=start_time,
            end_time=end_time,
            performance_level=performance_level,
            metrics_summary=metrics_summary,
            alerts=alerts,
            recommendations=recommendations
        )
    
    def _calculate_performance_level(self, metrics_summary: Dict[str, Dict[str, float]],
                                    alerts: List[PerformanceAlert]) -> PerformanceLevel:
        """Calculate overall performance level"""
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
        
        if critical_alerts:
            return PerformanceLevel.CRITICAL
        elif warning_alerts:
            return PerformanceLevel.POOR
        
        # Check key metrics
        cpu_usage = metrics_summary.get("system.cpu.usage", {}).get("avg", 0)
        memory_usage = metrics_summary.get("system.memory.usage", {}).get("avg", 0)
        success_rate = metrics_summary.get("integration.success.rate", {}).get("avg", 100)
        
        if cpu_usage > 80 or memory_usage > 85 or success_rate < 95:
            return PerformanceLevel.FAIR
        elif cpu_usage > 60 or memory_usage > 70 or success_rate < 98:
            return PerformanceLevel.GOOD
        else:
            return PerformanceLevel.EXCELLENT
    
    def _generate_recommendations(self, metrics_summary: Dict[str, Dict[str, float]],
                                 alerts: List[PerformanceAlert]) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        cpu_usage = metrics_summary.get("system.cpu.usage", {}).get("avg", 0)
        memory_usage = metrics_summary.get("system.memory.usage", {}).get("avg", 0)
        disk_usage = metrics_summary.get("system.disk.usage", {}).get("avg", 0)
        
        if cpu_usage > 80:
            recommendations.append("High CPU usage detected. Consider optimizing code or scaling horizontally.")
        elif cpu_usage > 60:
            recommendations.append("Moderate CPU usage. Monitor for potential optimization opportunities.")
        
        if memory_usage > 85:
            recommendations.append("High memory usage detected. Check for memory leaks or increase available memory.")
        elif memory_usage > 70:
            recommendations.append("Moderate memory usage. Consider memory optimization.")
        
        if disk_usage > 85:
            recommendations.append("High disk usage detected. Clean up old files or expand storage.")
        
        error_count = metrics_summary.get("integration.error.count", {}).get("sum", 0)
        if error_count > 0:
            recommendations.append(f"{error_count} integration errors detected. Review error logs and implement error handling.")
        
        if len(alerts) > 0:
            recommendations.append(f"{len(alerts)} performance alerts triggered. Review alert configuration and system performance.")
        
        return recommendations
    
    def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot"""
        snapshot = self.system_monitor.get_current_snapshot()
        
        # Add custom metrics
        for metric_name in self.metrics_collector.metric_definitions:
            values = self.metrics_collector.get_metric_values(metric_name)
            if values:
                snapshot.custom_metrics[metric_name] = values[-1]
        
        return snapshot
    
    def get_metrics_summary(self, metric_names: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        """Get metrics summary"""
        if not metric_names:
            metric_names = list(self.metrics_collector.metric_definitions.keys())
        
        summary = {}
        for metric_name in metric_names:
            stats = self.metrics_collector.get_metric_stats(metric_name)
            if stats:
                summary[metric_name] = stats
        
        return summary
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get active alerts"""
        return self.alert_manager.get_active_alerts()
    
    def add_custom_threshold(self, metric_name: str, warning_threshold: float,
                           critical_threshold: float, comparison: str = "greater_than"):
        """Add custom performance threshold"""
        threshold = PerformanceThreshold(
            metric_name=metric_name,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            comparison=comparison
        )
        self.alert_manager.add_threshold(threshold)
    
    def add_alert_handler(self, handler: Callable):
        """Add custom alert handler"""
        self.alert_manager.add_alert_handler(handler)


# Global performance monitor instance
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def initialize_performance_monitor() -> PerformanceMonitor:
    """Initialize the global performance monitor"""
    global _performance_monitor
    _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# Export main classes and functions
__all__ = [
    'PerformanceMonitor',
    'MetricsCollector',
    'SystemMonitor',
    'AlertManager',
    'MetricValue',
    'MetricDefinition',
    'PerformanceThreshold',
    'PerformanceAlert',
    'PerformanceSnapshot',
    'PerformanceReport',
    'MetricType',
    'AlertSeverity',
    'PerformanceLevel',
    'get_performance_monitor',
    'initialize_performance_monitor',
]
