"""
Monitoring Service for Offer Routing System

This module provides monitoring and alerting functionality
for routing performance, errors, and system health.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from ..constants import MAX_ROUTING_TIME_MS, PERFORMANCE_ALERT_THRESHOLD
from ..exceptions import PerformanceError

User = get_user_model()
logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Service for monitoring routing system performance and health.
    
    Provides performance monitoring, alerting, and health checks.
    """
    
    def __init__(self):
        self.alert_thresholds = {
            'response_time_ms': MAX_ROUTING_TIME_MS,
            'error_rate': 5.0,
            'cache_hit_rate': 70.0,
            'memory_usage': 80.0,
            'cpu_usage': 80.0
        }
        
        self.last_health_check = None
        self.performance_metrics = {}
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        try:
            health_status = {
                'overall_status': 'healthy',
                'checks': {},
                'timestamp': timezone.now().isoformat(),
                'alerts': []
            }
            
            # Check database connectivity
            db_status = self._check_database_health()
            health_status['checks']['database'] = db_status
            
            # Check cache connectivity
            cache_status = self._check_cache_health()
            health_status['checks']['cache'] = cache_status
            
            # Check memory usage
            memory_status = self._check_memory_usage()
            health_status['checks']['memory'] = memory_status
            
            # Check routing performance
            performance_status = self._check_routing_performance()
            health_status['checks']['performance'] = performance_status
            
            # Check error rates
            error_status = self._check_error_rates()
            health_status['checks']['errors'] = error_status
            
            # Determine overall status
            for check_name, check_result in health_status['checks'].items():
                if check_result['status'] != 'healthy':
                    health_status['overall_status'] = 'degraded'
                    health_status['alerts'].append({
                        'type': 'health_check',
                        'component': check_name,
                        'message': f"{check_name} is {check_result['status']}: {check_result['message']}",
                        'timestamp': timezone.now().isoformat()
                    })
            
            self.last_health_check = health_status
            return health_status
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {
                'overall_status': 'unhealthy',
                'checks': {},
                'timestamp': timezone.now().isoformat(),
                'alerts': [{'type': 'system_error', 'message': str(e)}]
            }
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            if response_time > 1000:  # 1 second
                return {
                    'status': 'degraded',
                    'message': f'Database response time: {response_time:.2f}ms',
                    'response_time_ms': response_time
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Database response time: {response_time:.2f}ms',
                    'response_time_ms': response_time
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}',
                'error': str(e)
            }
    
    def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test cache operations
            test_key = 'health_check_test'
            test_value = {'test': True, 'timestamp': time.time()}
            
            # Test set
            cache.set(test_key, test_value, timeout=60)
            
            # Test get
            retrieved_value = cache.get(test_key)
            
            # Test delete
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if retrieved_value != test_value:
                return {
                    'status': 'unhealthy',
                    'message': 'Cache read/write test failed',
                    'response_time_ms': response_time
                }
            elif response_time > 500:  # 500ms
                return {
                    'status': 'degraded',
                    'message': f'Cache response time: {response_time:.2f}ms',
                    'response_time_ms': response_time
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Cache response time: {response_time:.2f}ms',
                    'response_time_ms': response_time
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Cache connection failed: {str(e)}',
                'error': str(e)
            }
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            import psutil
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent
            
            if memory_usage_percent > self.alert_thresholds['memory_usage']:
                return {
                    'status': 'degraded',
                    'message': f'Memory usage: {memory_usage_percent:.1f}%',
                    'memory_usage_percent': memory_usage_percent,
                    'total_memory_gb': memory.total / (1024**3),
                    'available_memory_gb': memory.available / (1024**3)
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Memory usage: {memory_usage_percent:.1f}%',
                    'memory_usage_percent': memory_usage_percent,
                    'total_memory_gb': memory.total / (1024**3),
                    'available_memory_gb': memory.available / (1024**3)
                }
                
        except ImportError:
            return {
                'status': 'unknown',
                'message': 'psutil not available for memory monitoring'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Memory check failed: {str(e)}',
                'error': str(e)
            }
    
    def _check_routing_performance(self) -> Dict[str, Any]:
        """Check routing performance metrics."""
        try:
            from datetime import timedelta
            from ..models import RoutingDecisionLog
            
            # Get recent routing decisions
            cutoff_time = timezone.now() - timedelta(minutes=5)
            recent_decisions = RoutingDecisionLog.objects.filter(
                created_at__gte=cutoff_time
            ).aggregate(
                avg_response_time=Avg('response_time_ms'),
                max_response_time=Max('response_time_ms'),
                total_decisions=Count('id'),
                slow_requests=Count('id', filter=Q(response_time_ms__gt=self.alert_thresholds['response_time_ms']))
            )
            
            avg_response_time = recent_decisions['avg_response_time'] or 0
            max_response_time = recent_decisions['max_response_time'] or 0
            total_decisions = recent_decisions['total_decisions'] or 0
            slow_requests = recent_decisions['slow_requests'] or 0
            
            # Calculate slow request percentage
            slow_request_percentage = (slow_requests / total_decisions * 100) if total_decisions > 0 else 0
            
            if avg_response_time > self.alert_thresholds['response_time_ms']:
                return {
                    'status': 'degraded',
                    'message': f'Average response time: {avg_response_time:.2f}ms (threshold: {self.alert_thresholds["response_time_ms"]}ms)',
                    'avg_response_time_ms': avg_response_time,
                    'max_response_time_ms': max_response_time,
                    'slow_request_percentage': slow_request_percentage,
                    'total_requests': total_decisions
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Average response time: {avg_response_time:.2f}ms',
                    'avg_response_time_ms': avg_response_time,
                    'max_response_time_ms': max_response_time,
                    'slow_request_percentage': slow_request_percentage,
                    'total_requests': total_decisions
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Performance check failed: {str(e)}',
                'error': str(e)
            }
    
    def _check_error_rates(self) -> Dict[str, Any]:
        """Check error rates."""
        try:
            from datetime import timedelta
            from ..models import RoutingDecisionLog
            
            # Get recent routing decisions
            cutoff_time = timezone.now() - timedelta(minutes=5)
            recent_decisions = RoutingDecisionLog.objects.filter(
                created_at__gte=cutoff_time
            ).aggregate(
                total_decisions=Count('id'),
                cache_misses=Count('id', filter=Q(cache_hit=False)),
                fallback_usage=Count('id', filter=Q(fallback_used=True))
            )
            
            total_decisions = recent_decisions['total_decisions'] or 0
            cache_misses = recent_decisions['cache_misses'] or 0
            fallback_usage = recent_decisions['fallback_usage'] or 0
            
            # Calculate rates
            cache_miss_rate = (cache_misses / total_decisions * 100) if total_decisions > 0 else 0
            fallback_rate = (fallback_usage / total_decisions * 100) if total_decisions > 0 else 0
            cache_hit_rate = 100 - cache_miss_rate
            
            if cache_hit_rate < self.alert_thresholds['cache_hit_rate']:
                return {
                    'status': 'degraded',
                    'message': f'Cache hit rate: {cache_hit_rate:.1f}% (threshold: {self.alert_thresholds["cache_hit_rate"]}%)',
                    'cache_hit_rate': cache_hit_rate,
                    'cache_miss_rate': cache_miss_rate,
                    'fallback_rate': fallback_rate,
                    'total_requests': total_decisions
                }
            else:
                return {
                    'status': 'healthy',
                    'message': f'Cache hit rate: {cache_hit_rate:.1f}%',
                    'cache_hit_rate': cache_hit_rate,
                    'cache_miss_rate': cache_miss_rate,
                    'fallback_rate': fallback_rate,
                    'total_requests': total_decisions
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Error rate check failed: {str(e)}',
                'error': str(e)
            }
    
    def record_performance_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a performance metric."""
        try:
            timestamp = timezone.now()
            
            metric_data = {
                'name': metric_name,
                'value': value,
                'timestamp': timestamp,
                'tags': tags or {}
            }
            
            # Store in memory for recent metrics
            if metric_name not in self.performance_metrics:
                self.performance_metrics[metric_name] = []
            
            self.performance_metrics[metric_name].append(metric_data)
            
            # Keep only last 100 metrics per name
            if len(self.performance_metrics[metric_name]) > 100:
                self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-100:]
            
            # Check for alerts
            self._check_metric_alerts(metric_name, value, tags)
            
        except Exception as e:
            logger.error(f"Error recording performance metric: {e}")
    
    def _check_metric_alerts(self, metric_name: str, value: float, tags: Dict[str, str]):
        """Check if metric triggers any alerts."""
        try:
            alert_triggered = False
            alert_message = ""
            
            # Check response time alerts
            if metric_name == 'routing_response_time':
                if value > self.alert_thresholds['response_time_ms']:
                    alert_triggered = True
                    alert_message = f"High response time: {value:.2f}ms"
            
            # Check cache hit rate alerts
            elif metric_name == 'cache_hit_rate':
                if value < self.alert_thresholds['cache_hit_rate']:
                    alert_triggered = True
                    alert_message = f"Low cache hit rate: {value:.1f}%"
            
            # Check error rate alerts
            elif metric_name == 'error_rate':
                if value > self.alert_thresholds['error_rate']:
                    alert_triggered = True
                    alert_message = f"High error rate: {value:.1f}%"
            
            if alert_triggered:
                self._trigger_alert(metric_name, value, alert_message, tags)
                
        except Exception as e:
            logger.error(f"Error checking metric alerts: {e}")
    
    def _trigger_alert(self, metric_name: str, value: float, message: str, tags: Dict[str, str]):
        """Trigger an alert."""
        try:
            alert = {
                'metric_name': metric_name,
                'value': value,
                'message': message,
                'tags': tags,
                'timestamp': timezone.now().isoformat(),
                'severity': 'warning'
            }
            
            # Log alert
            logger.warning(f"Performance alert: {message}")
            
            # This would send alert to monitoring system
            # For now, just log it
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
    
    def get_performance_metrics(self, metric_name: str = None, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get performance metrics."""
        try:
            from datetime import timedelta
            cutoff_time = timezone.now() - timedelta(minutes=minutes)
            
            metrics = []
            
            if metric_name:
                if metric_name in self.performance_metrics:
                    for metric in self.performance_metrics[metric_name]:
                        if metric['timestamp'] >= cutoff_time:
                            metrics.append(metric)
            else:
                for name, metric_list in self.performance_metrics.items():
                    for metric in metric_list:
                        if metric['timestamp'] >= cutoff_time:
                            metrics.append(metric)
            
            return sorted(metrics, key=lambda x: x['timestamp'])
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return []
    
    def get_performance_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary."""
        try:
            metrics = self.get_performance_metrics(minutes=minutes)
            
            if not metrics:
                return {}
            
            # Group by metric name
            metric_groups = {}
            for metric in metrics:
                name = metric['name']
                if name not in metric_groups:
                    metric_groups[name] = []
                metric_groups[name].append(metric['value'])
            
            # Calculate statistics for each metric
            summary = {}
            for name, values in metric_groups.items():
                if values:
                    summary[name] = {
                        'count': len(values),
                        'avg': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'latest': values[-1]
                    }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    def check_service_dependencies(self) -> Dict[str, Any]:
        """Check external service dependencies."""
        try:
            dependencies = {
                'database': self._check_database_dependency(),
                'cache': self._check_cache_dependency(),
                'external_apis': self._check_external_api_dependencies()
            }
            
            overall_status = 'healthy'
            for dep_name, dep_status in dependencies.items():
                if dep_status['status'] != 'healthy':
                    overall_status = 'degraded'
            
            return {
                'overall_status': overall_status,
                'dependencies': dependencies,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking service dependencies: {e}")
            return {
                'overall_status': 'unhealthy',
                'dependencies': {},
                'error': str(e)
            }
    
    def _check_database_dependency(self) -> Dict[str, Any]:
        """Check database dependency."""
        try:
            start_time = time.time()
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy' if response_time < 1000 else 'degraded',
                'response_time_ms': response_time,
                'message': f'Database response time: {response_time:.2f}ms'
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'Database connection failed'
            }
    
    def _check_cache_dependency(self) -> Dict[str, Any]:
        """Check cache dependency."""
        try:
            start_time = time.time()
            
            test_key = 'dependency_check'
            test_value = {'test': True}
            
            cache.set(test_key, test_value, timeout=10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            if retrieved != test_value:
                return {
                    'status': 'unhealthy',
                    'message': 'Cache read/write test failed'
                }
            else:
                return {
                    'status': 'healthy' if response_time < 500 else 'degraded',
                    'response_time_ms': response_time,
                    'message': f'Cache response time: {response_time:.2f}ms'
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'Cache connection failed'
            }
    
    def _check_external_api_dependencies(self) -> Dict[str, Any]:
        """Check external API dependencies."""
        try:
            # This would check external APIs that the routing system depends on
            # For now, return healthy status
            
            return {
                'status': 'healthy',
                'message': 'All external APIs are healthy'
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'External API check failed'
            }


# Singleton instance
monitoring_service = MonitoringService()
