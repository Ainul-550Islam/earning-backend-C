"""
Analytics views for Telemetry Observability.
Upgraded from function-based views to DRF APIView (CBV).
DRY: delegates ALL logic to AnalyticsService — no business logic here.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..permissions import TelemetryBasePermission
from ..mixins import TelemetryMixin, ResponseMixin
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


class AnalyticsView(TelemetryMixin, ResponseMixin, APIView):
    """
    Analytics overview and per-domain analytics.

    GET /api/v1/telemetry/analytics/overview/          → system overview
    GET /api/v1/telemetry/analytics/metrics/           → metric analytics
    GET /api/v1/telemetry/analytics/logs/              → log analytics
    GET /api/v1/telemetry/analytics/traces/            → trace analytics
    GET /api/v1/telemetry/analytics/alerts/            → alert analytics
    GET /api/v1/telemetry/analytics/health/            → health analytics
    GET /api/v1/telemetry/analytics/service/           → per-service analytics
    GET /api/v1/telemetry/analytics/trend/             → metric trend data
    """

    permission_classes = [TelemetryBasePermission]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = AnalyticsService()

    def _parse_hours(self, request, default=24):
        """DRY: parse ?hours= query param used by every action."""
        try:
            return int(request.query_params.get('hours', default))
        except ValueError:
            return None

    def get(self, request, action=None):
        """
        Route GET requests to the correct analytics action.
        Uses ?action= or URL segment to dispatch.
        """
        action = action or request.query_params.get('action', 'overview')
        handler = {
            'overview': self._overview,
            'metrics':  self._metric_analytics,
            'logs':     self._log_analytics,
            'traces':   self._trace_analytics,
            'alerts':   self._alert_analytics,
            'health':   self._health_analytics,
            'service':  self._service_analytics,
            'trend':    self._trend_data,
        }.get(action)

        if handler is None:
            return self.error_response(
                f"Unknown action '{action}'. Valid: overview, metrics, logs, "
                f"traces, alerts, health, service, trend.",
                status_code=400,
            )
        return handler(request)

    def _overview(self, request):
        """GET /analytics/overview/?hours=24 — full system summary."""
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")

        from django.utils import timezone
        from datetime import timedelta
        from ..models.metric_event import MetricEvent
        from ..models.log_entry import LogEntry
        from ..models.trace_span import TraceSpan
        from ..models.alert import Alert
        from ..models.health_status import HealthStatus
        from django.db.models import Avg

        since = timezone.now() - timedelta(hours=hours)

        data = {
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

    def _metric_analytics(self, request):
        """GET /analytics/metrics/?name=<name>&hours=24"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        data = self._service.get_metric_analytics(name, hours=hours)
        return Response(MetricAnalyticsSerializer(data).data)

    def _log_analytics(self, request):
        """GET /analytics/logs/?hours=24"""
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        data = self._service.get_log_analytics(hours=hours)
        return Response(LogAnalyticsSerializer(data).data)

    def _trace_analytics(self, request):
        """GET /analytics/traces/?hours=24"""
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        data = self._service.get_trace_analytics(hours=hours)
        return Response(TraceAnalyticsSerializer(data).data)

    def _alert_analytics(self, request):
        """GET /analytics/alerts/?hours=24"""
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        data = self._service.get_alert_analytics(hours=hours)
        return Response(AlertAnalyticsSerializer(data).data)

    def _health_analytics(self, request):
        """GET /analytics/health/"""
        data = self._service.get_health_analytics()
        return Response(HealthAnalyticsSerializer(data).data)

    def _service_analytics(self, request):
        """GET /analytics/service/?service=<name>&hours=24"""
        service = request.query_params.get('service')
        if not service:
            return self.error_response("'service' query parameter is required.")
        hours = self._parse_hours(request)
        if hours is None:
            return self.error_response("'hours' must be a valid integer.")
        data = self._service.get_service_analytics(service, hours=hours)
        return Response(ServiceAnalyticsSerializer(data).data)

    def _trend_data(self, request):
        """GET /analytics/trend/?name=<name>&interval=hour|day&periods=24"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        interval = request.query_params.get('interval', 'hour')
        try:
            periods = int(request.query_params.get('periods', 24))
        except ValueError:
            return self.error_response("'periods' must be a valid integer.")
        data = self._service.get_trend_data(name, interval=interval, periods=periods)
        return Response({'name': name, 'interval': interval, 'data': data})
