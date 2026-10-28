"""
Performance Monitor Module
Performance monitoring for integration system
"""

import logging
import time
import psutil
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import MonitoringLevel

User = get_user_model()
logger = logging.getLogger('security.integration.performance_monitor')


class PerformanceMetric:
    """Performance metric"""
    
    def __init__(self, name: str, unit: str, description: str = ""):
        self.name = name
        self.unit = unit
        self.description = description
        self.values = []
        self.max_values = 1000
        self.created_at = timezone.now()
        self.last_updated = timezone.now()
    
    def add_value(self, value: float, timestamp: datetime = None):
        """Add metric value"""
        if timestamp is None:
            timestamp = timezone.now()
        
        self.values.append({
            'value': value,
            'timestamp': timestamp
        })
        
        # Maintain max values
        if len(self.values) > self.max_values:
            self.values.pop(0)
        
        self.last_updated = timestamp
    
    def get_latest_value(self) -> Optional[float]:
        """Get latest value"""
        if self.values:
            return self.values[-1]['value']
        return None
    
    def get_average(self, minutes: int = 5) -> Optional[float]:
        """Get average value for last N minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_values = [v['value'] for v in self.values if v['timestamp'] >= cutoff_time]
        
        if recent_values:
            return sum(recent_values) / len(recent_values)
        
        return None
    
    def get_max(self, minutes: int = 5) -> Optional[float]:
        """Get max value for last N minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_values = [v['value'] for v in self.values if v['timestamp'] >= cutoff_time]
        
        if recent_values:
            return max(recent_values)
        
        return None
    
    def get_min(self, minutes: int = 5) -> Optional[float]:
        """Get min value for last N minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_values = [v['value'] for v in self.values if v['timestamp'] >= cutoff_time]
        
        if recent_values:
            return min(recent_values)
        
        return None
    
    def get_percentile(self, percentile: float, minutes: int = 5) -> Optional[float]:
        """Get percentile value for last N minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_values = [v['value'] for v in self.values if v['timestamp'] >= cutoff_time]
        
        if recent_values:
            sorted_values = sorted(recent_values)
            index = int(len(sorted_values) * (percentile / 100))
            return sorted_values[min(index, len(sorted_values) - 1)]
        
        return None
    
    def clear_values(self):
        """Clear all values"""
        self.values.clear()
        self.last_updated = timezone.now()


