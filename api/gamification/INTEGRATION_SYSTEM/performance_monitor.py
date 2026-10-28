"""
Performance Monitor — System performance monitoring and metrics collection.

This module provides comprehensive performance monitoring capabilities
for tracking system performance, resource usage, and integration metrics.
"""

from __future__ import annotations

import logging
import threading
import time
import psutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum
from collections import defaultdict, deque

from .integ_constants import ErrorCode
from .integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Performance Monitoring Types
# ---------------------------------------------------------------------------

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


class ResourceCategory(Enum):
    """Resource category enumeration."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    APPLICATION = "application"
    INTEGRATION = "integration"


# ---------------------------------------------------------------------------
# Performance Data Classes
# ---------------------------------------------------------------------------

@dataclass
class MetricValue:
    """Metric value with timestamp."""
    
    name: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "unit": self.unit
        }


@dataclass
class PerformanceMetric:
    """Performance metric definition."""
    
    name: str
    metric_type: MetricType
    description: str = ""
    category: ResourceCategory = ResourceCategory.APPLICATION
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "description": self.description,
            "category": self.category.value,
            "enabled": self.enabled,
            "labels": self.labels,
            "thresholds": self.thresholds
        }


@dataclass
class AlertRule:
    """Alert rule definition."""
    
    id: str
    name: str
    metric_name: str
    condition: str  # e.g., ">", "<", ">=", "<=", "==", "!="
    threshold: float
    severity: AlertSeverity
    duration: float = 60.0  # seconds
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    action: Optional[Callable] = None
    
    def evaluate(self, metric_value: float) -> bool:
        """Evaluate alert condition."""
        if self.condition == ">":
            return metric_value > self.threshold
        elif self.condition == "<":
            return metric_value < self.threshold
        elif self.condition == ">=":
            return metric_value >= self.threshold
        elif self.condition == "<=":
            return metric_value <= self.threshold
        elif self.condition == "==":
            return metric_value == self.threshold
        elif self.condition == "!=":
            return metric_value != self.threshold
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "duration": self.duration,
            "enabled": self.enabled,
            "labels": self.labels
        }


@dataclass
class Alert:
    """Alert instance."""
    
    id: str
    rule_id: str
    metric_name: str
    severity: AlertSeverity
    message: str
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    value: float = 0.0
    threshold: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if alert is active."""
        return self.resolved_at is None
    
    def resolve(self) -> None:
        """Resolve the alert."""
        self.resolved_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "metric_name": self.metric_name,
            "severity": self.severity.value,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "is_active": self.is_active(),
            "value": self.value,
            "threshold": self.threshold,
            "labels": self.labels
        }


@dataclass
class SystemMetrics:
    """System resource metrics."""
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    load_average: List[float] = field(default_factory=list)
    process_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_mb": self.memory_used_mb,
            "memory_available_mb": self.memory_available_mb,
            "disk_usage_percent": self.disk_usage_percent,
            "disk_used_gb": self.disk_used_gb,
            "disk_free_gb": self.disk_free_gb,
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "load_average": self.load_average,
            "process_count": self.process_count
        }


# ---------------------------------------------------------------------------
# Abstract Metric Collector
# ---------------------------------------------------------------------------

