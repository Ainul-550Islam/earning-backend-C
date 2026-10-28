"""
TelemetryService — high-level overview and cross-domain queries.
DRY: uses model managers directly for aggregations (not duplicating logic.py).
Decorated with @trace_operation for automatic distributed tracing.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count

from ..models.metric_event import MetricEvent
from ..models.log_entry import LogEntry
from ..models.trace_span import TraceSpan
from ..models.alert import Alert
from ..models.health_status import HealthStatus
from ..decorators import trace_operation, measure_time


class TelemetryService:
    """
    High-level cross-domain service.
    Provides overview queries that span multiple models.
    Domain-specific logic stays in logic.py → services/*.
    """

    def __init__(self):
        pass

    @trace_operation(service='telemetry-service', operation_name='get_overview')
    def get_overview(self, hours: int = 24) -> Dict[str, Any]:
        """
        Full system overview for the given time window.

        Args:
            hours: Look-back window in hours

        Returns:
            Dict with counts across all telemetry domains
        """
        since = timezone.now() - timedelta(hours=hours)

        return {
            'period_hours':    hours,
            'metrics': {
                'total':     MetricEvent.objects.filter(timestamp__gte=since).count(),
                'by_type':   dict(
                    MetricEvent.objects.filter(timestamp__gte=since)
                    .values_list('metric_type')
                    .annotate(c=Count('id'))
                    .values_list('metric_type', 'c')
                ),
            },
            'logs': {
                'total':    LogEntry.objects.filter(timestamp__gte=since).count(),
                'errors':   LogEntry.objects.filter(
                                timestamp__gte=since, level__in=['error', 'critical']).count(),
                'by_level': dict(
                    LogEntry.objects.filter(timestamp__gte=since)
                    .values_list('level')
                    .annotate(c=Count('id'))
                    .values_list('level', 'c')
                ),
            },
            'traces': {
                'total':      TraceSpan.objects.filter(start_time__gte=since).count(),
                'errors':     TraceSpan.objects.filter(
                                  start_time__gte=since, status='error').count(),
                'avg_duration_ms': round(
                    TraceSpan.objects.filter(
                        start_time__gte=since, duration_ms__isnull=False
                    ).aggregate(avg=Avg('duration_ms'))['avg'] or 0.0, 2
                ),
            },
            'alerts': {
                'total':    Alert.objects.filter(triggered_at__gte=since).count(),
                'open':     Alert.objects.filter(status='open').count(),
                'critical': Alert.objects.filter(severity='critical', status='open').count(),
            },
            'health': {
                'total_services':    HealthStatus.objects.values('service_name').distinct().count(),
                'healthy':           HealthStatus.objects.filter(status='healthy').count(),
                'unhealthy':         HealthStatus.objects.filter(
                                         status__in=['degraded', 'unhealthy']).count(),
                'avg_health_score':  round(
                    HealthStatus.objects.aggregate(avg=Avg('health_score'))['avg'] or 0.0, 2
                ),
            },
        }

    @trace_operation(service='telemetry-service', operation_name='get_service_overview')
    def get_service_overview(self, service_name: str, hours: int = 24) -> Dict[str, Any]:
        """
        Overview scoped to a single service.

        Args:
            service_name: Service to query
            hours:        Look-back window

        Returns:
            Dict with per-service counts
        """
        since = timezone.now() - timedelta(hours=hours)

        health = HealthStatus.objects.filter(service_name=service_name).first()

        return {
            'service_name': service_name,
            'period_hours': hours,
            'metrics_count': MetricEvent.objects.filter(
                service=service_name, timestamp__gte=since).count(),
            'log_count': LogEntry.objects.filter(
                service=service_name, timestamp__gte=since).count(),
            'error_log_count': LogEntry.objects.filter(
                service=service_name, timestamp__gte=since,
                level__in=['error', 'critical']).count(),
            'trace_count': TraceSpan.objects.filter(
                service=service_name, start_time__gte=since).count(),
            'alert_count': Alert.objects.filter(
                service=service_name, triggered_at__gte=since).count(),
            'open_alerts': Alert.objects.filter(
                service=service_name, status='open').count(),
            'health_status': health.status if health else 'unknown',
            'health_score':  health.health_score if health else 0,
        }

    @trace_operation(service='telemetry-service', operation_name='get_environment_overview')
    def get_environment_overview(self, environment: str, hours: int = 24) -> Dict[str, Any]:
        """
        Overview scoped to a single environment (production, staging, etc.).

        Args:
            environment: Environment to query
            hours:       Look-back window

        Returns:
            Dict with per-environment counts
        """
        since = timezone.now() - timedelta(hours=hours)

        return {
            'environment':   environment,
            'period_hours':  hours,
            'metrics_count': MetricEvent.objects.filter(
                environment=environment, timestamp__gte=since).count(),
            'log_count': LogEntry.objects.filter(
                environment=environment, timestamp__gte=since).count(),
            'alert_count': Alert.objects.filter(
                environment=environment, triggered_at__gte=since).count(),
            'open_alerts': Alert.objects.filter(
                environment=environment, status='open').count(),
            'services': list(
                HealthStatus.objects.filter(environment=environment)
                .values('service_name', 'status', 'health_score')
                .order_by('service_name')
            ),
        }

    def search_telemetry(
        self,
        query: str,
        service: Optional[str] = None,
        hours: int = 24,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Cross-domain free-text search across logs and alerts.

        Args:
            query:   Search string
            service: Optional service filter
            hours:   Look-back window
            limit:   Max results per domain

        Returns:
            Dict with matching logs and alerts
        """
        since = timezone.now() - timedelta(hours=hours)

        log_qs   = LogEntry.objects.filter(message__icontains=query, timestamp__gte=since)
        alert_qs = Alert.objects.filter(name__icontains=query, triggered_at__gte=since)

        if service:
            log_qs   = log_qs.filter(service=service)
            alert_qs = alert_qs.filter(service=service)

        return {
            'query':  query,
            'logs':   list(
                log_qs.order_by('-timestamp')[:limit]
                .values('id', 'level', 'message', 'service', 'timestamp')
            ),
            'alerts': list(
                alert_qs.order_by('-triggered_at')[:limit]
                .values('id', 'name', 'severity', 'status', 'service', 'triggered_at')
            ),
        }