class PerformanceMonitor:
    """Performance monitor for integration system"""
    
    def __init__(self, name: str):
        self.name = name
        self.metrics = {}
        self.enabled = True
        self.monitoring_level = MonitoringLevel.INFO
        self.collection_interval = 60  # seconds
        self.alert_thresholds = {}
        self.last_collection = timezone.now()
        self.statistics = {
            'collections': 0,
            'alerts_triggered': 0,
            'last_alert': None
        }
    
    def add_metric(self, metric: PerformanceMetric):
        """Add performance metric"""
        self.metrics[metric.name] = metric
        logger.info(f"Added performance metric: {metric.name}")
    
    def remove_metric(self, metric_name: str) -> bool:
        """Remove performance metric"""
        if metric_name in self.metrics:
            del self.metrics[metric_name]
            logger.info(f"Removed performance metric: {metric_name}")
            return True
        return False
    
    def get_metric(self, metric_name: str) -> Optional[PerformanceMetric]:
        """Get metric by name"""
        return self.metrics.get(metric_name)
    
    def record_metric(self, metric_name: str, value: float, timestamp: datetime = None):
        """Record metric value"""
        if not self.enabled:
            return
        
        metric = self.get_metric(metric_name)
        if metric:
            metric.add_value(value, timestamp)
            
            # Check alert thresholds
            self._check_alert_thresholds(metric_name, value)
    
    def _check_alert_thresholds(self, metric_name: str, value: float):
        """Check if alert thresholds are exceeded"""
        thresholds = self.alert_thresholds.get(metric_name, {})
        
        # Check max threshold
        if 'max' in thresholds and value > thresholds['max']:
            self._trigger_alert(metric_name, 'max_threshold', value, thresholds['max'])
        
        # Check min threshold
        if 'min' in thresholds and value < thresholds['min']:
            self._trigger_alert(metric_name, 'min_threshold', value, thresholds['min'])
    
    def _trigger_alert(self, metric_name: str, alert_type: str, value: float, threshold: float):
        """Trigger performance alert"""
        self.statistics['alerts_triggered'] += 1
        self.statistics['last_alert'] = timezone.now()
        
        # Create security incident for critical alerts
        if alert_type == 'max_threshold' and value > threshold * 2:
            SecurityIncident.objects.create(
                title=f"Performance Alert: {metric_name}",
                incident_type='performance_issue',
                severity='high',
                priority='medium',
                description=f"Performance metric {metric_name} exceeded threshold: {value} > {threshold}",
                metadata={
                    'metric_name': metric_name,
                    'alert_type': alert_type,
                    'value': value,
                    'threshold': threshold,
                    'monitor': self.name
                }
            )
        
        # Log performance alert
        SecurityLog.objects.create(
            security_type='performance_alert',
            severity='warning',
            description=f"Performance alert: {metric_name} - {alert_type}",
            metadata={
                'metric_name': metric_name,
                'alert_type': alert_type,
                'value': value,
                'threshold': threshold,
                'monitor': self.name
            }
        )
        
        logger.warning(f"Performance alert triggered: {metric_name} {alert_type} - {value} > {threshold}")
    
    def set_alert_threshold(self, metric_name: str, min_threshold: float = None, 
                           max_threshold: float = None):
        """Set alert threshold for metric"""
        if metric_name not in self.alert_thresholds:
            self.alert_thresholds[metric_name] = {}
        
        if min_threshold is not None:
            self.alert_thresholds[metric_name]['min'] = min_threshold
        
        if max_threshold is not None:
            self.alert_thresholds[metric_name]['max'] = max_threshold
        
        logger.info(f"Set alert threshold for {metric_name}: min={min_threshold}, max={max_threshold}")
    
    def collect_system_metrics(self):
        """Collect system metrics"""
        if not self.enabled:
            return
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric('cpu_usage', cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric('memory_usage', memory.percent)
            self.record_metric('memory_available_gb', memory.available / (1024**3))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.record_metric('disk_usage', disk.percent)
            self.record_metric('disk_free_gb', disk.free / (1024**3))
            
            # Network I/O
            network = psutil.net_io_counters()
            self.record_metric('network_bytes_sent', network.bytes_sent)
            self.record_metric('network_bytes_recv', network.bytes_recv)
            
            # Process count
            process_count = len(psutil.pids())
            self.record_metric('process_count', process_count)
            
            self.statistics['collections'] += 1
            self.last_collection = timezone.now()
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def get_metrics_summary(self, minutes: int = 5) -> Dict[str, Any]:
        """Get metrics summary for last N minutes"""
        summary = {}
        
        for metric_name, metric in self.metrics.items():
            summary[metric_name] = {
                'latest': metric.get_latest_value(),
                'average': metric.get_average(minutes),
                'min': metric.get_min(minutes),
                'max': metric.get_max(minutes),
                'p95': metric.get_percentile(95, minutes),
                'p99': metric.get_percentile(99, minutes),
                'unit': metric.unit,
                'description': metric.description
            }
        
        return summary
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            'monitor_name': self.name,
            'enabled': self.enabled,
            'monitoring_level': self.monitoring_level.value,
            'collection_interval': self.collection_interval,
            'last_collection': self.last_collection.isoformat(),
            'statistics': self.statistics,
            'metrics_count': len(self.metrics),
            'alert_thresholds_count': len(self.alert_thresholds),
            'metrics_summary': self.get_metrics_summary(60),  # Last hour
            'alert_thresholds': self.alert_thresholds
        }
    
    def enable(self):
        """Enable performance monitor"""
        self.enabled = True
        logger.info(f"Performance monitor {self.name} enabled")
    
    def disable(self):
        """Disable performance monitor"""
        self.enabled = False
        logger.info(f"Performance monitor {self.name} disabled")
    
    def clear_all_metrics(self):
        """Clear all metrics"""
        for metric in self.metrics.values():
            metric.clear_values()
        
        logger.info(f"Cleared all metrics for monitor {self.name}")