class BaseMetricCollector(ABC):
    """Abstract base class for metric collectors."""
    
    @abstractmethod
    def collect(self) -> List[MetricValue]:
        """Collect metrics."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> List[PerformanceMetric]:
        """Get metric definitions."""
        pass


# ---------------------------------------------------------------------------
# Built-in Metric Collectors
# ---------------------------------------------------------------------------

class SystemMetricCollector(BaseMetricCollector):
    """Collector for system metrics."""
    
    def collect(self) -> List[MetricValue]:
        """Collect system metrics."""
        metrics = []
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(MetricValue(
                name="system_cpu_percent",
                value=cpu_percent,
                unit="percent",
                category=ResourceCategory.CPU
            ))
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.append(MetricValue(
                name="system_memory_percent",
                value=memory.percent,
                unit="percent",
                category=ResourceCategory.MEMORY
            ))
            metrics.append(MetricValue(
                name="system_memory_used_mb",
                value=memory.used / 1024 / 1024,
                unit="MB",
                category=ResourceCategory.MEMORY
            ))
            metrics.append(MetricValue(
                name="system_memory_available_mb",
                value=memory.available / 1024 / 1024,
                unit="MB",
                category=ResourceCategory.MEMORY
            ))
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics.append(MetricValue(
                name="system_disk_usage_percent",
                value=disk.percent,
                unit="percent",
                category=ResourceCategory.DISK
            ))
            metrics.append(MetricValue(
                name="system_disk_used_gb",
                value=disk.used / 1024 / 1024 / 1024,
                unit="GB",
                category=ResourceCategory.DISK
            ))
            metrics.append(MetricValue(
                name="system_disk_free_gb",
                value=disk.free / 1024 / 1024 / 1024,
                unit="GB",
                category=ResourceCategory.DISK
            ))
            
            # Network metrics
            network = psutil.net_io_counters()
            metrics.append(MetricValue(
                name="system_network_bytes_sent",
                value=network.bytes_sent,
                unit="bytes",
                category=ResourceCategory.NETWORK
            ))
            metrics.append(MetricValue(
                name="system_network_bytes_recv",
                value=network.bytes_recv,
                unit="bytes",
                category=ResourceCategory.NETWORK
            ))
            
            # Process count
            process_count = len(psutil.pids())
            metrics.append(MetricValue(
                name="system_process_count",
                value=process_count,
                unit="count",
                category=ResourceCategory.APPLICATION
            ))
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def get_metrics(self) -> List[PerformanceMetric]:
        """Get system metric definitions."""
        return [
            PerformanceMetric(
                name="system_cpu_percent",
                metric_type=MetricType.GAUGE,
                description="CPU usage percentage",
                category=ResourceCategory.CPU,
                thresholds={"warning": 80.0, "critical": 95.0}
            ),
            PerformanceMetric(
                name="system_memory_percent",
                metric_type=MetricType.GAUGE,
                description="Memory usage percentage",
                category=ResourceCategory.MEMORY,
                thresholds={"warning": 80.0, "critical": 95.0}
            ),
            PerformanceMetric(
                name="system_disk_usage_percent",
                metric_type=MetricType.GAUGE,
                description="Disk usage percentage",
                category=ResourceCategory.DISK,
                thresholds={"warning": 80.0, "critical": 95.0}
            )
        ]


class IntegrationMetricCollector(BaseMetricCollector):
    """Collector for integration metrics."""
    
    def __init__(self):
        self.metrics_store: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def collect(self) -> List[MetricValue]:
        """Collect integration metrics."""
        metrics = []
        
        # This would collect actual integration metrics
        # For now, we'll return empty metrics
        return metrics
    
    def get_metrics(self) -> List[PerformanceMetric]:
        """Get integration metric definitions."""
        return [
            PerformanceMetric(
                name="integration_request_count",
                metric_type=MetricType.COUNTER,
                description="Total number of integration requests",
                category=ResourceCategory.INTEGRATION
            ),
            PerformanceMetric(
                name="integration_response_time",
                metric_type=MetricType.TIMER,
                description="Integration response time",
                category=ResourceCategory.INTEGRATION,
                thresholds={"warning": 5.0, "critical": 10.0}
            ),
            PerformanceMetric(
                name="integration_error_rate",
                metric_type=MetricType.GAUGE,
                description="Integration error rate",
                category=ResourceCategory.INTEGRATION,
                thresholds={"warning": 0.05, "critical": 0.10}
            )
        ]
    
    def record_request(self, integration_name: str, response_time: float, success: bool) -> None:
        """Record integration request."""
        timestamp = time.time()
        
        # Record request count
        self.metrics_store[f"{integration_name}_request_count"].append(timestamp)
        
        # Record response time
        self.metrics_store[f"{integration_name}_response_time"].append(response_time)
        
        # Record error
        if not success:
            self.metrics_store[f"{integration_name}_error_count"].append(timestamp)


# ---------------------------------------------------------------------------
# Performance Monitor Implementation
# ---------------------------------------------------------------------------

class PerformanceMonitor:
    """Main performance monitoring system."""
    
    def __init__(self, collection_interval: float = 30.0):
        self.collection_interval = collection_interval
        self.collectors: List[BaseMetricCollector] = []
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._running = False
        self._collection_thread: Optional[threading.Thread] = None
        
        # Register built-in collectors
        self.register_collector(SystemMetricCollector())
        self.register_collector(IntegrationMetricCollector())
    
    def start(self) -> None:
        """Start performance monitoring."""
        if self._running:
            return
        
        self._running = True
        self._collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collection_thread.start()
        
        self.logger.info("Performance monitor started")
    
    def stop(self) -> None:
        """Stop performance monitoring."""
        self._running = False
        
        if self._collection_thread:
            self._collection_thread.join(timeout=5.0)
        
        self.logger.info("Performance monitor stopped")
    
    def register_collector(self, collector: BaseMetricCollector) -> None:
        """Register a metric collector."""
        with self._lock:
            self.collectors.append(collector)
            self.logger.info(f"Registered metric collector: {collector.__class__.__name__}")
    
    def register_alert_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        with self._lock:
            self.alert_rules[rule.id] = rule
            self.logger.info(f"Registered alert rule: {rule.id}")
    
    def unregister_alert_rule(self, rule_id: str) -> bool:
        """Unregister an alert rule."""
        with self._lock:
            if rule_id in self.alert_rules:
                del self.alert_rules[rule_id]
                # Resolve any active alerts for this rule
                if rule_id in self.active_alerts:
                    self.active_alerts[rule_id].resolve()
                    del self.active_alerts[rule_id]
                
                self.logger.info(f"Unregistered alert rule: {rule_id}")
                return True
            return False
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a metric value."""
        with self._lock:
            metric = MetricValue(
                name=name,
                value=value,
                labels=labels or {}
            )
            
            self.metrics[name].append(metric)
    
    def get_metric_values(self, metric_name: str, since: Optional[datetime] = None) -> List[MetricValue]:
        """Get metric values."""
        with self._lock:
            values = list(self.metrics.get(metric_name, []))
            
            if since:
                values = [v for v in values if v.timestamp >= since]
            
            return values
    
    def get_metric_summary(self, metric_name: str, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get metric summary."""
        values = self.get_metric_values(metric_name, since)
        
        if not values:
            return {"count": 0}
        
        numeric_values = [v.value for v in values]
        
        return {
            "count": len(values),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values),
            "latest": values[-1].value,
            "latest_timestamp": values[-1].timestamp.isoformat()
        }
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            process_count = len(psutil.pids())
            
            # Get load average (Unix-like systems)
            load_average = []
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                pass
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_usage_percent=disk.percent,
                disk_used_gb=disk.used / 1024 / 1024 / 1024,
                disk_free_gb=disk.free / 1024 / 1024 / 1024,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                load_average=load_average,
                process_count=process_count
            )
            
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return SystemMetrics()
    
    def get_alerts(self, active_only: bool = False) -> List[Alert]:
        """Get alerts."""
        with self._lock:
            alerts = list(self.active_alerts.values())
            
            if active_only:
                alerts = [a for a in alerts if a.is_active()]
            
            return alerts
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._lock:
            if alert_id in self.active_alerts:
                self.active_alerts[alert_id].resolve()
                self.logger.info(f"Resolved alert: {alert_id}")
                return True
            return False
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate performance report."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        report = {
            "period_hours": hours,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system_metrics": self.get_system_metrics().to_dict(),
            "metrics_summary": {},
            "alerts": {
                "total": len(self.active_alerts),
                "active": len([a for a in self.active_alerts.values() if a.is_active()]),
                "by_severity": {}
            }
        }
        
        # Get metric summaries
        for collector in self.collectors:
            for metric in collector.get_metrics():
                if metric.enabled:
                    summary = self.get_metric_summary(metric.name, since)
                    report["metrics_summary"][metric.name] = summary
        
        # Get alert counts by severity
        for alert in self.active_alerts.values():
            severity = alert.severity.value
            report["alerts"]["by_severity"][severity] = report["alerts"]["by_severity"].get(severity, 0) + 1
        
        return report
    
    def _collection_loop(self) -> None:
        """Main collection loop."""
        while self._running:
            try:
                start_time = time.time()
                
                # Collect metrics from all collectors
                for collector in self.collectors:
                    try:
                        metric_values = collector.collect()
                        
                        for metric_value in metric_values:
                            self.metrics[metric_value.name].append(metric_value)
                        
                        # Check alert rules
                        self._check_alert_rules(metric_values)
                        
                    except Exception as e:
                        self.logger.error(f"Error collecting from {collector.__class__.__name__}: {e}")
                
                # Calculate collection time
                collection_time = time.time() - start_time
                self.record_metric("monitor_collection_time", collection_time)
                
                # Sleep until next collection
                sleep_time = max(0, self.collection_interval - collection_time)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")
                time.sleep(5)
    
    def _check_alert_rules(self, metric_values: List[MetricValue]) -> None:
        """Check alert rules against metric values."""
        for metric_value in metric_values:
            # Find matching alert rules
            matching_rules = [
                rule for rule in self.alert_rules.values()
                if rule.enabled and rule.metric_name == metric_value.name
            ]
            
            for rule in matching_rules:
                if rule.evaluate(metric_value.value):
                    self._trigger_alert(rule, metric_value)
                else:
                    # Check if we should resolve existing alert
                    existing_alert = self.active_alerts.get(rule.id)
                    if existing_alert and existing_alert.is_active():
                        existing_alert.resolve()
                        del self.active_alerts[rule.id]
    
    def _trigger_alert(self, rule: AlertRule, metric_value: MetricValue) -> None:
        """Trigger an alert."""
        import uuid
        
        # Check if alert is already active
        if rule.id in self.active_alerts:
            return
        
        alert = Alert(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            metric_name=rule.metric_name,
            severity=rule.severity,
            message=f"{rule.metric_name} {rule.condition} {rule.threshold} (current: {metric_value.value})",
            value=metric_value.value,
            threshold=rule.threshold,
            labels=rule.labels
        )
        
        self.active_alerts[rule.id] = alert
        
        # Execute alert action if defined
        if rule.action:
            try:
                rule.action(alert)
            except Exception as e:
                self.logger.error(f"Error executing alert action for {rule.id}: {e}")
        
        self.logger.warning(f"Alert triggered: {alert.message}")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a metric."""
    performance_monitor.record_metric(name, value, labels)


def get_system_metrics() -> SystemMetrics:
    """Get current system metrics."""
    return performance_monitor.get_system_metrics()


def create_alert_rule(
    rule_id: str,
    name: str,
    metric_name: str,
    condition: str,
    threshold: float,
    severity: AlertSeverity,
    **kwargs: Any
) -> AlertRule:
    """Create an alert rule."""
    rule = AlertRule(
        id=rule_id,
        name=name,
        metric_name=metric_name,
        condition=condition,
        threshold=threshold,
        severity=severity,
        **kwargs
    )
    
    performance_monitor.register_alert_rule(rule)
    return rule


# Initialize logging
logger.info("Performance monitor module initialized")
