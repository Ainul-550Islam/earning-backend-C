"""
Log ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import LogEntryFilter
from ..mixins import TelemetryMixin, ResponseMixin, CacheMixin
from ..permissions import TelemetryBasePermission
from ..logic import LogLogic
from ..services.analytics_service import AnalyticsService
from ..models.log_entry import LogEntry
from ..serializers.log_serializer import (
    LogEntrySerializer,
    LogEntryCreateSerializer,
    LogBatchCreateSerializer,
)


class LogViewSet(TelemetryMixin, ResponseMixin, CacheMixin, viewsets.ModelViewSet):
    """
    DRF ViewSet for LogEntry.

    GET    /api/v1/telemetry/logs/              → list (filtered)
    POST   /api/v1/telemetry/logs/              → create
    GET    /api/v1/telemetry/logs/<pk>/         → retrieve
    DELETE /api/v1/telemetry/logs/<pk>/         → destroy
    POST   /api/v1/telemetry/logs/batch/        → batch create
    GET    /api/v1/telemetry/logs/analytics/    → level distribution
    GET    /api/v1/telemetry/logs/errors/       → error + critical only
    GET    /api/v1/telemetry/logs/by-service/   → per-service breakdown
    """

    queryset           = LogEntry.objects.all().order_by('-timestamp')
    serializer_class   = LogEntrySerializer
    permission_classes = [TelemetryBasePermission]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogEntryFilter
    ordering_fields = ['timestamp', 'level', 'service']
    ordering        = ['-timestamp']
    search_fields   = ['message', 'logger_name', 'source', 'service']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic     = LogLogic()
        self._analytics = AnalyticsService()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LogEntryCreateSerializer
        return LogEntrySerializer

    def create(self, request, *args, **kwargs):
        serializer = LogEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = self._logic.record_log(serializer.validated_data)
        return Response(LogEntrySerializer(log).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """POST /logs/batch/ — create multiple log entries at once."""
        serializer = LogBatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        logs = self._logic.batch_record(serializer.validated_data['logs'])
        return Response(
            LogEntrySerializer(logs, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics_view(self, request):
        """GET /logs/analytics/?hours=24 — level distribution + error rate."""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._analytics.get_log_analytics(hours=hours))

    @action(detail=False, methods=['get'], url_path='errors')
    def errors(self, request):
        """GET /logs/errors/?service=<name>&limit=<n> — error + critical only."""
        qs = LogEntry.objects.filter(level__in=['error', 'critical'])
        service = request.query_params.get('service')
        if service:
            qs = qs.filter(service=service)
        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return self.error_response("'limit' must be a valid integer.")
        return Response(LogEntrySerializer(qs.order_by('-timestamp')[:limit], many=True).data)

    @action(detail=False, methods=['get'], url_path='by-service')
    def by_service(self, request):
        """GET /logs/by-service/?service=<name>&hours=24 — per-service analytics."""
        service = request.query_params.get('service')
        if not service:
            return self.error_response("'service' query parameter is required.")
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._analytics.get_service_analytics(service, hours=hours))
