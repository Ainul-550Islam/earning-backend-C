"""Performance Monitor

This module provides performance monitoring for integration system
with comprehensive metrics collection and analysis.
"""

import logging
import time
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .integ_constants import HealthStatus

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Performance metrics collector."""
    
    def __init__(self):
        """Initialize the performance metrics."""
        self.logger = logger
        self.metrics = {}
        self.start_time = timezone.now()
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load performance monitoring configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_PERFORMANCE_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.metrics_retention = self.config.get('metrics_retention', 86400)  # 24 hours
            self.alert_thresholds = self.config.get('alert_thresholds', {})
            
        except Exception as e:
            self.logger.error(f"Error loading performance configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.metrics_retention = 86400
            self.alert_thresholds = {}
    
    def record_metric(self, metric_name: str, value: float, tags: Dict[str, Any] = None):
        """
        Record a performance metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags
        """
        try:
            if not self.enabled:
                return
            
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            
            metric_data = {
                'value': value,
                'timestamp': timezone.now(),
                'tags': tags or {}
            }
            
            self.metrics[metric_name].append(metric_data)
            
            # Limit metrics retention
            self._cleanup_metrics(metric_name)
            
            # Check for alerts
            self._check_alerts(metric_name, value)
            
        except Exception as e:
            self.logger.error(f"Error recording metric {metric_name}: {str(e)}")
    
    def _cleanup_metrics(self, metric_name: str):
        """Clean up old metrics."""
        try:
            cutoff_time = timezone.now() - timedelta(seconds=self.metrics_retention)
            
            self.metrics[metric_name] = [
                metric for metric in self.metrics[metric_name]
                if metric['timestamp'] >= cutoff_time
            ]
            
        except Exception as e:
            self.logger.error(f"Error cleaning up metrics {metric_name}: {str(e)}")
    
    def _check_alerts(self, metric_name: str, value: float):
        """Check for performance alerts."""
        try:
            if metric_name in self.alert_thresholds:
                threshold = self.alert_thresholds[metric_name]
                
                if 'warning' in threshold and value >= threshold['warning']:
                    self.logger.warning(f"Performance warning: {metric_name} = {value} (threshold: {threshold['warning']})")
                
                if 'critical' in threshold and value >= threshold['critical']:
                    self.logger.critical(f"Performance critical: {metric_name} = {value} (threshold: {threshold['critical']})")
            
        except Exception as e:
            self.logger.error(f"Error checking alerts for {metric_name}: {str(e)}")
    
    def get_metric_stats(self, metric_name: str, since: datetime = None) -> Dict[str, Any]:
        """
        Get statistics for a metric.
        
        Args:
            metric_name: Name of the metric
            since: Optional start time
            
        Returns:
            Metric statistics
        """
        try:
            if metric_name not in self.metrics:
                return {'error': f'Metric {metric_name} not found'}
            
            metrics = self.metrics[metric_name]
            
            # Filter by time
            if since:
                metrics = [m for m in metrics if m['timestamp'] >= since]
            
            if not metrics:
                return {'error': f'No metrics found for {metric_name} since {since}'}
            
            values = [m['value'] for m in metrics]
            
            return {
                'metric_name': metric_name,
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'latest': values[-1],
                'oldest': values[0],
                'period': {
                    'start': metrics[0]['timestamp'].isoformat(),
                    'end': metrics[-1]['timestamp'].isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting metric stats for {metric_name}: {str(e)}")
            return {'error': str(e)}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics summary."""
        try:
            summary = {
                'total_metrics': len(self.metrics),
                'metrics': {},
                'system_info': self._get_system_info()
            }
            
            for metric_name in self.metrics:
                summary['metrics'][metric_name] = self.get_metric_stats(metric_name)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting all metrics: {str(e)}")
            return {'error': str(e)}
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'uptime_seconds': (timezone.now() - self.start_time).total_seconds()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system info: {str(e)}")
            return {}


