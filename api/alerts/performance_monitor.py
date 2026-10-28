"""
Performance Monitor for alerts app - System performance tracking and analysis
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import connection
import asyncio
import logging
import time
import psutil
import threading
from collections import deque

logger = logging.getLogger(__name__)


class PerformanceMetric(ABC):
    """Abstract base class for performance metrics"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.collection_interval = config.get('collection_interval', 60)  # seconds
        self.max_samples = config.get('max_samples', 1000)
        self.samples = deque(maxlen=self.max_samples)
        self.last_collection = None
        
    @abstractmethod
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect metric data"""
        pass
    
    @abstractmethod
    def get_aggregates(self) -> Dict[str, Any]:
        """Get aggregated metric data"""
        pass
    
    def add_sample(self, sample: Dict[str, Any]):
        """Add sample to collection"""
        sample['timestamp'] = timezone.now().isoformat()
        self.samples.append(sample)
        self.last_collection = timezone.now()
    
    def get_samples(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent samples"""
        return list(self.samples)[-limit:]
    
    def clear_samples(self):
        """Clear all samples"""
        self.samples.clear()
        logger.info(f"Cleared samples for metric: {self.name}")


class CPUMetric(PerformanceMetric):
    """CPU performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect CPU metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Get per-CPU usage
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            sample = {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'cpu_per_core': cpu_per_core,
                'load_1min': load_avg[0],
                'load_5min': load_avg[1],
                'load_15min': load_avg[2]
            }
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get CPU metric aggregates"""
        if not self.samples:
            return {}
        
        cpu_values = [s['cpu_percent'] for s in self.samples]
        
        return {
            'name': self.name,
            'current_cpu': cpu_values[-1] if cpu_values else 0,
            'avg_cpu': sum(cpu_values) / len(cpu_values),
            'min_cpu': min(cpu_values),
            'max_cpu': max(cpu_values),
            'sample_count': len(cpu_values),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class MemoryMetric(PerformanceMetric):
    """Memory performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect memory metrics"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            sample = {
                'total_memory': memory.total,
                'available_memory': memory.available,
                'used_memory': memory.used,
                'memory_percent': memory.percent,
                'total_swap': swap.total,
                'used_swap': swap.used,
                'swap_percent': swap.percent,
                'free_memory': memory.free
            }
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get memory metric aggregates"""
        if not self.samples:
            return {}
        
        memory_values = [s['memory_percent'] for s in self.samples]
        
        return {
            'name': self.name,
            'current_memory_percent': memory_values[-1] if memory_values else 0,
            'avg_memory_percent': sum(memory_values) / len(memory_values),
            'min_memory_percent': min(memory_values),
            'max_memory_percent': max(memory_values),
            'current_used_memory': self.samples[-1]['used_memory'] if self.samples else 0,
            'current_available_memory': self.samples[-1]['available_memory'] if self.samples else 0,
            'sample_count': len(memory_values),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class DiskMetric(PerformanceMetric):
    """Disk performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect disk metrics"""
        try:
            disk_partitions = psutil.disk_partitions()
            disk_usage = {}
            
            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': (usage.used / usage.total) * 100
                    }
                except PermissionError:
                    continue
            
            # Get I/O statistics
            disk_io = psutil.disk_io_counters()
            
            sample = {
                'disk_usage': disk_usage,
                'disk_io': {
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count
                }
            }
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get disk metric aggregates"""
        if not self.samples:
            return {}
        
        latest_sample = self.samples[-1]
        
        return {
            'name': self.name,
            'disk_usage': latest_sample.get('disk_usage', {}),
            'disk_io': latest_sample.get('disk_io', {}),
            'sample_count': len(self.samples),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class NetworkMetric(PerformanceMetric):
    """Network performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect network metrics"""
        try:
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            sample = {
                'network_io': {
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv,
                    'errin': network_io.errin,
                    'errout': network_io.errout,
                    'dropin': network_io.dropin,
                    'dropout': network_io.dropout
                },
                'active_connections': network_connections
            }
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get network metric aggregates"""
        if not self.samples:
            return {}
        
        latest_sample = self.samples[-1]
        
        return {
            'name': self.name,
            'network_io': latest_sample.get('network_io', {}),
            'active_connections': latest_sample.get('active_connections', 0),
            'sample_count': len(self.samples),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class DatabaseMetric(PerformanceMetric):
    """Database performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect database metrics"""
        try:
            with connection.cursor() as cursor:
                # Get connection count
                cursor.execute("SELECT count(*) FROM pg_stat_activity")
                connection_count = cursor.fetchone()[0]
                
                # Get database size
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cursor.fetchone()[0]
                
                # Get slow queries (if pg_stat_statements is available)
                try:
                    cursor.execute("""
                        SELECT query, calls, total_time, mean_time 
                        FROM pg_stat_statements 
                        ORDER BY mean_time DESC 
                        LIMIT 5
                    """)
                    slow_queries = [
                        {
                            'query': row[0][:100],  # Truncate long queries
                            'calls': row[1],
                            'total_time': row[2],
                            'mean_time': row[3]
                        }
                        for row in cursor.fetchall()
                    ]
                except:
                    slow_queries = []
                
                sample = {
                    'connection_count': connection_count,
                    'database_size': db_size,
                    'slow_queries': slow_queries
                }
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get database metric aggregates"""
        if not self.samples:
            return {}
        
        latest_sample = self.samples[-1]
        
        return {
            'name': self.name,
            'connection_count': latest_sample.get('connection_count', 0),
            'database_size': latest_sample.get('database_size', 'Unknown'),
            'slow_queries': latest_sample.get('slow_queries', []),
            'sample_count': len(self.samples),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class ApplicationMetric(PerformanceMetric):
    """Application-specific performance metric"""
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect application metrics"""
        try:
            # Get Django-specific metrics
            from django.core.cache import cache
            
            # Cache metrics
            cache_stats = getattr(cache, '_cache', {})
            
            # Request metrics (would be collected via middleware)
            request_stats = cache.get('app_request_stats', {
                'total_requests': 0,
                'avg_response_time': 0,
                'error_rate': 0
            })
            
            sample = {
                'cache_stats': {
                    'hits': getattr(cache_stats, 'hits', 0),
                    'misses': getattr(cache_stats, 'misses', 0),
                    'hit_rate': 0
                },
                'request_stats': request_stats,
                'active_users': cache.get('active_users', 0),
                'alert_count': cache.get('alert_count', 0)
            }
            
            # Calculate cache hit rate
            hits = sample['cache_stats']['hits']
            misses = sample['cache_stats']['misses']
            total = hits + misses
            if total > 0:
                sample['cache_stats']['hit_rate'] = (hits / total) * 100
            
            self.add_sample(sample)
            return sample
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return None
    
    def get_aggregates(self) -> Dict[str, Any]:
        """Get application metric aggregates"""
        if not self.samples:
            return {}
        
        latest_sample = self.samples[-1]
        
        return {
            'name': self.name,
            'cache_stats': latest_sample.get('cache_stats', {}),
            'request_stats': latest_sample.get('request_stats', {}),
            'active_users': latest_sample.get('active_users', 0),
            'alert_count': latest_sample.get('alert_count', 0),
            'sample_count': len(self.samples),
            'collection_period': self.collection_interval,
            'last_updated': self.last_collection.isoformat() if self.last_collection else None
        }


class PerformanceMonitor:
    """Main performance monitoring system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics = {}
        self.enabled = config.get('enabled', True)
        self.collection_thread = None
        self.stop_event = threading.Event()
        
        # Initialize metrics
        self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Initialize performance metrics"""
        metric_configs = self.config.get('metrics', {})
        
        for metric_name, metric_config in metric_configs.items():
            metric_type = metric_config.get('type', 'cpu')
            
            if metric_type == 'cpu':
                metric = CPUMetric(metric_name, metric_config)
            elif metric_type == 'memory':
                metric = MemoryMetric(metric_name, metric_config)
            elif metric_type == 'disk':
                metric = DiskMetric(metric_name, metric_config)
            elif metric_type == 'network':
                metric = NetworkMetric(metric_name, metric_config)
            elif metric_type == 'database':
                metric = DatabaseMetric(metric_name, metric_config)
            elif metric_type == 'application':
                metric = ApplicationMetric(metric_name, metric_config)
            else:
                logger.error(f"Unknown metric type: {metric_type}")
                continue
            
            self.metrics[metric_name] = metric
            logger.info(f"Initialized performance metric: {metric_name}")
    
    def start_monitoring(self):
        """Start performance monitoring"""
        if not self.enabled:
            logger.warning("Performance monitoring is disabled")
            return
        
        if self.collection_thread and self.collection_thread.is_alive():
            logger.warning("Performance monitoring is already running")
            return
        
        self.stop_event.clear()
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            name="performance_monitor",
            daemon=True
        )
        self.collection_thread.start()
        
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        if self.collection_thread and self.collection_thread.is_alive():
            self.stop_event.set()
            self.collection_thread.join(timeout=5)
            logger.info("Performance monitoring stopped")
    
    def _collection_loop(self):
        """Main collection loop"""
        while not self.stop_event.is_set():
            try:
                # Collect all metrics
                for metric_name, metric in self.metrics.items():
                    if metric.enabled:
                        try:
                            metric.collect()
                        except Exception as e:
                            logger.error(f"Error collecting metric {metric_name}: {e}")
                
                # Wait for next collection
                collection_interval = self.config.get('collection_interval', 60)
                
                # Use different intervals for different metrics
                for metric in self.metrics.values():
                    if metric.enabled:
                        self.stop_event.wait(metric.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                self.stop_event.wait(5)  # Wait before retrying
    
    def get_metric_data(self, metric_name: str = None) -> Dict[str, Any]:
        """Get metric data"""
        if metric_name:
            metric = self.metrics.get(metric_name)
            if metric:
                return metric.get_aggregates()
            else:
                return {'error': f'Metric {metric_name} not found'}
        
        # Return all metrics
        all_metrics = {}
        for name, metric in self.metrics.items():
            all_metrics[name] = metric.get_aggregates()
        
        return {
            'metrics': all_metrics,
            'monitoring_enabled': self.enabled,
            'collection_thread_active': self.collection_thread.is_alive() if self.collection_thread else False,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_metric_samples(self, metric_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get metric samples"""
        metric = self.metrics.get(metric_name)
        if not metric:
            return []
        
        return metric.get_samples(limit)
    
    def clear_metric_samples(self, metric_name: str = None):
        """Clear metric samples"""
        if metric_name:
            metric = self.metrics.get(metric_name)
            if metric:
                metric.clear_samples()
        else:
            for metric in self.metrics.values():
                metric.clear_samples()
    
    def add_custom_metric(self, metric_name: str, metric: PerformanceMetric):
        """Add custom metric"""
        self.metrics[metric_name] = metric
        logger.info(f"Added custom metric: {metric_name}")
    
    def remove_metric(self, metric_name: str):
        """Remove metric"""
        if metric_name in self.metrics:
            del self.metrics[metric_name]
            logger.info(f"Removed metric: {metric_name}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring system status"""
        return {
            'enabled': self.enabled,
            'collection_thread_active': self.collection_thread.is_alive() if self.collection_thread else False,
            'total_metrics': len(self.metrics),
            'enabled_metrics': len([m for m in self.metrics.values() if m.enabled]),
            'collection_interval': self.config.get('collection_interval', 60),
            'metric_names': list(self.metrics.keys()),
            'timestamp': timezone.now().isoformat()
        }


class PerformanceAnalyzer:
    """Analyzes performance data and provides insights"""
    
    def __init__(self, performance_monitor: PerformanceMonitor):
        self.performance_monitor = performance_monitor
        self.analysis_rules = []
        
    def analyze_performance(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Analyze performance over time window"""
        analysis = {
            'time_window_minutes': time_window_minutes,
            'analysis_timestamp': timezone.now().isoformat(),
            'alerts': [],
            'recommendations': [],
            'metrics_analysis': {}
        }
        
        # Get metric data
        all_metrics = self.performance_monitor.get_metric_data()
        
        for metric_name, metric_data in all_metrics.get('metrics', {}).items():
            metric_analysis = self._analyze_metric(metric_name, metric_data, time_window_minutes)
            analysis['metrics_analysis'][metric_name] = metric_analysis
            
            # Check for performance alerts
            alerts = self._check_performance_alerts(metric_name, metric_analysis)
            analysis['alerts'].extend(alerts)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(metric_name, metric_analysis)
            analysis['recommendations'].extend(recommendations)
        
        return analysis
    
    def _analyze_metric(self, metric_name: str, metric_data: Dict[str, Any], time_window_minutes: int) -> Dict[str, Any]:
        """Analyze individual metric"""
        if not metric_data:
            return {'status': 'no_data'}
        
        # CPU analysis
        if 'cpu_percent' in metric_data:
            current_cpu = metric_data['current_cpu']
            avg_cpu = metric_data['avg_cpu']
            max_cpu = metric_data['max_cpu']
            
            cpu_status = 'normal'
            if avg_cpu > 80:
                cpu_status = 'critical'
            elif avg_cpu > 60:
                cpu_status = 'warning'
            elif avg_cpu > 40:
                cpu_status = 'moderate'
            
            return {
                'status': cpu_status,
                'current_value': current_cpu,
                'average_value': avg_cpu,
                'max_value': max_cpu,
                'trend': self._calculate_trend([s['cpu_percent'] for s in self.performance_monitor.get_metric_samples(metric_name, 50)])
            }
        
        # Memory analysis
        elif 'memory_percent' in metric_data:
            current_memory = metric_data['current_memory_percent']
            avg_memory = metric_data['avg_memory_percent']
            max_memory = metric_data['max_memory_percent']
            
            memory_status = 'normal'
            if avg_memory > 85:
                memory_status = 'critical'
            elif avg_memory > 70:
                memory_status = 'warning'
            elif avg_memory > 50:
                memory_status = 'moderate'
            
            return {
                'status': memory_status,
                'current_value': current_memory,
                'average_value': avg_memory,
                'max_value': max_memory,
                'trend': self._calculate_trend([s['memory_percent'] for s in self.performance_monitor.get_metric_samples(metric_name, 50)])
            }
        
        # Disk analysis
        elif 'disk_usage' in metric_data:
            disk_usage = metric_data['disk_usage']
            
            # Find highest disk usage
            max_usage = 0
            for mountpoint, usage in disk_usage.items():
                if usage['percent'] > max_usage:
                    max_usage = usage['percent']
            
            disk_status = 'normal'
            if max_usage > 90:
                disk_status = 'critical'
            elif max_usage > 80:
                disk_status = 'warning'
            elif max_usage > 70:
                disk_status = 'moderate'
            
            return {
                'status': disk_status,
                'max_usage_percent': max_usage,
                'disk_usage': disk_usage,
                'recommendation': self._get_disk_recommendation(disk_usage)
            }
        
        # Network analysis
        elif 'network_io' in metric_data:
            network_io = metric_data['network_io']
            connections = metric_data.get('active_connections', 0)
            
            return {
                'status': 'normal',
                'bytes_sent': network_io['bytes_sent'],
                'bytes_recv': network_io['bytes_recv'],
                'active_connections': connections,
                'recommendation': self._get_network_recommendation(network_io, connections)
            }
        
        # Database analysis
        elif 'connection_count' in metric_data:
            connection_count = metric_data['connection_count']
            slow_queries = metric_data.get('slow_queries', [])
            
            db_status = 'normal'
            if connection_count > 100:
                db_status = 'warning'
            elif connection_count > 200:
                db_status = 'critical'
            
            return {
                'status': db_status,
                'connection_count': connection_count,
                'slow_query_count': len(slow_queries),
                'slow_queries': slow_queries[:5],  # Top 5 slow queries
                'recommendation': self._get_database_recommendation(connection_count, slow_queries)
            }
        
        return {'status': 'unknown'}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from values"""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear regression
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        # Calculate slope
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 'stable'
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        if abs(slope) < 0.1:
            return 'stable'
        elif slope > 0:
            return 'increasing'
        else:
            return 'decreasing'
    
    def _check_performance_alerts(self, metric_name: str, metric_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for performance alerts"""
        alerts = []
        status = metric_analysis.get('status', 'normal')
        
        if status == 'critical':
            alerts.append({
                'type': 'critical_performance',
                'metric': metric_name,
                'message': f'{metric_name} is in critical state',
                'severity': 'critical',
                'current_value': metric_analysis.get('current_value'),
                'threshold': metric_analysis.get('max_value')
            })
        elif status == 'warning':
            alerts.append({
                'type': 'performance_warning',
                'metric': metric_name,
                'message': f'{metric_name} is showing warning signs',
                'severity': 'warning',
                'current_value': metric_analysis.get('current_value'),
                'threshold': metric_analysis.get('max_value')
            })
        
        return alerts
    
    def _generate_recommendations(self, metric_name: str, metric_analysis: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        # Add metric-specific recommendations
        if 'recommendation' in metric_analysis:
            recommendations.append(metric_analysis['recommendation'])
        
        # Add general recommendations based on status
        status = metric_analysis.get('status', 'normal')
        
        if status in ['critical', 'warning']:
            recommendations.append(f'Consider investigating {metric_name} performance issues')
            recommendations.append('Monitor system resources closely')
        
        return recommendations
    
    def _get_disk_recommendation(self, disk_usage: Dict[str, Any]) -> str:
        """Get disk usage recommendation"""
        high_usage_disks = [
            mountpoint for mountpoint, usage in disk_usage.items()
            if usage['percent'] > 80
        ]
        
        if high_usage_disks:
            return f'Disk cleanup recommended for: {", ".join(high_usage_disks)}'
        
        return 'Disk usage is within acceptable limits'
    
    def _get_network_recommendation(self, network_io: Dict[str, Any], connections: int) -> str:
        """Get network performance recommendation"""
        if connections > 1000:
            return 'High number of network connections detected'
        
        bytes_sent = network_io['bytes_sent']
        bytes_recv = network_io['bytes_recv']
        
        if bytes_sent > 1024 * 1024 * 1024 * 100:  # 100GB
            return 'High network egress traffic detected'
        
        if bytes_recv > 1024 * 1024 * 1024 * 100:  # 100GB
            return 'High network ingress traffic detected'
        
        return 'Network performance is normal'
    
    def _get_database_recommendation(self, connection_count: int, slow_queries: List[Dict[str, Any]]) -> str:
        """Get database performance recommendation"""
        recommendations = []
        
        if connection_count > 100:
            recommendations.append('Consider increasing database connection pool size')
        
        if len(slow_queries) > 5:
            recommendations.append('Optimize slow queries')
            recommendations.append('Review database indexes')
        
        if not recommendations:
            return 'Database performance is normal'
        
        return '; '.join(recommendations)


# Global performance monitor
performance_monitor = None
performance_analyzer = None


def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get global performance monitor"""
    return performance_monitor


def get_performance_analyzer() -> Optional[PerformanceAnalyzer]:
    """Get global performance analyzer"""
    return performance_analyzer


def initialize_performance_monitoring():
    """Initialize performance monitoring from settings"""
    from django.conf import settings
    
    global performance_monitor, performance_analyzer
    
    config = getattr(settings, 'PERFORMANCE_MONITORING_CONFIG', {
        'enabled': True,
        'collection_interval': 60,
        'metrics': {
            'system_cpu': {
                'type': 'cpu',
                'enabled': True,
                'collection_interval': 30
            },
            'system_memory': {
                'type': 'memory',
                'enabled': True,
                'collection_interval': 30
            },
            'system_disk': {
                'type': 'disk',
                'enabled': True,
                'collection_interval': 300
            },
            'system_network': {
                'type': 'network',
                'enabled': True,
                'collection_interval': 60
            },
            'application_metrics': {
                'type': 'application',
                'enabled': True,
                'collection_interval': 60
            }
        }
    })
    
    try:
        performance_monitor = PerformanceMonitor(config)
        performance_analyzer = PerformanceAnalyzer(performance_monitor)
        
        # Auto-start if enabled
        # Opt-in: PERFORMANCE_MONITORING_CONFIG = {'auto_start': True, ...} (one thread per process)
        if config.get('auto_start', False):
            performance_monitor.start_monitoring()
        
        logger.info("Performance monitoring system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing performance monitoring: {e}")


# Initialize on module import
try:
    initialize_performance_monitoring()
except Exception as e:
    logger.error(f"Error initializing performance monitoring: {e}")
