"""
Metric ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import MetricEventFilter
from ..mixins import MetricMixin, ResponseMixin, CacheMixin
from ..permissions import TelemetryBasePermission
from ..logic import MetricLogic
from ..services.analytics_service import AnalyticsService
from ..models.metric_event import MetricEvent
from ..serializers.metric_serializer import (
    MetricEventSerializer,
    MetricEventCreateSerializer,
    MetricStatisticsSerializer,
    MetricBatchCreateSerializer,
)


class MetricViewSet(MetricMixin, ResponseMixin, CacheMixin,
                    viewsets.ModelViewSet):
    # NOTE: MetricMixin already subclasses TelemetryMixin (see mixins.py) — it is
    # not listed separately here. Doing so previously produced:
    #   TypeError: Cannot create a consistent method resolution order (MRO)
    # because a subclass (MetricMixin) and its own parent (TelemetryMixin)
    # were both listed as direct bases with the parent ordered first.
    """
    DRF ViewSet for MetricEvent.

    GET    /api/v1/telemetry/metrics/                → list (filtered)
    POST   /api/v1/telemetry/metrics/                → create
    GET    /api/v1/telemetry/metrics/<pk>/           → retrieve
    PUT    /api/v1/telemetry/metrics/<pk>/           → update
    DELETE /api/v1/telemetry/metrics/<pk>/           → destroy
    POST   /api/v1/telemetry/metrics/batch/          → batch create
    GET    /api/v1/telemetry/metrics/statistics/     → aggregated stats
    GET    /api/v1/telemetry/metrics/analytics/      → detailed analytics
    GET    /api/v1/telemetry/metrics/aggregate/      → time-series
    """

    queryset           = MetricEvent.objects.all().order_by('-timestamp')
    serializer_class   = MetricEventSerializer
    permission_classes = [TelemetryBasePermission]

    # DRY: filtering delegated to filters.py — no get_queryset() manual logic
    filter_backends  = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class  = MetricEventFilter
    ordering_fields  = ['timestamp', 'name', 'value', 'metric_type']
    ordering         = ['-timestamp']
    search_fields    = ['name', 'source', 'service']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic     = MetricLogic()
        self._analytics = AnalyticsService()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MetricEventCreateSerializer
        return MetricEventSerializer

    def create(self, request, *args, **kwargs):
        serializer = MetricEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        metric = self._logic.record_metric(serializer.validated_data)
        return Response(MetricEventSerializer(metric).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """POST /metrics/batch/ — create multiple metrics at once."""
        serializer = MetricBatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        metrics = self._logic.batch_record(serializer.validated_data['metrics'])
        return Response(
            MetricEventSerializer(metrics, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """GET /metrics/statistics/?name=<name>&hours=<n>"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")

        stats      = self._logic.get_statistics(name, hours=hours)
        serializer = MetricStatisticsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics_view(self, request):
        """GET /metrics/analytics/?name=<name>&hours=<n>"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._analytics.get_metric_analytics(name, hours=hours))

    @action(detail=False, methods=['get'], url_path='aggregate')
    def aggregate(self, request):
        """GET /metrics/aggregate/?name=<name>&interval=hour|day&periods=24"""
        name = request.query_params.get('name')
        if not name:
            return self.error_response("'name' query parameter is required.")
        interval = request.query_params.get('interval', 'hour')
        try:
            periods = int(request.query_params.get('periods', 24))
        except ValueError:
            return self.error_response("'periods' must be a valid integer.")

        from django.utils import timezone
        from datetime import timedelta
        delta = timedelta(hours=1) if interval == 'hour' else timedelta(days=1)
        since = timezone.now() - (delta * periods)
        return Response(self._logic.aggregate_by_time(name, interval=interval, since=since))