class PerformanceMonitor:
    """
    Main performance monitor for integration system.
    Provides comprehensive performance monitoring and metrics collection.
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.logger = logger
        self.metrics = PerformanceMetrics()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize monitoring
        self._initialize_monitoring()
    
    def _load_configuration(self):
        """Load monitor configuration."""
        try:
            self.config = getattr(settings, 'WEBHOOK_PERFORMANCE_MONITOR_CONFIG', {})
            self.enabled = self.config.get('enabled', True)
            self.default_timeout = self.config.get('default_timeout', 30)
            self.track_slow_queries = self.config.get('track_slow_queries', True)
            self.slow_query_threshold = self.config.get('slow_query_threshold', 1.0)
            
        except Exception as e:
            self.logger.error(f"Error loading performance monitor configuration: {str(e)}")
            self.config = {}
            self.enabled = True
            self.default_timeout = 30
            self.track_slow_queries = True
            self.slow_query_threshold = 1.0
    
    def _initialize_monitoring(self):
        """Initialize the performance monitor."""
        try:
            # Start background monitoring
            self._start_background_monitoring()
            
            self.logger.info("Performance monitor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing performance monitor: {str(e)}")
    
    def _start_background_monitoring(self):
        """Start background monitoring."""
        try:
            # This would integrate with your background task system
            # For now, just log that monitoring is enabled
            self.logger.info("Background monitoring enabled")
            
        except Exception as e:
            self.logger.error(f"Error starting background monitoring: {str(e)}")
    
    def measure_event(self, event_type: str) -> 'EventMeasurement':
        """
        Measure event performance.
        
        Args:
            event_type: Type of event
            
        Returns:
            Event measurement context manager
        """
        return EventMeasurement(self.metrics, event_type)
    
    def measure_handler(self, handler_name: str) -> 'HandlerMeasurement':
        """
        Measure handler performance.
        
        Args:
            handler_name: Name of the handler
            
        Returns:
            Handler measurement context manager
        """
        return HandlerMeasurement(self.metrics, handler_name)
    
    def measure_adapter(self, adapter_type: str) -> 'AdapterMeasurement':
        """
        Measure adapter performance.
        
        Args:
            adapter_type: Type of adapter
            
        Returns:
            Adapter measurement context manager
        """
        return AdapterMeasurement(self.metrics, adapter_type)
    
    def measure_bridge(self, bridge_type: str) -> 'BridgeMeasurement':
        """
        Measure bridge performance.
        
        Args:
            bridge_type: Type of bridge
            
        Returns:
            Bridge measurement context manager
        """
        return BridgeMeasurement(self.metrics, bridge_type)
    
    def measure_validation(self, validation_type: str) -> 'ValidationMeasurement':
        """
        Measure validation performance.
        
        Args:
            validation_type: Type of validation
            
        Returns:
            Validation measurement context manager
        """
        return ValidationMeasurement(self.metrics, validation_type)
    
    def measure_auth(self, auth_type: str) -> 'AuthMeasurement':
        """
        Measure authentication performance.
        
        Args:
            auth_type: Type of authentication
            
        Returns:
            Auth measurement context manager
        """
        return AuthMeasurement(self.metrics, auth_type)
    
    def measure_fallback(self, fallback_type: str) -> 'FallbackMeasurement':
        """
        Measure fallback performance.
        
        Args:
            fallback_type: Type of fallback
            
        Returns:
            Fallback measurement context manager
        """
        return FallbackMeasurement(self.metrics, fallback_type)
    
    def record_custom_metric(self, metric_name: str, value: float, tags: Dict[str, Any] = None):
        """
        Record a custom metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags
        """
        self.metrics.record_metric(metric_name, value, tags)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics.
        
        Returns:
            System metrics
        """
        try:
            return self.metrics._get_system_info()
            
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {str(e)}")
            return {}
    
    def get_uptime(self) -> float:
        """
        Get system uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        try:
            return (timezone.now() - self.metrics.start_time).total_seconds()
            
        except Exception as e:
            self.logger.error(f"Error getting uptime: {str(e)}")
            return 0.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.
        
        Returns:
            Performance summary
        """
        try:
            return {
                'enabled': self.enabled,
                'uptime_seconds': self.get_uptime(),
                'metrics': self.metrics.get_all_metrics(),
                'system_info': self.metrics._get_system_info()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance summary: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of performance monitor.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check metrics collection
            health_status['components']['metrics'] = {
                'status': HealthStatus.HEALTHY,
                'total_metrics': len(self.metrics.metrics),
                'enabled': self.enabled
            }
            
            # Check system resources
            system_info = self.metrics._get_system_info()
            
            if system_info.get('cpu_percent', 0) > 90:
                health_status['overall'] = HealthStatus.DEGRADED
            
            if system_info.get('memory_percent', 0) > 90:
                health_status['overall'] = HealthStatus.DEGRADED
            
            if system_info.get('disk_percent', 0) > 90:
                health_status['overall'] = HealthStatus.DEGRADED
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }


