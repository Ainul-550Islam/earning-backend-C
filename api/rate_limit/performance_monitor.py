# api/rate_limit/performance_monitor.py
"""
Performance monitoring system for rate limit module.

Provides comprehensive performance tracking and analysis.
"""

import logging
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


class PerformanceMetric:
    """Represents a performance metric."""
    
    def __init__(self, name: str, value: float, unit: str = '', 
                 tags: Dict[str, str] = None, timestamp: datetime = None):
        self.name = name
        self.value = value
        self.unit = unit
        self.tags = tags or {}
        self.timestamp = timestamp or timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat()
        }


class PerformanceThreshold:
    """Represents a performance threshold."""
    
    def __init__(self, metric_name: str, operator: str, threshold: float,
                 severity: str = 'warning', message: str = None):
        self.metric_name = metric_name
        self.operator = operator
        self.threshold = threshold
        self.severity = severity
        self.message = message or f"Metric {metric_name} {operator} {threshold}"
    
    def check(self, value: float) -> bool:
        """Check if threshold is exceeded."""
        if self.operator == '>':
            return value > self.threshold
        elif self.operator == '<':
            return value < self.threshold
        elif self.operator == '>=':
            return value >= self.threshold
        elif self.operator == '<=':
            return value <= self.threshold
        elif self.operator == '==':
            return value == self.threshold
        elif self.operator == '!=':
            return value != self.threshold
        else:
            return False


