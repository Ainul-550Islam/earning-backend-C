"""
Analytics ViewSet for Telemetry Observability.
DRY: delegates ALL logic to AnalyticsService.
Fixes: missing Count import from original upload.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
# FIX: Count was used in original but not imported
from django.db.models import Avg, Sum, Min, Max, Count

from ..permissions import TelemetryBasePermission
from ..mixins import TelemetryMixin, ResponseMixin, CacheMixin
from ..services.analytics_service import AnalyticsService
from ..serializers.analytics_serializer import (
    MetricAnalyticsSerializer,
    LogAnalyticsSerializer,
    TraceAnalyticsSerializer,
    AlertAnalyticsSerializer,
    HealthAnalyticsSerializer,
    ServiceAnalyticsSerializer,
    OverviewSerializer,
)


class AnalyticsViewSet(TelemetryMixin, ResponseMixin, CacheMixin, viewsets.ViewSet):
    """
    Read-only ViewSet for analytics — no model CRUD.

    GET /api/v1/telemetry/analytics/overview/       → system overview
    GET /api/v1/telemetry/analytics/metrics/        → metric analytics
    GET /api/v1/telemetry/analytics/logs/           → log analytics
    GET /api/v1/telemetry/analytics/traces/         → trace analytics
    GET /api/v1/telemetry/analytics/alerts/         → alert analytics
    GET /api/v1/telemetry/analytics/health/         → health analytics
    GET /api/v1/telemetry/analytics/service/        → per-service
    GET /api/v1/telemetry/analytics/trend/          → time-series trend
    GET /api/v1/telemetry/analytics/compare/        → cross-service compare
    """

    permission_classes = [TelemetryBasePermission]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._svc = AnalyticsService()

    def _hours(self, request, default=24):
        """DRY: parse ?hours= used by every action."""
        try:
            return int(request.query_params.get('hours', default))
        except ValueError:
            return None

    def list(self, request):
        """
        GET /analytics/                  → overview (default)
        GET /analytics/?action=<name>    → dispatch to the named sub-resource,
                                            same as GET /analytics/<name>/
        """
        action_name = request.query_params.get('action')
        if not action_name or action_name == 'overview':
            return self._overview(request)

        dispatch = {
            'metrics': self.metrics,
            'logs': self.logs,
            'traces': self.traces,
            'alerts': self.alerts,
            'health': self.health,
            'service': self.service,
            'trend': self.trend,
            'compare': self.compare,
        }
        handler = dispatch.get(action_name)
        if handler is None:
            return Response(
                {'error': f"Unknown action '{action_name}'.",
                 'valid_actions': ['overview'] + list(dispatch.keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return handler(request)

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        return self._overview(request)

    def _overview(self, request):
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")

        from django.utils import timezone
        from datetime import timedelta
        from ..models.metric_event import MetricEvent
        from ..models.log_entry import LogEntry
        from ..models.trace_span import TraceSpan
        from ..models.alert import Alert
        from ..models.health_status import HealthStatus

        since = timezone.now() - timedelta(hours=hours)
        data  = {
            'period_hours':       hours,
            'total_metrics':      MetricEvent.objects.filter(timestamp__gte=since).count(),
            'total_logs':         LogEntry.objects.filter(timestamp__gte=since).count(),
            'total_traces':       TraceSpan.objects.filter(start_time__gte=since).count(),
            'total_alerts':       Alert.objects.filter(triggered_at__gte=since).count(),
            'open_alerts':        Alert.objects.filter(status='open').count(),
            'critical_alerts':    Alert.objects.filter(severity='critical', status='open').count(),
            'healthy_services':   HealthStatus.objects.filter(status='healthy').count(),
            'unhealthy_services': HealthStatus.objects.filter(
                                      status__in=['degraded', 'unhealthy']).count(),
            'avg_health_score':   round(
                HealthStatus.objects.aggregate(avg=Avg('health_score'))['avg'] or 0.0, 2
            ),
        }
        return Response(OverviewSerializer(data).data)

    @action(detail=False, methods=['get'], url_path='metrics')
    def metrics(self, request):
        """GET /analytics/metrics/?name=<name>&hours=24"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            MetricAnalyticsSerializer(self._svc.get_metric_analytics(name, hours=hours)).data
        )

    @action(detail=False, methods=['get'], url_path='logs')
    def logs(self, request):
        """GET /analytics/logs/?hours=24"""
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            LogAnalyticsSerializer(self._svc.get_log_analytics(hours=hours)).data
        )

    @action(detail=False, methods=['get'], url_path='traces')
    def traces(self, request):
        """GET /analytics/traces/?hours=24"""
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            TraceAnalyticsSerializer(self._svc.get_trace_analytics(hours=hours)).data
        )

    @action(detail=False, methods=['get'], url_path='alerts')
    def alerts(self, request):
        """GET /analytics/alerts/?hours=24"""
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            AlertAnalyticsSerializer(self._svc.get_alert_analytics(hours=hours)).data
        )

    @action(detail=False, methods=['get'], url_path='health')
    def health(self, request):
        """GET /analytics/health/"""
        return Response(HealthAnalyticsSerializer(self._svc.get_health_analytics()).data)

    @action(detail=False, methods=['get'], url_path='service')
    def service(self, request):
        """GET /analytics/service/?service=<name>&hours=24"""
        svc_name = request.query_params.get('service')
        if not svc_name:
            return self.error_response("'service' query parameter is required.")
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            ServiceAnalyticsSerializer(
                self._svc.get_service_analytics(svc_name, hours=hours)
            ).data
        )

    @action(detail=False, methods=['get'], url_path='trend')
    def trend(self, request):
        """GET /analytics/trend/?name=<name>&interval=hour|day&periods=24"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        interval = request.query_params.get('interval', 'hour')
        try:
            periods = int(request.query_params.get('periods', 24))
        except ValueError:
            return self.error_response("'periods' must be a valid integer.")
        data = self._svc.get_trend_data(name, interval=interval, periods=periods)
        return Response({'name': name, 'interval': interval, 'data': data})

    @action(detail=False, methods=['get'], url_path='compare')
    def compare(self, request):
        """
        GET /analytics/compare/?services=svc1,svc2&hours=24
        Compare analytics across multiple services side by side.
        """
        raw = request.query_params.get('services', '')
        services = [s.strip() for s in raw.split(',') if s.strip()]
        if not services:
            return self.error_response("'services' query parameter is required (comma-separated).")
        hours = self._hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")

        result = {}
        for svc in services:
            result[svc] = self._svc.get_service_analytics(svc, hours=hours)
        return Response({'period_hours': hours, 'comparison': result})