class MeasurementContext:
    """Base class for measurement contexts."""
    
    def __init__(self, metrics: PerformanceMetrics, measurement_type: str):
        """Initialize the measurement context."""
        self.metrics = metrics
        self.measurement_type = measurement_type
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """Enter measurement context."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit measurement context."""
        self.end_time = time.time()
        
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            self._record_measurement(duration)
    
    def _record_measurement(self, duration: float):
        """Record the measurement."""
        raise NotImplementedError("Subclasses must implement _record_measurement")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get measurement metrics."""
        if self.start_time and self.end_time:
            return {
                'duration': self.end_time - self.start_time,
                'measurement_type': self.measurement_type,
                'start_time': self.start_time,
                'end_time': self.end_time
            }
        return {}


class EventMeasurement(MeasurementContext):
    """Event performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, event_type: str):
        """Initialize the event measurement."""
        super().__init__(metrics, 'event')
        self.event_type = event_type
    
    def _record_measurement(self, duration: float):
        """Record event measurement."""
        self.metrics.record_metric(
            f'event.{self.event_type}.duration',
            duration,
            {'event_type': self.event_type}
        )
        
        self.metrics.record_metric(
            f'event.{self.event_type}.count',
            1,
            {'event_type': self.event_type}
        )


class HandlerMeasurement(MeasurementContext):
    """Handler performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, handler_name: str):
        """Initialize the handler measurement."""
        super().__init__(metrics, 'handler')
        self.handler_name = handler_name
    
    def _record_measurement(self, duration: float):
        """Record handler measurement."""
        self.metrics.record_metric(
            f'handler.{self.handler_name}.duration',
            duration,
            {'handler_name': self.handler_name}
        )
        
        self.metrics.record_metric(
            f'handler.{self.handler_name}.count',
            1,
            {'handler_name': self.handler_name}
        )


class AdapterMeasurement(MeasurementContext):
    """Adapter performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, adapter_type: str):
        """Initialize the adapter measurement."""
        super().__init__(metrics, 'adapter')
        self.adapter_type = adapter_type
    
    def _record_measurement(self, duration: float):
        """Record adapter measurement."""
        self.metrics.record_metric(
            f'adapter.{self.adapter_type}.duration',
            duration,
            {'adapter_type': self.adapter_type}
        )
        
        self.metrics.record_metric(
            f'adapter.{self.adapter_type}.count',
            1,
            {'adapter_type': self.adapter_type}
        )


class BridgeMeasurement(MeasurementContext):
    """Bridge performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, bridge_type: str):
        """Initialize the bridge measurement."""
        super().__init__(metrics, 'bridge')
        self.bridge_type = bridge_type
    
    def _record_measurement(self, duration: float):
        """Record bridge measurement."""
        self.metrics.record_metric(
            f'bridge.{self.bridge_type}.duration',
            duration,
            {'bridge_type': self.bridge_type}
        )
        
        self.metrics.record_metric(
            f'bridge.{self.bridge_type}.count',
            1,
            {'bridge_type': self.bridge_type}
        )


class ValidationMeasurement(MeasurementContext):
    """Validation performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, validation_type: str):
        """Initialize the validation measurement."""
        super().__init__(metrics, 'validation')
        self.validation_type = validation_type
    
    def _record_measurement(self, duration: float):
        """Record validation measurement."""
        self.metrics.record_metric(
            f'validation.{self.validation_type}.duration',
            duration,
            {'validation_type': self.validation_type}
        )
        
        self.metrics.record_metric(
            f'validation.{self.validation_type}.count',
            1,
            {'validation_type': self.validation_type}
        )


class AuthMeasurement(MeasurementContext):
    """Authentication performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, auth_type: str):
        """Initialize the auth measurement."""
        super().__init__(metrics, 'auth')
        self.auth_type = auth_type
    
    def _record_measurement(self, duration: float):
        """Record auth measurement."""
        self.metrics.record_metric(
            f'auth.{self.auth_type}.duration',
            duration,
            {'auth_type': self.auth_type}
        )
        
        self.metrics.record_metric(
            f'auth.{self.auth_type}.count',
            1,
            {'auth_type': self.auth_type}
        )


class FallbackMeasurement(MeasurementContext):
    """Fallback performance measurement."""
    
    def __init__(self, metrics: PerformanceMetrics, fallback_type: str):
        """Initialize the fallback measurement."""
        super().__init__(metrics, 'fallback')
        self.fallback_type = fallback_type
    
    def _record_measurement(self, duration: float):
        """Record fallback measurement."""
        self.metrics.record_metric(
            f'fallback.{self.fallback_type}.duration',
            duration,
            {'fallback_type': self.fallback_type}
        )
        
        self.metrics.record_metric(
            f'fallback.{self.fallback_type}.count',
            1,
            {'fallback_type': self.fallback_type}
        )