class IntegrationPerformanceMonitor(PerformanceMonitor):
    """Performance monitor for integration system"""
    
    def __init__(self):
        super().__init__("integration_performance")
        
        # Create integration-specific metrics
        self._create_integration_metrics()
        
        # Set default alert thresholds
        self._set_default_thresholds()
    
    def _create_integration_metrics(self):
        """Create integration-specific metrics"""
        metrics = [
            PerformanceMetric('request_count', 'count', 'Number of requests'),
            PerformanceMetric('response_time', 'ms', 'Response time in milliseconds'),
            PerformanceMetric('error_rate', 'percent', 'Error rate percentage'),
            PerformanceMetric('throughput', 'requests/sec', 'Requests per second'),
            PerformanceMetric('queue_size', 'count', 'Queue size'),
            PerformanceMetric('connection_pool_active', 'count', 'Active connections'),
            PerformanceMetric('connection_pool_idle', 'count', 'Idle connections'),
            PerformanceMetric('cache_hit_rate', 'percent', 'Cache hit rate'),
            PerformanceMetric('database_query_time', 'ms', 'Database query time'),
            PerformanceMetric('api_response_time', 'ms', 'API response time'),
            PerformanceMetric('webhook_success_rate', 'percent', 'Webhook success rate'),
            PerformanceMetric('data_sync_latency', 'ms', 'Data sync latency'),
            PerformanceMetric('message_processing_rate', 'msg/sec', 'Message processing rate'),
            PerformanceMetric('circuit_breaker_trips', 'count', 'Circuit breaker trips'),
            PerformanceMetric('retry_attempts', 'count', 'Retry attempts'),
            PerformanceMetric('fallback_activations', 'count', 'Fallback activations')
        ]
        
        for metric in metrics:
            self.add_metric(metric)
    
    def _set_default_thresholds(self):
        """Set default alert thresholds"""
        thresholds = {
            'response_time': {'max': 5000},  # 5 seconds
            'error_rate': {'max': 10},  # 10%
            'cpu_usage': {'max': 80},  # 80%
            'memory_usage': {'max': 85},  # 85%
            'disk_usage': {'max': 90},  # 90%
            'queue_size': {'max': 1000},
            'database_query_time': {'max': 1000},  # 1 second
            'api_response_time': {'max': 10000},  # 10 seconds
            'webhook_success_rate': {'min': 90},  # 90%
            'cache_hit_rate': {'min': 80},  # 80%
        }
        
        for metric_name, threshold_config in thresholds.items():
            self.set_alert_threshold(metric_name, **threshold_config)
    
    def record_request(self, response_time: float, success: bool = True):
        """Record request metrics"""
        self.record_metric('request_count', 1)
        self.record_metric('response_time', response_time)
        
        # Update error rate (simplified)
        current_avg = self.get_metric('error_rate').get_average(1) or 0
        if not success:
            new_error_rate = (current_avg * 9 + 100) / 10  # Weighted average
        else:
            new_error_rate = current_avg * 0.9  # Decay
        
        self.record_metric('error_rate', new_error_rate)
    
    def record_webhook(self, success: bool):
        """Record webhook metrics"""
        current_avg = self.get_metric('webhook_success_rate').get_average(1) or 0
        if success:
            new_rate = (current_avg * 9 + 100) / 10  # Weighted average
        else:
            new_rate = current_avg * 0.9  # Decay
        
        self.record_metric('webhook_success_rate', new_rate)
    
    def record_cache_operation(self, hit: bool):
        """Record cache operation"""
        current_avg = self.get_metric('cache_hit_rate').get_average(1) or 0
        if hit:
            new_rate = (current_avg * 9 + 100) / 10  # Weighted average
        else:
            new_rate = current_avg * 0.9  # Decay
        
        self.record_metric('cache_hit_rate', new_rate)
    
    def record_circuit_breaker_trip(self):
        """Record circuit breaker trip"""
        self.record_metric('circuit_breaker_trips', 1)
    
    def record_retry_attempt(self):
        """Record retry attempt"""
        self.record_metric('retry_attempts', 1)
    
    def record_fallback_activation(self):
        """Record fallback activation"""
        self.record_metric('fallback_activations', 1)


