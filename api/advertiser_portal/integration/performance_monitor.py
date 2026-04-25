"""
Performance Monitor for Inter-Module Communications

This module provides comprehensive monitoring and logging for all
inter-module communications with latency tracking and performance metrics.
"""

import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from contextlib import contextmanager

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = timezone.now()


class PerformanceMonitor:
    """
    High-performance monitoring system for inter-module communications.
    
    Tracks latency, success rates, and performance metrics with
    configurable alerting and reporting.
    """
    
    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.active_operations: Dict[str, float] = {}
        self.lock = threading.Lock()
        
        # Performance targets
        self.CRITICAL_LATENCY_MS = 50
        self.STANDARD_LATENCY_MS = 200
        self.SLOW_OPERATION_MS = 500
        
        # Alert thresholds
        self.ERROR_RATE_THRESHOLD = 0.05  # 5%
        self.SLOW_OPERATION_THRESHOLD = 0.1  # 10%
        
    @contextmanager
    def measure(self, operation: str, metadata: Dict[str, Any] = None):
        """
        Context manager for measuring operation performance.
        
        Args:
            operation: Name of the operation being measured
            metadata: Additional metadata to store with the metric
            
        Yields:
            None
        """
        start_time = time.time()
        operation_id = f"{operation}_{start_time}"
        
        with self.lock:
            self.active_operations[operation_id] = start_time
        
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            metric = PerformanceMetric(
                operation=operation,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )
            
            self._record_metric(metric)
            
            with self.lock:
                self.active_operations.pop(operation_id, None)
    
    def record_operation(self, operation: str, duration_ms: float, 
                        success: bool = True, error_message: str = None,
                        metadata: Dict[str, Any] = None):
        """
        Manually record an operation metric.
        
        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            error_message: Error message if operation failed
            metadata: Additional metadata
        """
        metric = PerformanceMetric(
            operation=operation,
            start_time=time.time() - (duration_ms / 1000),
            end_time=time.time(),
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )
        
        self._record_metric(metric)
    
    def _record_metric(self, metric: PerformanceMetric):
        """Record a performance metric."""
        with self.lock:
            self.metrics[metric.operation].append(metric)
        
        # Check for performance alerts
        self._check_performance_alerts(metric)
        
        # Log slow operations
        if metric.duration_ms > self.SLOW_OPERATION_MS:
            logger.warning(
                f"Slow operation detected: {metric.operation} took {metric.duration_ms:.2f}ms"
            )
        
        # Log errors
        if not metric.success:
            logger.error(
                f"Operation failed: {metric.operation} - {metric.error_message}"
            )
    
    def _check_performance_alerts(self, metric: PerformanceMetric):
        """Check for performance alerts and trigger them if needed."""
        operation_metrics = list(self.metrics[metric.operation])
        
        if len(operation_metrics) < 10:  # Need enough data for meaningful alerts
            return
        
        # Calculate recent metrics (last 50 operations or last 5 minutes)
        recent_metrics = operation_metrics[-50:]
        recent_time = timezone.now() - timedelta(minutes=5)
        recent_metrics = [m for m in recent_metrics if m.timestamp > recent_time]
        
        if len(recent_metrics) < 5:
            return
        
        # Check error rate
        error_rate = sum(1 for m in recent_metrics if not m.success) / len(recent_metrics)
        if error_rate > self.ERROR_RATE_THRESHOLD:
            self._trigger_alert('high_error_rate', {
                'operation': metric.operation,
                'error_rate': error_rate,
                'recent_operations': len(recent_metrics)
            })
        
        # Check slow operation rate
        slow_rate = sum(1 for m in recent_metrics if m.duration_ms > self.SLOW_OPERATION_MS) / len(recent_metrics)
        if slow_rate > self.SLOW_OPERATION_THRESHOLD:
            self._trigger_alert('high_slow_rate', {
                'operation': metric.operation,
                'slow_rate': slow_rate,
                'recent_operations': len(recent_metrics)
            })
    
    def _trigger_alert(self, alert_type: str, data: Dict[str, Any]):
        """Trigger a performance alert."""
        logger.warning(f"Performance alert: {alert_type} - {data}")
        
        # Store alert in cache for monitoring
        alert_key = f"perf_alert_{alert_type}_{data['operation']}_{int(time.time())}"
        cache.set(alert_key, {
            'type': alert_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }, timeout=3600)  # Keep for 1 hour
    
    def get_operation_stats(self, operation: str, minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance statistics for an operation.
        
        Args:
            operation: Name of the operation
            minutes: Number of minutes to look back
            
        Returns:
            Dictionary with performance statistics
        """
        operation_metrics = list(self.metrics[operation])
        
        if not operation_metrics:
            return {
                'operation': operation,
                'total_operations': 0,
                'avg_duration_ms': 0,
                'success_rate': 1.0,
                'error_rate': 0.0,
                'slow_rate': 0.0
            }
        
        # Filter by time window
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        recent_metrics = [m for m in operation_metrics if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            recent_metrics = operation_metrics[-100:]  # Last 100 operations
        
        # Calculate statistics
        durations = [m.duration_ms for m in recent_metrics]
        successes = [m for m in recent_metrics if m.success]
        slow_operations = [m for m in recent_metrics if m.duration_ms > self.SLOW_OPERATION_MS]
        
        return {
            'operation': operation,
            'total_operations': len(recent_metrics),
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'min_duration_ms': min(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
            'median_duration_ms': sorted(durations)[len(durations) // 2] if durations else 0,
            'success_rate': len(successes) / len(recent_metrics) if recent_metrics else 1.0,
            'error_rate': (len(recent_metrics) - len(successes)) / len(recent_metrics) if recent_metrics else 0.0,
            'slow_rate': len(slow_operations) / len(recent_metrics) if recent_metrics else 0.0,
            'period_minutes': minutes,
            'last_updated': timezone.now().isoformat()
        }
    
    def get_all_stats(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance statistics for all operations.
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            Dictionary with all performance statistics
        """
        all_stats = {}
        
        for operation in self.metrics.keys():
            all_stats[operation] = self.get_operation_stats(operation, minutes)
        
        # Add summary statistics
        all_stats['_summary'] = {
            'total_operations': sum(stats['total_operations'] for stats in all_stats.values()),
            'total_errors': sum(stats['total_operations'] * stats['error_rate'] for stats in all_stats.values()),
            'avg_success_rate': sum(stats['success_rate'] for stats in all_stats.values()) / len(all_stats) if all_stats else 1.0,
            'monitored_operations': len(self.metrics),
            'period_minutes': minutes,
            'last_updated': timezone.now().isoformat()
        }
        
        return all_stats
    
    def get_active_operations(self) -> Dict[str, Any]:
        """Get currently active operations."""
        with self.lock:
            current_time = time.time()
            active_ops = {}
            
            for op_id, start_time in self.active_operations.items():
                duration_ms = (current_time - start_time) * 1000
                operation = op_id.rsplit('_', 1)[0]  # Extract operation name
                
                if operation not in active_ops:
                    active_ops[operation] = []
                
                active_ops[operation].append({
                    'operation_id': op_id,
                    'start_time': start_time,
                    'duration_ms': duration_ms,
                    'is_slow': duration_ms > self.SLOW_OPERATION_MS
                })
        
        return active_ops
    
    def clear_metrics(self, operation: str = None):
        """Clear performance metrics."""
        with self.lock:
            if operation:
                self.metrics[operation].clear()
            else:
                self.metrics.clear()
    
    def export_metrics(self, operation: str = None, minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Export performance metrics for analysis.
        
        Args:
            operation: Specific operation to export (None for all)
            minutes: Time window in minutes
            
        Returns:
            List of metric dictionaries
        """
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        exported_metrics = []
        
        operations = [operation] if operation else self.metrics.keys()
        
        for op in operations:
            for metric in self.metrics[op]:
                if metric.timestamp > cutoff_time:
                    exported_metrics.append(asdict(metric))
        
        return exported_metrics


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# Decorator for automatic performance monitoring
def monitor_performance(operation: str = None, metadata: Dict[str, Any] = None):
    """
    Decorator for automatic performance monitoring of functions.
    
    Args:
        operation: Operation name (defaults to function name)
        metadata: Additional metadata to record
        
    Returns:
        Decorated function
    """
    def decorator(func):
        op_name = operation or f"{func.__module__}.{func.__name__}"
        
        def wrapper(*args, **kwargs):
            with performance_monitor.measure(op_name, metadata):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Export main classes
__all__ = [
    'PerformanceMonitor',
    'PerformanceMetric',
    'performance_monitor',
    'monitor_performance',
]
