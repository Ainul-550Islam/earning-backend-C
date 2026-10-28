"""
Integration Performance Monitor - Performance monitoring for integration system
Provides safe performance monitoring with existing alerts architecture
"""
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.conf import settings as django_settings
from django.db import connection, connections as db_connections
from collections import defaultdict, deque

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS,
    PERFORMANCE_THRESHOLDS as _BASE_THRESHOLDS
)

logger = logging.getLogger(__name__)


def _build_thresholds() -> Dict[str, float]:
    """Complete threshold set read by get_performance_alerts().

    integ_constants.PERFORMANCE_THRESHOLDS only carries integration-level keys
    (``*_ms``, error_rate, queue_depth). The monitor also needs system, database
    and response-time (seconds) keys, which used to raise KeyError and silently
    disable every performance alert. Override any key from project settings with
    ``ALERTS_PERFORMANCE_THRESHOLDS = {...}``.
    """
    thresholds: Dict[str, float] = {
        'cpu_warning': 80.0, 'cpu_critical': 95.0,
        'memory_warning': 80.0, 'memory_critical': 95.0,
        'disk_warning': 85.0, 'disk_critical': 95.0,
        'db_connections_warning': 80, 'db_connections_critical': 150,
        'response_time_warning': 1.0, 'response_time_critical': 5.0,  # seconds
    }
    base = dict(_BASE_THRESHOLDS or {})
    for level in ('warning', 'critical'):
        ms = base.get(f'response_time_{level}_ms')
        if ms is not None:
            thresholds[f'response_time_{level}'] = float(ms) / 1000.0
    thresholds.update(base)
    override = getattr(django_settings, 'ALERTS_PERFORMANCE_THRESHOLDS', None)
    if isinstance(override, dict):
        thresholds.update(override)
    return thresholds


PERFORMANCE_THRESHOLDS = _build_thresholds()


