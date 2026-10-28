# =============================================================================
# auto_mod/monitoring.py
# =============================================================================

"""
Monitoring and health checking for auto moderation system.
Provides system health monitoring, performance metrics, and alerting.
"""

import logging
import psutil
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from django.conf import settings

from .models import SuspiciousSubmission, ModerationDecision, TaskBot, ModerationQueue
from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class SystemMetrics:
    """System metrics container."""
    
    def __init__(self):
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.disk_percent = 0.0
        self.database_connections = 0
        self.cache_hit_rate = 0.0
        self.queue_size = 0
        self.active_bots = 0
        self.processing_rate = 0.0
        self.error_rate = 0.0
        self.response_time = 0.0
        self.timestamp = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_percent': self.disk_percent,
            'database_connections': self.database_connections,
            'cache_hit_rate': self.cache_hit_rate,
            'queue_size': self.queue_size,
            'active_bots': self.active_bots,
            'processing_rate': self.processing_rate,
            'error_rate': self.error_rate,
            'response_time': self.response_time,
            'timestamp': self.timestamp.isoformat(),
        }


class HealthChecker:
    """Health checker for auto moderation system."""
    
    def __init__(self):
        self.thresholds = self._initialize_thresholds()
        self.alerts = []
    
    def _initialize_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize health check thresholds."""
        return {
            'cpu': {'warning': 70.0, 'critical': 90.0},
            'memory': {'warning': 75.0, 'critical': 90.0},
            'disk': {'warning': 80.0, 'critical': 95.0},
            'database_connections': {'warning': 50, 'critical': 80},
            'cache_hit_rate': {'warning': 80.0, 'critical': 60.0},
            'queue_size': {'warning': 1000, 'critical': 5000},
            'error_rate': {'warning': 5.0, 'critical': 10.0},
            'response_time': {'warning': 2.0, 'critical': 5.0},
        }
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Health check results
        """
        try:
            metrics = self._collect_system_metrics()
            health_status = self._evaluate_health(metrics)
            alerts = self._generate_alerts(metrics, health_status)
            
            # Store recent health check
            self._store_health_check(metrics, health_status, alerts)
            
            return {
                'status': health_status,
                'metrics': metrics.to_dict(),
                'alerts': alerts,
                'checked_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Health check failed: {exc}")
            return {
                'status': HealthStatus.CRITICAL,
                'error': str(exc),
                'checked_at': timezone.now().isoformat(),
            }
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system metrics."""
        metrics = SystemMetrics()
        
        try:
            # CPU usage
            metrics.cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics.memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics.disk_percent = (disk.used / disk.total) * 100
            
            # Database connections
            metrics.database_connections = self._get_database_connections()
            
            # Cache hit rate
            metrics.cache_hit_rate = self._get_cache_hit_rate()
            
            # Queue size
            metrics.queue_size = self._get_queue_size()
            
            # Active bots
            metrics.active_bots = self._get_active_bots()
            
            # Processing rate (submissions per minute)
            metrics.processing_rate = self._get_processing_rate()
            
            # Error rate
            metrics.error_rate = self._get_error_rate()
            
            # Response time
            metrics.response_time = self._get_response_time()
            
        except Exception as exc:
            logger.error(f"Collect metrics failed: {exc}")
        
        return metrics
    
    def _get_database_connections(self) -> int:
        """Get database connection count."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        try:
            # This would depend on your cache backend
            # For Redis, you can use INFO stats
            cache_stats = cache.get('cache_stats')
            if cache_stats:
                hits = cache_stats.get('hits', 0)
                misses = cache_stats.get('misses', 0)
                total = hits + misses
                return (hits / total * 100) if total > 0 else 0.0
            return 0.0
        except Exception:
            return 0.0
    
    def _get_queue_size(self) -> int:
        """Get moderation queue size."""
        try:
            return ModerationQueue.objects.filter(status='pending').count()
        except Exception:
            return 0
    
    def _get_active_bots(self) -> int:
        """Get active bot count."""
        try:
            return TaskBot.objects.filter(status='running').count()
        except Exception:
            return 0
    
    def _get_processing_rate(self) -> float:
        """Get processing rate (submissions per minute)."""
        try:
            one_minute_ago = timezone.now() - timedelta(minutes=1)
            count = SuspiciousSubmission.objects.filter(
                created_at__gte=one_minute_ago
            ).count()
            return float(count)
        except Exception:
            return 0.0
    
    def _get_error_rate(self) -> float:
        """Get error rate (percentage)."""
        try:
            one_hour_ago = timezone.now() - timedelta(hours=1)
            total_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=one_hour_ago
            ).count()
            
            if total_submissions == 0:
                return 0.0
            
            failed_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=one_hour_ago,
                status='error'
            ).count()
            
            return (failed_submissions / total_submissions) * 100
        except Exception:
            return 0.0
    
    def _get_response_time(self) -> float:
        """Get average response time in seconds."""
        try:
            # This would measure actual API response times
            # For now, return a mock value
            return 0.5
        except Exception:
            return 0.0
    
    def _evaluate_health(self, metrics: SystemMetrics) -> str:
        """Evaluate overall health status."""
        critical_issues = []
        warning_issues = []
        
        # Check CPU
        if metrics.cpu_percent >= self.thresholds['cpu']['critical']:
            critical_issues.append('cpu')
        elif metrics.cpu_percent >= self.thresholds['cpu']['warning']:
            warning_issues.append('cpu')
        
        # Check memory
        if metrics.memory_percent >= self.thresholds['memory']['critical']:
            critical_issues.append('memory')
        elif metrics.memory_percent >= self.thresholds['memory']['warning']:
            warning_issues.append('memory')
        
        # Check disk
        if metrics.disk_percent >= self.thresholds['disk']['critical']:
            critical_issues.append('disk')
        elif metrics.disk_percent >= self.thresholds['disk']['warning']:
            warning_issues.append('disk')
        
        # Check database connections
        if metrics.database_connections >= self.thresholds['database_connections']['critical']:
            critical_issues.append('database_connections')
        elif metrics.database_connections >= self.thresholds['database_connections']['warning']:
            warning_issues.append('database_connections')
        
        # Check cache hit rate
        if metrics.cache_hit_rate <= self.thresholds['cache_hit_rate']['critical']:
            critical_issues.append('cache_hit_rate')
        elif metrics.cache_hit_rate <= self.thresholds['cache_hit_rate']['warning']:
            warning_issues.append('cache_hit_rate')
        
        # Check queue size
        if metrics.queue_size >= self.thresholds['queue_size']['critical']:
            critical_issues.append('queue_size')
        elif metrics.queue_size >= self.thresholds['queue_size']['warning']:
            warning_issues.append('queue_size')
        
        # Check error rate
        if metrics.error_rate >= self.thresholds['error_rate']['critical']:
            critical_issues.append('error_rate')
        elif metrics.error_rate >= self.thresholds['error_rate']['warning']:
            warning_issues.append('error_rate')
        
        # Check response time
        if metrics.response_time >= self.thresholds['response_time']['critical']:
            critical_issues.append('response_time')
        elif metrics.response_time >= self.thresholds['response_time']['warning']:
            warning_issues.append('response_time')
        
        # Determine overall status
        if critical_issues:
            return HealthStatus.CRITICAL
        elif warning_issues:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _generate_alerts(self, metrics: SystemMetrics, health_status: str) -> List[Dict[str, Any]]:
        """Generate alerts based on metrics and health status."""
        alerts = []
        
        if health_status == HealthStatus.CRITICAL:
            alerts.append({
                'level': 'critical',
                'message': 'System is in critical state',
                'timestamp': timezone.now().isoformat(),
            })
        elif health_status == HealthStatus.DEGRADED:
            alerts.append({
                'level': 'warning',
                'message': 'System performance is degraded',
                'timestamp': timezone.now().isoformat(),
            })
        
        # Add specific alerts for critical metrics
        if metrics.cpu_percent >= self.thresholds['cpu']['critical']:
            alerts.append({
                'level': 'critical',
                'message': f'CPU usage is critical: {metrics.cpu_percent:.1f}%',
                'metric': 'cpu_percent',
                'value': metrics.cpu_percent,
                'timestamp': timezone.now().isoformat(),
            })
        
        if metrics.memory_percent >= self.thresholds['memory']['critical']:
            alerts.append({
                'level': 'critical',
                'message': f'Memory usage is critical: {metrics.memory_percent:.1f}%',
                'metric': 'memory_percent',
                'value': metrics.memory_percent,
                'timestamp': timezone.now().isoformat(),
            })
        
        if metrics.queue_size >= self.thresholds['queue_size']['critical']:
            alerts.append({
                'level': 'critical',
                'message': f'Queue size is critical: {metrics.queue_size} items',
                'metric': 'queue_size',
                'value': metrics.queue_size,
                'timestamp': timezone.now().isoformat(),
            })
        
        return alerts
    
    def _store_health_check(self, metrics: SystemMetrics, health_status: str, alerts: List[Dict[str, Any]]) -> None:
        """Store health check results."""
        try:
            health_data = {
                'status': health_status,
                'metrics': metrics.to_dict(),
                'alerts': alerts,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Store in cache for 1 hour
            cache.set('health_check_latest', health_data, timeout=3600)
            
            # Store in history (last 24 hours of checks)
            history_key = 'health_check_history'
            history = cache.get(history_key, [])
            history.append(health_data)
            
            # Keep only last 24 hours of data (assuming checks every 5 minutes)
            if len(history) > 288:  # 24 * 60 / 5
                history = history[-288:]
            
            cache.set(history_key, history, timeout=86400)  # 24 hours
            
        except Exception as exc:
            logger.error(f"Store health check failed: {exc}")


class PerformanceMonitor:
    """Performance monitor for auto moderation system."""
    
    def __init__(self):
        self.metrics_history = []
        self.max_history_size = 1000
    
    def record_operation(self, operation_type: str, duration: float, 
                         success: bool = True, metadata: Dict[str, Any] = None) -> None:
        """
        Record an operation for performance tracking.
        
        Args:
            operation_type: Type of operation
            duration: Duration in seconds
            success: Whether operation was successful
            metadata: Additional metadata
        """
        try:
            record = {
                'operation_type': operation_type,
                'duration': duration,
                'success': success,
                'metadata': metadata or {},
                'timestamp': timezone.now().isoformat(),
            }
            
            self.metrics_history.append(record)
            
            # Keep history size limited
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size:]
            
        except Exception as exc:
            logger.error(f"Record operation failed: {exc}")
    
    def get_performance_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance statistics for the last N minutes.
        
        Args:
            minutes: Number of minutes to analyze
            
        Returns:
            Performance statistics
        """
        try:
            cutoff_time = timezone.now() - timedelta(minutes=minutes)
            
            # Filter records within time range
            recent_records = [
                record for record in self.metrics_history
                if timezone.make_aware(datetime.fromisoformat(record['timestamp'])) >= cutoff_time
            ]
            
            if not recent_records:
                return {
                    'total_operations': 0,
                    'success_rate': 0.0,
                    'avg_duration': 0.0,
                    'max_duration': 0.0,
                    'min_duration': 0.0,
                    'operations_per_minute': 0.0,
                    'period_minutes': minutes,
                }
            
            # Calculate statistics
            total_operations = len(recent_records)
            successful_operations = len([r for r in recent_records if r['success']])
            durations = [r['duration'] for r in recent_records]
            
            success_rate = (successful_operations / total_operations) * 100
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            operations_per_minute = total_operations / minutes
            
            # Group by operation type
            operation_stats = {}
            for record in recent_records:
                op_type = record['operation_type']
                if op_type not in operation_stats:
                    operation_stats[op_type] = {
                        'count': 0,
                        'success_count': 0,
                        'total_duration': 0.0,
                        'max_duration': 0.0,
                        'min_duration': float('inf'),
                    }
                
                stats = operation_stats[op_type]
                stats['count'] += 1
                if record['success']:
                    stats['success_count'] += 1
                stats['total_duration'] += record['duration']
                stats['max_duration'] = max(stats['max_duration'], record['duration'])
                stats['min_duration'] = min(stats['min_duration'], record['duration'])
            
            # Calculate averages for each operation type
            for op_type, stats in operation_stats.items():
                if stats['count'] > 0:
                    stats['success_rate'] = (stats['success_count'] / stats['count']) * 100
                    stats['avg_duration'] = stats['total_duration'] / stats['count']
                else:
                    stats['success_rate'] = 0.0
                    stats['avg_duration'] = 0.0
                if stats['min_duration'] == float('inf'):
                    stats['min_duration'] = 0.0
            
            return {
                'total_operations': total_operations,
                'success_rate': success_rate,
                'avg_duration': avg_duration,
                'max_duration': max_duration,
                'min_duration': min_duration,
                'operations_per_minute': operations_per_minute,
                'period_minutes': minutes,
                'operation_breakdown': operation_stats,
            }
            
        except Exception as exc:
            logger.error(f"Get performance stats failed: {exc}")
            return {'error': str(exc)}
    
    def get_slow_operations(self, threshold_seconds: float = 2.0, 
                           limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get slow operations above threshold.
        
        Args:
            threshold_seconds: Duration threshold in seconds
            limit: Maximum number of results
            
        Returns:
            List of slow operations
        """
        try:
            slow_operations = [
                record for record in self.metrics_history
                if record['duration'] >= threshold_seconds
            ]
            
            # Sort by duration (descending)
            slow_operations.sort(key=lambda x: x['duration'], reverse=True)
            
            return slow_operations[:limit]
            
        except Exception as exc:
            logger.error(f"Get slow operations failed: {exc}")
            return []


