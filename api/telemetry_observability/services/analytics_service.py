"""
Analytics service for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Sum, Min, Max, Count

from ..models.metric_event import MetricEvent
from ..models.log_entry import LogEntry
from ..models.trace_span import TraceSpan
from ..models.alert import Alert
from ..models.health_status import HealthStatus


class AnalyticsService:
    """
    Service for analytics and reporting.
    """

    def __init__(self):
        """Initialize the analytics service."""
        pass

    def get_metric_analytics(self, name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get analytics for a specific metric.

        Args:
            name: Metric name
            hours: Number of hours to look back

        Returns:
            Dictionary with analytics data
        """
        since = timezone.now() - timedelta(hours=hours)

        metrics = MetricEvent.objects.filter(name=name, timestamp__gte=since)

        values = [m.value for m in metrics]

        if not values:
            return {
                'metric_name': name,
                'period_hours': hours,
                'count': 0,
                'avg': 0.0,
                'min': 0.0,
                'max': 0.0,
                'sum': 0.0,
                'std_dev': 0.0,
                'percentile_50': 0.0,
                'percentile_95': 0.0,
                'percentile_99': 0.0
            }

        import statistics

        sorted_values = sorted(values)

        return {
            'metric_name': name,
            'period_hours': hours,
            'count': len(values),
            'avg': round(statistics.mean(values), 2),
            'min': round(min(values), 2),
            'max': round(max(values), 2),
            'sum': round(sum(values), 2),
            'std_dev': round(statistics.stdev(values) if len(values) > 1 else 0, 2),
            'percentile_50': round(self._calculate_percentile(sorted_values, 50), 2),
            'percentile_95': round(self._calculate_percentile(sorted_values, 95), 2),
            'percentile_99': round(self._calculate_percentile(sorted_values, 99), 2)
        }

    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """
        Calculate percentile value.

        Args:
            values: Sorted list of values
            percentile: Percentile to calculate

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        index = int(len(values) * (percentile / 100))

        if index >= len(values):
            return values[-1]

        return values[index]

    def get_log_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get log analytics.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with log analytics
        """
        since = timezone.now() - timedelta(hours=hours)

        logs = LogEntry.objects.filter(timestamp__gte=since)

        # Count by level
        level_counts = {}
        for level in ['debug', 'info', 'warning', 'error', 'critical']:
            level_counts[level] = logs.filter(level=level).count()

        total_logs = logs.count()

        return {
            'period_hours': hours,
            'total_logs': total_logs,
            'level_counts': level_counts,
            'error_rate': round(
                (level_counts['error'] + level_counts['critical']) / total_logs * 100, 2
            ) if total_logs > 0 else 0.0
        }

    def get_trace_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get trace analytics.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with trace analytics
        """
        since = timezone.now() - timedelta(hours=hours)

        traces = TraceSpan.objects.filter(start_time__gte=since)

        # Count by status
        status_counts = {}
        for span_status in ['success', 'error', 'timeout']:
            status_counts[span_status] = traces.filter(status=span_status).count()

        total_traces = traces.count()

        # Average duration
        avg_duration = traces.filter(
            duration_ms__isnull=False
        ).aggregate(avg=Avg('duration_ms'))['avg'] or 0.0

        return {
            'period_hours': hours,
            'total_traces': total_traces,
            'status_counts': status_counts,
            'error_rate': round(
                status_counts['error'] / total_traces * 100, 2
            ) if total_traces > 0 else 0.0,
            'avg_duration_ms': round(avg_duration, 2)
        }

    def get_alert_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get alert analytics.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with alert analytics
        """
        since = timezone.now() - timedelta(hours=hours)

        alerts = Alert.objects.filter(triggered_at__gte=since)

        # Count by severity
        severity_counts = {}
        for severity in ['info', 'warning', 'error', 'critical']:
            severity_counts[severity] = alerts.filter(severity=severity).count()

        # Count by status
        status_counts = {}
        for alert_status in ['open', 'acknowledged', 'resolved']:
            status_counts[alert_status] = alerts.filter(status=alert_status).count()

        total_alerts = alerts.count()

        return {
            'period_hours': hours,
            'total_alerts': total_alerts,
            'severity_counts': severity_counts,
            'status_counts': status_counts,
            'resolution_rate': round(
                status_counts['resolved'] / total_alerts * 100, 2
            ) if total_alerts > 0 else 0.0
        }

    def get_health_analytics(self) -> Dict[str, Any]:
        """
        Get health analytics.

        Returns:
            Dictionary with health analytics
        """
        total_services = HealthStatus.objects.values('service_name').distinct().count()

        # Count by status
        status_counts = {}
        for health_status in ['healthy', 'degraded', 'unhealthy', 'unknown']:
            status_counts[health_status] = HealthStatus.objects.filter(
                status=health_status
            ).count()

        # Average health score
        avg_score = HealthStatus.objects.aggregate(avg=Avg('health_score'))['avg'] or 0.0

        return {
            'total_services': total_services,
            'status_counts': status_counts,
            'avg_health_score': round(avg_score, 2),
            'health_percentage': round(
                status_counts['healthy'] / total_services * 100, 2
            ) if total_services > 0 else 0.0
        }

    def get_service_analytics(self, service_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get analytics for a specific service.

        Args:
            service_name: Service name
            hours: Number of hours to look back

        Returns:
            Dictionary with service analytics
        """
        since = timezone.now() - timedelta(hours=hours)

        # Get metrics
        metric_count = MetricEvent.objects.filter(
            service=service_name, timestamp__gte=since
        ).count()

        # Get logs
        log_count = LogEntry.objects.filter(
            service=service_name, timestamp__gte=since
        ).count()
        error_log_count = LogEntry.objects.filter(
            service=service_name, timestamp__gte=since, level='error'
        ).count()

        # Get traces
        trace_count = TraceSpan.objects.filter(
            service=service_name, start_time__gte=since
        ).count()
        avg_duration = TraceSpan.objects.filter(
            service=service_name,
            start_time__gte=since,
            duration_ms__isnull=False
        ).aggregate(avg=Avg('duration_ms'))['avg'] or 0.0

        # Get alerts
        alert_count = Alert.objects.filter(
            service=service_name, triggered_at__gte=since
        ).count()

        # Get health status
        health = HealthStatus.objects.filter(service_name=service_name).first()

        return {
            'service_name': service_name,
            'period_hours': hours,
            'metric_count': metric_count,
            'log_count': log_count,
            'error_log_count': error_log_count,
            'error_rate': round(
                error_log_count / log_count * 100, 2
            ) if log_count > 0 else 0.0,
            'trace_count': trace_count,
            'avg_duration_ms': round(avg_duration, 2),
            'alert_count': alert_count,
            'health_status': health.status if health else 'unknown',
            'health_score': health.health_score if health else 0
        }

    def get_trend_data(
        self,
        metric_name: str,
        interval: str = 'hour',
        periods: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get trend data for a metric.

        Args:
            metric_name: Metric name
            interval: Time interval (hour, day)
            periods: Number of periods

        Returns:
            List of trend data points
        """
        # FIX: was incorrectly importing from .metrics (services/metrics.py which doesn't exist)
        # Correct path is ..metrics (telemetry_observability/metrics.py)
        from ..metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        # Calculate start time
        interval_map = {
            'hour': timedelta(hours=1),
            'day': timedelta(days=1)
        }

        delta = interval_map.get(interval, timedelta(hours=1))
        since = timezone.now() - (delta * periods)

        return aggregator.aggregate_by_time(metric_name, interval, since)