class PerformanceCollector:
    """Collects performance metrics."""
    
    def __init__(self, collection_interval: int = 60):
        self.collection_interval = collection_interval
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.is_collecting = False
        self.collection_thread = None
        self.collectors: Dict[str, Callable] = {}
        self._initialize_collectors()
    
    def _initialize_collectors(self):
        """Initialize default metric collectors."""
        self.collectors['system_cpu'] = self._collect_cpu_usage
        self.collectors['system_memory'] = self._collect_memory_usage
        self.collectors['system_disk'] = self._collect_disk_usage
        self.collectors['django_cache'] = self._collect_cache_metrics
        self.collectors['rate_limit'] = self._collect_rate_limit_metrics
    
    def _collect_cpu_usage(self) -> List[PerformanceMetric]:
        """Collect CPU usage metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            metrics = [
                PerformanceMetric('cpu_usage_percent', cpu_percent, '%'),
                PerformanceMetric('cpu_count', cpu_count, 'count')
            ]
            
            # Per-CPU usage
            per_cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            for i, percent in enumerate(per_cpu_percent):
                metrics.append(
                    PerformanceMetric(f'cpu_usage_percent_cpu_{i}', percent, '%', {'cpu': str(i)})
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect CPU metrics: {str(e)}")
            return []
    
    def _collect_memory_usage(self) -> List[PerformanceMetric]:
        """Collect memory usage metrics."""
        try:
            memory = psutil.virtual_memory()
            
            metrics = [
                PerformanceMetric('memory_total', memory.total, 'bytes'),
                PerformanceMetric('memory_available', memory.available, 'bytes'),
                PerformanceMetric('memory_used', memory.used, 'bytes'),
                PerformanceMetric('memory_percent', memory.percent, '%'),
                PerformanceMetric('memory_free', memory.free, 'bytes')
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {str(e)}")
            return []
    
    def _collect_disk_usage(self) -> List[PerformanceMetric]:
        """Collect disk usage metrics."""
        try:
            disk = psutil.disk_usage('/')
            
            metrics = [
                PerformanceMetric('disk_total', disk.total, 'bytes'),
                PerformanceMetric('disk_used', disk.used, 'bytes'),
                PerformanceMetric('disk_free', disk.free, 'bytes'),
                PerformanceMetric('disk_percent', (disk.used / disk.total) * 100, '%')
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect disk metrics: {str(e)}")
            return []
    
    def _collect_cache_metrics(self) -> List[PerformanceMetric]:
        """Collect Django cache metrics."""
        try:
            # Test cache performance
            start_time = time.time()
            cache.set('performance_test', 'test_value', timeout=60)
            cache_get_time = time.time() - start_time
            
            start_time = time.time()
            cache.get('performance_test')
            cache_set_time = time.time() - start_time
            
            metrics = [
                PerformanceMetric('cache_get_time', cache_get_time, 'seconds'),
                PerformanceMetric('cache_set_time', cache_set_time, 'seconds')
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {str(e)}")
            return []
    
    def _collect_rate_limit_metrics(self) -> List[PerformanceMetric]:
        """Collect rate limit specific metrics."""
        try:
            # Get rate limit statistics from cache
            today = timezone.now().date()
            cache_key = f"rate_limit_stats:{today}"
            stats = cache.get(cache_key, {'exceeded_count': 0, 'allowed_count': 0})
            
            total_requests = stats['exceeded_count'] + stats['allowed_count']
            block_rate = (stats['exceeded_count'] / max(total_requests, 1)) * 100
            
            metrics = [
                PerformanceMetric('rate_limit_total_requests', total_requests, 'count'),
                PerformanceMetric('rate_limit_exceeded_count', stats['exceeded_count'], 'count'),
                PerformanceMetric('rate_limit_allowed_count', stats['allowed_count'], 'count'),
                PerformanceMetric('rate_limit_block_rate', block_rate, '%')
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect rate limit metrics: {str(e)}")
            return []
    
    def add_collector(self, name: str, collector: Callable):
        """Add a custom metric collector."""
        self.collectors[name] = collector
        logger.info(f"Added metric collector: {name}")
    
    def remove_collector(self, name: str):
        """Remove a metric collector."""
        if name in self.collectors:
            del self.collectors[name]
            logger.info(f"Removed metric collector: {name}")
    
    def collect_metrics(self) -> List[PerformanceMetric]:
        """Collect all metrics."""
        all_metrics = []
        
        for collector_name, collector in self.collectors.items():
            try:
                metrics = collector()
                all_metrics.extend(metrics)
            except Exception as e:
                logger.error(f"Collector {collector_name} failed: {str(e)}")
        
        # Store metrics
        for metric in all_metrics:
            self.metrics[metric.name].append(metric)
        
        return all_metrics
    
    def start_collection(self):
        """Start metric collection."""
        if self.is_collecting:
            logger.warning("Performance collection is already running")
            return
        
        self.is_collecting = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        
        logger.info("Started performance collection")
    
    def stop_collection(self):
        """Stop metric collection."""
        if not self.is_collecting:
            return
        
        self.is_collecting = False
        
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        logger.info("Stopped performance collection")
    
    def _collection_loop(self):
        """Main collection loop."""
        while self.is_collecting:
            try:
                self.collect_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in collection loop: {str(e)}")
                time.sleep(self.collection_interval)
    
    def get_metrics(self, metric_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get collected metrics."""
        if metric_name:
            if metric_name in self.metrics:
                return [metric.to_dict() for metric in list(self.metrics[metric_name])[-limit:]]
            else:
                return []
        else:
            all_metrics = []
            for metrics in self.metrics.values():
                all_metrics.extend([metric.to_dict() for metric in list(metrics)[-limit:]])
            
            # Sort by timestamp
            all_metrics.sort(key=lambda m: m['timestamp'], reverse=True)
            
            return all_metrics[:limit]
    
    def get_metric_statistics(self, metric_name: str, period_minutes: int = 60) -> Dict[str, Any]:
        """Get statistical analysis of a metric."""
        try:
            if metric_name not in self.metrics:
                return {'error': f'Metric not found: {metric_name}'}
            
            cutoff_time = timezone.now() - timedelta(minutes=period_minutes)
            recent_metrics = [
                metric for metric in self.metrics[metric_name]
                if metric.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {'error': 'No recent data available'}
            
            values = [metric.value for metric in recent_metrics]
            
            return {
                'metric_name': metric_name,
                'period_minutes': period_minutes,
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'stdev': statistics.stdev(values) if len(values) > 1 else 0,
                'latest': values[-1],
                'trend': self._calculate_trend(values)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate metric statistics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction."""
        if len(values) < 2:
            return 'stable'
        
        # Simple trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        if second_avg > first_avg * 1.1:
            return 'increasing'
        elif second_avg < first_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'


class PerformanceAnalyzer:
    """Analyzes performance metrics and provides insights."""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
        self.thresholds: List[PerformanceThreshold] = []
        self.alerts: List[Dict[str, Any]] = []
        self.max_alerts = 1000
        self._initialize_thresholds()
    
    def _initialize_thresholds(self):
        """Initialize default performance thresholds."""
        self.thresholds = [
            PerformanceThreshold('cpu_usage_percent', '>', 80, 'critical'),
            PerformanceThreshold('cpu_usage_percent', '>', 60, 'warning'),
            PerformanceThreshold('memory_percent', '>', 90, 'critical'),
            PerformanceThreshold('memory_percent', '>', 75, 'warning'),
            PerformanceThreshold('disk_percent', '>', 90, 'critical'),
            PerformanceThreshold('disk_percent', '>', 80, 'warning'),
            PerformanceThreshold('cache_get_time', '>', 0.1, 'warning'),
            PerformanceThreshold('cache_set_time', '>', 0.1, 'warning'),
            PerformanceThreshold('rate_limit_block_rate', '>', 20, 'warning'),
            PerformanceThreshold('rate_limit_block_rate', '>', 50, 'critical')
        ]
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """Add a performance threshold."""
        self.thresholds.append(threshold)
        logger.info(f"Added performance threshold: {threshold.metric_name}")
    
    def remove_threshold(self, metric_name: str, operator: str, threshold: float):
        """Remove a performance threshold."""
        self.thresholds = [
            t for t in self.thresholds
            if not (t.metric_name == metric_name and t.operator == operator and t.threshold == threshold)
        ]
        logger.info(f"Removed performance threshold: {metric_name}")
    
    def check_thresholds(self, metrics: List[PerformanceMetric] = None) -> List[Dict[str, Any]]:
        """Check metrics against thresholds."""
        if metrics is None:
            # Get latest metrics
            metrics = []
            for metric_name in self.collector.metrics:
                if self.collector.metrics[metric_name]:
                    metrics.append(self.collector.metrics[metric_name][-1])
        
        triggered_alerts = []
        
        for metric in metrics:
            for threshold in self.thresholds:
                if threshold.metric_name == metric.name and threshold.check(metric.value):
                    alert = {
                        'timestamp': timezone.now().isoformat(),
                        'metric_name': metric.name,
                        'metric_value': metric.value,
                        'threshold': threshold.threshold,
                        'operator': threshold.operator,
                        'severity': threshold.severity,
                        'message': threshold.message,
                        'tags': metric.tags
                    }
                    
                    triggered_alerts.append(alert)
                    self.alerts.append(alert)
        
        # Maintain alert history size
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        return triggered_alerts
    
    def get_performance_report(self, period_hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        try:
            report = {
                'period_hours': period_hours,
                'generated_at': timezone.now().isoformat(),
                'metrics_summary': {},
                'alerts_summary': {},
                'recommendations': []
            }
            
            # Get metric statistics
            for metric_name in self.collector.metrics:
                stats = self.collector.get_metric_statistics(metric_name, period_hours * 60)
                if 'error' not in stats:
                    report['metrics_summary'][metric_name] = stats
            
            # Get alerts summary
            cutoff_time = timezone.now() - timedelta(hours=period_hours)
            recent_alerts = [
                alert for alert in self.alerts
                if datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00')) >= cutoff_time
            ]
            
            alert_counts = defaultdict(int)
            severity_counts = defaultdict(int)
            
            for alert in recent_alerts:
                alert_counts[alert['metric_name']] += 1
                severity_counts[alert['severity']] += 1
            
            report['alerts_summary'] = {
                'total_alerts': len(recent_alerts),
                'by_metric': dict(alert_counts),
                'by_severity': dict(severity_counts)
            }
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {str(e)}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        try:
            metrics_summary = report.get('metrics_summary', {})
            alerts_summary = report.get('alerts_summary', {})
            
            # CPU recommendations
            if 'cpu_usage_percent' in metrics_summary:
                cpu_stats = metrics_summary['cpu_usage_percent']
                if cpu_stats['mean'] > 70:
                    recommendations.append("Consider scaling up CPU resources or optimizing CPU-intensive operations")
            
            # Memory recommendations
            if 'memory_percent' in metrics_summary:
                memory_stats = metrics_summary['memory_percent']
                if memory_stats['mean'] > 75:
                    recommendations.append("Monitor memory usage and consider optimizing memory consumption")
            
            # Cache recommendations
            if 'cache_get_time' in metrics_summary:
                cache_stats = metrics_summary['cache_get_time']
                if cache_stats['mean'] > 0.05:
                    recommendations.append("Consider optimizing cache configuration or using a faster cache backend")
            
            # Rate limit recommendations
            if 'rate_limit_block_rate' in metrics_summary:
                block_stats = metrics_summary['rate_limit_block_rate']
                if block_stats['mean'] > 15:
                    recommendations.append("High block rate detected - review rate limit configurations")
            
            # Alert-based recommendations
            critical_alerts = alerts_summary.get('by_severity', {}).get('critical', 0)
            if critical_alerts > 10:
                recommendations.append("High number of critical alerts - immediate attention required")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            return ["Unable to generate recommendations due to error"]
    
    def get_alerts(self, severity: str = None, metric_name: str = None, 
                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get performance alerts."""
        alerts = self.alerts
        
        # Apply filters
        if severity:
            alerts = [alert for alert in alerts if alert['severity'] == severity]
        
        if metric_name:
            alerts = [alert for alert in alerts if alert['metric_name'] == metric_name]
        
        # Sort by timestamp (most recent first)
        alerts.sort(key=lambda a: a['timestamp'], reverse=True)
        
        return alerts[:limit]
    
    def clear_alerts(self, older_than_hours: int = 24):
        """Clear old alerts."""
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)
        
        self.alerts = [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00')) >= cutoff_time
        ]
        
        logger.info(f"Cleared alerts older than {older_than_hours} hours")


class PerformanceMonitor:
    """
    Main performance monitor.
    """
    
    def __init__(self, collection_interval: int = 60):
        self.collector = PerformanceCollector(collection_interval)
        self.analyzer = PerformanceAnalyzer(self.collector)
        self.is_monitoring = False
        self.monitoring_thread = None
        self.monitoring_interval = 300  # 5 minutes
    
    def start_monitoring(self):
        """Start performance monitoring."""
        if self.is_monitoring:
            logger.warning("Performance monitoring is already running")
            return
        
        # Start collection
        self.collector.start_collection()
        
        # Start monitoring
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Started performance monitoring")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        self.collector.stop_collection()
        
        logger.info("Stopped performance monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Collect metrics
                metrics = self.collector.collect_metrics()
                
                # Check thresholds
                alerts = self.analyzer.check_thresholds(metrics)
                
                # Log alerts
                for alert in alerts:
                    if alert['severity'] == 'critical':
                        logger.critical(f"Performance alert: {alert['message']} (value: {alert['metric_value']})")
                    elif alert['severity'] == 'warning':
                        logger.warning(f"Performance alert: {alert['message']} (value: {alert['metric_value']})")
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(self.monitoring_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitoring status."""
        return {
            'is_monitoring': self.is_monitoring,
            'collection_active': self.collector.is_collecting,
            'collection_interval': self.collector.collection_interval,
            'monitoring_interval': self.monitoring_interval,
            'metrics_count': len(self.collector.metrics),
            'thresholds_count': len(self.analyzer.thresholds),
            'alerts_count': len(self.analyzer.alerts)
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for performance dashboard."""
        try:
            dashboard_data = {
                'status': self.get_status(),
                'latest_metrics': {},
                'recent_alerts': self.analyzer.get_alerts(limit=10),
                'performance_report': self.analyzer.get_performance_report(period_hours=1)
            }
            
            # Get latest metrics
            for metric_name in self.collector.metrics:
                if self.collector.metrics[metric_name]:
                    latest_metric = self.collector.metrics[metric_name][-1]
                    dashboard_data['latest_metrics'][metric_name] = latest_metric.to_dict()
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {str(e)}")
            return {'error': str(e)}


# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Start monitoring
performance_monitor.start_monitoring()


# Export classes and functions
__all__ = [
    'PerformanceMetric',
    'PerformanceThreshold',
    'PerformanceCollector',
    'PerformanceAnalyzer',
    'PerformanceMonitor',
    'performance_monitor'
]