class PerformanceMonitorManager:
    """Manager for multiple performance monitors"""
    
    def __init__(self):
        self.monitors = {}
        self.enabled = True
        self.global_alert_thresholds = {}
        self.collection_scheduler = None
    
    def create_monitor(self, monitor_name: str) -> PerformanceMonitor:
        """Create performance monitor"""
        monitor = PerformanceMonitor(monitor_name)
        self.monitors[monitor_name] = monitor
        logger.info(f"Created performance monitor: {monitor_name}")
        return monitor
    
    def remove_monitor(self, monitor_name: str) -> bool:
        """Remove performance monitor"""
        if monitor_name in self.monitors:
            del self.monitors[monitor_name]
            logger.info(f"Removed performance monitor: {monitor_name}")
            return True
        return False
    
    def get_monitor(self, monitor_name: str) -> Optional[PerformanceMonitor]:
        """Get monitor by name"""
        return self.monitors.get(monitor_name)
    
    def collect_all_metrics(self):
        """Collect metrics from all monitors"""
        for monitor in self.monitors.values():
            monitor.collect_system_metrics()
    
    def get_all_reports(self) -> Dict[str, Any]:
        """Get reports from all monitors"""
        return {
            'enabled': self.enabled,
            'total_monitors': len(self.monitors),
            'monitors': {
                name: monitor.get_performance_report()
                for name, monitor in self.monitors.items()
            }
        }
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get system overview"""
        overview = {
            'total_monitors': len(self.monitors),
            'enabled_monitors': len([m for m in self.monitors.values() if m.enabled]),
            'total_metrics': sum(len(m.metrics) for m in self.monitors.values()),
            'total_alerts': sum(m.statistics['alerts_triggered'] for m in self.monitors.values())
        }
        
        # Aggregate common metrics
        common_metrics = ['cpu_usage', 'memory_usage', 'response_time', 'error_rate']
        
        for metric_name in common_metrics:
            values = []
            for monitor in self.monitors.values():
                metric = monitor.get_metric(metric_name)
                if metric:
                    latest = metric.get_latest_value()
                    if latest is not None:
                        values.append(latest)
            
            if values:
                overview[f'avg_{metric_name}'] = sum(values) / len(values)
                overview[f'max_{metric_name}'] = max(values)
                overview[f'min_{metric_name}'] = min(values)
        
        return overview
    
    def enable_all_monitors(self):
        """Enable all monitors"""
        for monitor in self.monitors.values():
            monitor.enable()
    
    def disable_all_monitors(self):
        """Disable all monitors"""
        for monitor in self.monitors.values():
            monitor.disable()
    
    def clear_all_metrics(self):
        """Clear all metrics"""
        for monitor in self.monitors.values():
            monitor.clear_all_metrics()
    
    def enable(self):
        """Enable monitor manager"""
        self.enabled = True
        logger.info("Performance monitor manager enabled")
    
    def disable(self):
        """Disable monitor manager"""
        self.enabled = False
        logger.info("Performance monitor manager disabled")


# Global monitor manager
performance_monitor_manager = PerformanceMonitorManager()

# Create integration performance monitor
integration_performance_monitor = IntegrationPerformanceMonitor()
performance_monitor_manager.monitors['integration'] = integration_performance_monitor


# Export symbols
__all__ = [
    'PerformanceMetric',
    'PerformanceMonitor',
    'IntegrationPerformanceMonitor',
    'PerformanceMonitorManager',
    'performance_monitor_manager',
    'integration_performance_monitor'
]