class IntegrationPerformanceMonitor:
    """
    Performance monitoring for integration system
    Maintains existing monitoring logic and adds integration-specific metrics
    """
    
    def __init__(self):
        self.metrics = defaultdict(lambda: defaultdict(list))
        self.counters = defaultdict(int)
        self.timers = defaultdict(float)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        self.monitoring_stats = {
            'total_metrics': 0,
            'monitoring_start': django_tz.now().isoformat(),
            'last_update': None
        }
        self.lock = threading.RLock()
        # Background collection is opt-in: a thread (and DB connection) per worker
        # started at import time is a production hazard. Enable with
        # ALERTS_PERFORMANCE_MONITOR_AUTOSTART = True or call start_monitoring().
        if getattr(django_settings, 'ALERTS_PERFORMANCE_MONITOR_AUTOSTART', False):
            self._start_monitoring()

    def start_monitoring(self):
        """Start background metric collection (idempotent)."""
        self._start_monitoring()
    
    def _start_monitoring(self):
        """
        Start background monitoring
        """
        try:
            existing = getattr(self, 'monitoring_thread', None)
            if existing is not None and existing.is_alive():
                return
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop, name='alerts-perf-monitor', daemon=True
            )
            self.monitoring_thread.start()
            
            logger.info("Integration performance monitoring started")
            
        except Exception as e:
            logger.error(f"Error starting performance monitoring: {e}")
    
    def _monitoring_loop(self):
        """
        Background monitoring loop
        """
        while True:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                
                # Collect database metrics
                self._collect_database_metrics()
                
                # Collect cache metrics
                self._collect_cache_metrics()
                db_connections.close_all()  # background thread: never hold a DB connection while idle
                
                # Update monitoring stats
                self.monitoring_stats['last_update'] = django_tz.now().isoformat()
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                db_connections.close_all()
                time.sleep(30)
    
    def _collect_system_metrics(self):
        """
        Collect system performance metrics
        """
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric('system', 'cpu_usage', cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric('system', 'memory_usage', memory.percent)
            self.record_metric('system', 'memory_available', memory.available)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric('system', 'disk_usage', disk_percent)
            
        except ImportError:
            logger.warning("psutil not available for system metrics")
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _collect_database_metrics(self):
        """
        Collect database performance metrics
        """
        try:
            if connection.vendor != 'postgresql':
                return  # pg_stat_activity / pg_database_size are PostgreSQL-only
            # Database connection count
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                active_connections = cursor.fetchone()[0]
                self.record_metric('database', 'active_connections', active_connections)
                
                # Database size
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cursor.fetchone()[0]
                self.record_metric('database', 'size', db_size)
                
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
    
    def _collect_cache_metrics(self):
        """
        Collect cache performance metrics
        """
        try:
            # Cache hit/miss ratio (simplified)
            cache_hits = self.counters.get('cache_hits', 0)
            cache_misses = self.counters.get('cache_misses', 0)
            total_cache_requests = cache_hits + cache_misses
            
            if total_cache_requests > 0:
                hit_ratio = (cache_hits / total_cache_requests) * 100
                self.record_metric('cache', 'hit_ratio', hit_ratio)
            
        except Exception as e:
            logger.error(f"Error collecting cache metrics: {e}")
    
    def record_metric(self, category: str, metric_name: str, value: Union[int, float]):
        """
        Record a metric value
        """
        try:
            with self.lock:
                # Add timestamp
                timestamp = time.time()
                
                # Store metric
                self.metrics[category][metric_name].append({
                    'value': value,
                    'timestamp': timestamp
                })
                
                # Keep only last 1000 data points per metric
                if len(self.metrics[category][metric_name]) > 1000:
                    self.metrics[category][metric_name] = self.metrics[category][metric_name][-1000:]
                
                # Update counters
                self.counters[f'{category}_{metric_name}_count'] += 1
                
                # Update monitoring stats
                self.monitoring_stats['total_metrics'] += 1
                
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
    
    def record_timer(self, category: str, timer_name: str, duration: float):
        """
        Record a timer metric
        """
        try:
            with self.lock:
                # Update timer
                self.timers[f'{category}_{timer_name}_duration'] = duration
                
                # Record as metric
                self.record_metric(category, f'{timer_name}_duration', duration)
                
                # Update histogram
                duration_bucket = self._get_duration_bucket(duration)
                self.histograms[category][f'{timer_name}_histogram'][duration_bucket] += 1
                
        except Exception as e:
            logger.error(f"Error recording timer: {e}")
    
    def _get_duration_bucket(self, duration: float) -> str:
        """
        Get duration bucket for histogram
        """
        if duration < 0.1:
            return '0_0.1s'
        elif duration < 0.5:
            return '0.1_0.5s'
        elif duration < 1.0:
            return '0.5_1.0s'
        elif duration < 5.0:
            return '1_5s'
        elif duration < 10.0:
            return '5_10s'
        elif duration < 30.0:
            return '10_30s'
        elif duration < 60.0:
            return '30_60s'
        else:
            return '60s_plus'
    
    def increment_counter(self, category: str, counter_name: str, value: int = 1):
        """
        Increment a counter
        """
        try:
            with self.lock:
                self.counters[f'{category}_{counter_name}'] += value
                self.record_metric(category, counter_name, self.counters[f'{category}_{counter_name}'])
                
        except Exception as e:
            logger.error(f"Error incrementing counter: {e}")
    
    def set_gauge(self, category: str, gauge_name: str, value: float):
        """
        Set a gauge value
        """
        try:
            with self.lock:
                self.gauges[f'{category}_{gauge_name}'] = value
                self.record_metric(category, gauge_name, value)
                
        except Exception as e:
            logger.error(f"Error setting gauge: {e}")
    
    def time_function(self, category: str, timer_name: str):
        """
        Decorator to time function execution
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.record_timer(category, timer_name, duration)
            return wrapper
        return decorator
    
    def get_metrics_summary(self, category: str = None, metric_name: str = None) -> Dict[str, Any]:
        """
        Get metrics summary
        """
        try:
            with self.lock:
                if category and metric_name:
                    # Get specific metric
                    if category in self.metrics and metric_name in self.metrics[category]:
                        data_points = self.metrics[category][metric_name]
                        if data_points:
                            values = [point['value'] for point in data_points]
                            return {
                                'category': category,
                                'metric': metric_name,
                                'count': len(values),
                                'min': min(values),
                                'max': max(values),
                                'avg': sum(values) / len(values),
                                'latest': values[-1],
                                'data_points': data_points[-10:]  # Last 10 points
                            }
                    else:
                        return {'error': f'Metric {category}.{metric_name} not found'}
                
                elif category:
                    # Get all metrics for category
                    if category in self.metrics:
                        summary = {'category': category, 'metrics': {}}
                        for metric in self.metrics[category]:
                            metric_summary = self.get_metrics_summary(category, metric)
                            if 'error' not in metric_summary:
                                summary['metrics'][metric] = metric_summary
                        return summary
                    else:
                        return {'error': f'Category {category} not found'}
                
                else:
                    # Get all metrics
                    summary = {'categories': {}}
                    for cat in self.metrics:
                        cat_summary = self.get_metrics_summary(cat)
                        if 'error' not in cat_summary:
                            summary['categories'][cat] = cat_summary
                    return summary
                    
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {'error': 'Operation failed'}
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """
        Get performance alerts based on thresholds
        """
        try:
            alerts = []
            
            # Check system metrics
            system_metrics = self.get_metrics_summary('system')
            if 'metrics' in system_metrics:
                # CPU usage alert
                if 'cpu_usage' in system_metrics['metrics']:
                    cpu_usage = system_metrics['metrics']['cpu_usage']['latest']
                    if cpu_usage > PERFORMANCE_THRESHOLDS['cpu_warning']:
                        alerts.append({
                            'type': 'performance',
                            'severity': 'warning' if cpu_usage < PERFORMANCE_THRESHOLDS['cpu_critical'] else 'critical',
                            'message': f'High CPU usage: {cpu_usage:.1f}%',
                            'metric': 'system.cpu_usage',
                            'value': cpu_usage,
                            'threshold': PERFORMANCE_THRESHOLDS['cpu_warning']
                        })
                
                # Memory usage alert
                if 'memory_usage' in system_metrics['metrics']:
                    memory_usage = system_metrics['metrics']['memory_usage']['latest']
                    if memory_usage > PERFORMANCE_THRESHOLDS['memory_warning']:
                        alerts.append({
                            'type': 'performance',
                            'severity': 'warning' if memory_usage < PERFORMANCE_THRESHOLDS['memory_critical'] else 'critical',
                            'message': f'High memory usage: {memory_usage:.1f}%',
                            'metric': 'system.memory_usage',
                            'value': memory_usage,
                            'threshold': PERFORMANCE_THRESHOLDS['memory_warning']
                        })
                
                # Disk usage alert
                if 'disk_usage' in system_metrics['metrics']:
                    disk_usage = system_metrics['metrics']['disk_usage']['latest']
                    if disk_usage > PERFORMANCE_THRESHOLDS['disk_warning']:
                        alerts.append({
                            'type': 'performance',
                            'severity': 'warning' if disk_usage < PERFORMANCE_THRESHOLDS['disk_critical'] else 'critical',
                            'message': f'High disk usage: {disk_usage:.1f}%',
                            'metric': 'system.disk_usage',
                            'value': disk_usage,
                            'threshold': PERFORMANCE_THRESHOLDS['disk_warning']
                        })
            
            # Check database metrics
            db_metrics = self.get_metrics_summary('database')
            if 'metrics' in db_metrics:
                # Active connections alert
                if 'active_connections' in db_metrics['metrics']:
                    connections = db_metrics['metrics']['active_connections']['latest']
                    if connections > PERFORMANCE_THRESHOLDS['db_connections_warning']:
                        alerts.append({
                            'type': 'performance',
                            'severity': 'warning' if connections < PERFORMANCE_THRESHOLDS['db_connections_critical'] else 'critical',
                            'message': f'High database connections: {connections}',
                            'metric': 'database.active_connections',
                            'value': connections,
                            'threshold': PERFORMANCE_THRESHOLDS['db_connections_warning']
                        })
            
            # Check integration-specific metrics
            integration_metrics = self.get_metrics_summary('integration')
            if 'metrics' in integration_metrics:
                # Response time alerts
                for metric_name, metric_data in integration_metrics['metrics'].items():
                    if 'duration' in metric_name and 'avg' in metric_data:
                        avg_duration = metric_data['avg']
                        if avg_duration > PERFORMANCE_THRESHOLDS['response_time_warning']:
                            alerts.append({
                                'type': 'performance',
                                'severity': 'warning' if avg_duration < PERFORMANCE_THRESHOLDS['response_time_critical'] else 'critical',
                                'message': f'Slow response time: {metric_name} - {avg_duration:.3f}s',
                                'metric': f'integration.{metric_name}',
                                'value': avg_duration,
                                'threshold': PERFORMANCE_THRESHOLDS['response_time_warning']
                            })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting performance alerts: {e}")
            return []
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """
        Get monitoring statistics
        """
        try:
            with self.lock:
                return {
                    'total_metrics': self.monitoring_stats['total_metrics'],
                    'monitoring_start': self.monitoring_stats['monitoring_start'],
                    'last_update': self.monitoring_stats['last_update'],
                    'categories_count': len(self.metrics),
                    'counters_count': len(self.counters),
                    'timers_count': len(self.timers),
                    'gauges_count': len(self.gauges),
                    'histograms_count': len(self.histograms),
                    'timestamp': django_tz.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting monitoring statistics: {e}")
            return {'error': 'Operation failed'}
    
    def clear_metrics(self, category: str = None):
        """
        Clear metrics
        """
        try:
            with self.lock:
                if category:
                    if category in self.metrics:
                        del self.metrics[category]
                        logger.info(f"Cleared metrics for category: {category}")
                else:
                    self.metrics.clear()
                    self.counters.clear()
                    self.timers.clear()
                    self.gauges.clear()
                    self.histograms.clear()
                    logger.info("Cleared all metrics")
                    
        except Exception as e:
            logger.error(f"Error clearing metrics: {e}")
    
    def export_metrics(self, format: str = 'json') -> Union[str, Dict[str, Any]]:
        """
        Export metrics in specified format
        """
        try:
            if format == 'json':
                return self.get_metrics_summary()
            elif format == 'prometheus':
                return self._export_prometheus_format()
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return {'error': 'Operation failed'}
    
    def _export_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus format
        """
        try:
            prometheus_lines = []
            
            for category, metrics in self.metrics.items():
                for metric_name, data_points in metrics.items():
                    if data_points:
                        latest_value = data_points[-1]['value']
                        prometheus_name = f"alerts_integration_{category}_{metric_name}"
                        prometheus_lines.append(f"{prometheus_name} {latest_value}")
            
            return '\n'.join(prometheus_lines)
            
        except Exception as e:
            logger.error(f"Error exporting Prometheus format: {e}")
            return ""


# Global performance monitor instance
integration_performance_monitor = IntegrationPerformanceMonitor()


# Decorators for performance monitoring
def monitor_integration_performance(category: str = 'integration', timer_name: str = 'function'):
    """
    Decorator for monitoring integration performance
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            return integration_performance_monitor.time_function(category, timer_name)(func)(*args, **kwargs)
        return wrapper
    return decorator


# Utility functions
def record_integration_metric(category: str, metric_name: str, value: Union[int, float]):
    """
    Record integration metric
    """
    integration_performance_monitor.record_metric(category, metric_name, value)


def record_integration_timer(category: str, timer_name: str, duration: float):
    """
    Record integration timer
    """
    integration_performance_monitor.record_timer(category, timer_name, duration)


def increment_integration_counter(category: str, counter_name: str, value: int = 1):
    """
    Increment integration counter
    """
    integration_performance_monitor.increment_counter(category, counter_name, value)


def get_performance_metrics(category: str = None, metric_name: str = None) -> Dict[str, Any]:
    """
    Get performance metrics
    """
    return integration_performance_monitor.get_metrics_summary(category, metric_name)


def get_performance_alerts() -> List[Dict[str, Any]]:
    """
    Get performance alerts
    """
    return integration_performance_monitor.get_performance_alerts()


def get_monitoring_statistics() -> Dict[str, Any]:
    """
    Get monitoring statistics
    """
    return integration_performance_monitor.get_monitoring_statistics()