class AlertManager:
    """Alert manager for system notifications."""
    
    def __init__(self):
        self.alert_rules = self._initialize_alert_rules()
        self.alert_history = []
    
    def _initialize_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize alert rules."""
        return {
            'high_cpu': {
                'condition': lambda metrics: metrics.cpu_percent > 80,
                'message': 'High CPU usage detected',
                'severity': 'warning',
                'cooldown_minutes': 15,
            },
            'high_memory': {
                'condition': lambda metrics: metrics.memory_percent > 85,
                'message': 'High memory usage detected',
                'severity': 'warning',
                'cooldown_minutes': 15,
            },
            'queue_backlog': {
                'condition': lambda metrics: metrics.queue_size > 500,
                'message': 'Moderation queue backlog detected',
                'severity': 'critical',
                'cooldown_minutes': 5,
            },
            'high_error_rate': {
                'condition': lambda metrics: metrics.error_rate > 10,
                'message': 'High error rate detected',
                'severity': 'critical',
                'cooldown_minutes': 10,
            },
            'bot_failure': {
                'condition': lambda metrics: metrics.active_bots == 0,
                'message': 'No active bots detected',
                'severity': 'critical',
                'cooldown_minutes': 5,
            },
        }
    
    def check_alerts(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
        """
        Check for alerts based on metrics.
        
        Args:
            metrics: System metrics
            
        Returns:
            List of alerts
        """
        alerts = []
        current_time = timezone.now()
        
        for rule_name, rule in self.alert_rules.items():
            try:
                # Check cooldown
                if self._is_in_cooldown(rule_name, rule['cooldown_minutes']):
                    continue
                
                # Check condition
                if rule['condition'](metrics):
                    alert = {
                        'rule': rule_name,
                        'message': rule['message'],
                        'severity': rule['severity'],
                        'metrics': metrics.to_dict(),
                        'timestamp': current_time.isoformat(),
                    }
                    
                    alerts.append(alert)
                    self.alert_history.append(alert)
                    
                    # Set cooldown
                    self._set_cooldown(rule_name, rule['cooldown_minutes'])
                    
            except Exception as exc:
                logger.error(f"Alert rule '{rule_name}' failed: {exc}")
        
        return alerts
    
    def _is_in_cooldown(self, rule_name: str, cooldown_minutes: int) -> bool:
        """Check if rule is in cooldown period."""
        try:
            cooldown_key = f"alert_cooldown:{rule_name}"
            last_alert_time = cache.get(cooldown_key)
            
            if last_alert_time:
                last_time = timezone.make_aware(datetime.fromisoformat(last_alert_time))
                cooldown_end = last_time + timedelta(minutes=cooldown_minutes)
                return timezone.now() < cooldown_end
            
            return False
            
        except Exception:
            return False
    
    def _set_cooldown(self, rule_name: str, cooldown_minutes: int) -> None:
        """Set cooldown for alert rule."""
        try:
            cooldown_key = f"alert_cooldown:{rule_name}"
            cache.set(cooldown_key, timezone.now().isoformat(), timeout=cooldown_minutes * 60)
        except Exception as exc:
            logger.error(f"Set cooldown failed: {exc}")
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get alert history.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of alerts
        """
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            recent_alerts = [
                alert for alert in self.alert_history
                if timezone.make_aware(datetime.fromisoformat(alert['timestamp'])) >= cutoff_time
            ]
            
            return recent_alerts
            
        except Exception as exc:
            logger.error(f"Get alert history failed: {exc}")
            return []


# Global instances
health_checker = HealthChecker()
performance_monitor = PerformanceMonitor()
alert_manager = AlertManager()


# Utility functions
def check_system_health() -> Dict[str, Any]:
    """Check system health."""
    return health_checker.check_system_health()


def get_performance_stats(minutes: int = 60) -> Dict[str, Any]:
    """Get performance statistics."""
    return performance_monitor.get_performance_stats(minutes)


def record_operation(operation_type: str, duration: float, 
                   success: bool = True, metadata: Dict[str, Any] = None) -> None:
    """Record an operation for performance tracking."""
    performance_monitor.record_operation(operation_type, duration, success, metadata)


def get_slow_operations(threshold_seconds: float = 2.0, limit: int = 10) -> List[Dict[str, Any]]:
    """Get slow operations."""
    return performance_monitor.get_slow_operations(threshold_seconds, limit)


def get_alert_history(hours: int = 24) -> List[Dict[str, Any]]:
    """Get alert history."""
    return alert_manager.get_alert_history(hours)


# Initialize logging
logger.info("Monitoring module initialized with health checking and performance tracking")
