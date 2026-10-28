"""
Trace ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import TraceSpanFilter
from ..mixins import TelemetryMixin, ResponseMixin
from ..permissions import TelemetryBasePermission
from ..logic import TraceLogic
from ..services.analytics_service import AnalyticsService
from ..models.trace_span import TraceSpan
from ..serializers.trace_serializer import (
    TraceSpanSerializer,
    TraceSpanCreateSerializer,
    TraceSpanFinishSerializer,
    TraceBatchCreateSerializer,
)


class TraceViewSet(TelemetryMixin, ResponseMixin, viewsets.ModelViewSet):
    """
    DRF ViewSet for TraceSpan.

    GET    /api/v1/telemetry/traces/              → list (filtered)
    POST   /api/v1/telemetry/traces/              → start span
    GET    /api/v1/telemetry/traces/<pk>/         → retrieve
    DELETE /api/v1/telemetry/traces/<pk>/         → destroy
    POST   /api/v1/telemetry/traces/<pk>/finish/  → finish span
    POST   /api/v1/telemetry/traces/batch/        → batch start
    GET    /api/v1/telemetry/traces/tree/         → nested tree
    GET    /api/v1/telemetry/traces/slow/         → slow spans
    GET    /api/v1/telemetry/traces/errors/       → error spans
    GET    /api/v1/telemetry/traces/statistics/   → aggregated stats
    GET    /api/v1/telemetry/traces/analytics/    → detailed analytics
    """

    queryset           = TraceSpan.objects.all().order_by('-start_time')
    serializer_class   = TraceSpanSerializer
    permission_classes = [TelemetryBasePermission]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = TraceSpanFilter
    ordering_fields = ['start_time', 'duration_ms', 'service', 'status']
    ordering        = ['-start_time']
    search_fields   = ['operation_name', 'trace_id', 'service']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic     = TraceLogic()
        self._analytics = AnalyticsService()

    def get_serializer_class(self):
        if self.action == 'create':
            return TraceSpanCreateSerializer
        return TraceSpanSerializer

    def create(self, request, *args, **kwargs):
        serializer = TraceSpanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        span = self._logic.start_span(serializer.validated_data)
        return Response(TraceSpanSerializer(span).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='finish')
    def finish(self, request, pk=None):
        """POST /traces/<pk>/finish/ — close the span with status."""
        try:
            span = TraceSpan.objects.get(pk=pk)
        except TraceSpan.DoesNotExist:
            return self.error_response(f'Span {pk} not found.', status_code=404)

        serializer = TraceSpanFinishSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self._logic.finish_span(span.span_id, serializer.validated_data)
        span.refresh_from_db()
        return Response(TraceSpanSerializer(span).data)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """POST /traces/batch/ — start multiple spans at once."""
        serializer = TraceBatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        spans = [self._logic.start_span(s) for s in serializer.validated_data['spans']]
        return Response(
            TraceSpanSerializer(spans, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        """GET /traces/tree/?trace_id=<id> — nested span tree."""
        trace_id = request.query_params.get('trace_id')
        if not trace_id:
            return self.error_response("'trace_id' is required.")
        tree = self._logic.get_trace_tree(trace_id)
        if tree.get('total_spans', 0) == 0:
            return self.error_response(f'No spans for trace_id "{trace_id}".', status_code=404)
        return Response(tree)

    @action(detail=False, methods=['get'], url_path='slow')
    def slow(self, request):
        """GET /traces/slow/?threshold_ms=5000&hours=24 — slow spans."""
        try:
            threshold_ms = float(request.query_params.get('threshold_ms', 5000))
            hours        = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'threshold_ms' and 'hours' must be valid numbers.")
        spans = self._logic.get_slow_traces(threshold_ms=threshold_ms, hours=hours)
        return Response(TraceSpanSerializer(spans, many=True).data)

    @action(detail=False, methods=['get'], url_path='errors')
    def errors(self, request):
        """GET /traces/errors/?hours=24 — error-status spans."""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(
            TraceSpanSerializer(self._logic.get_error_traces(hours=hours), many=True).data
        )

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """GET /traces/statistics/?hours=24 — aggregate stats."""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._logic.get_statistics(hours=hours))

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics_view(self, request):
        """GET /traces/analytics/?hours=24 — detailed analytics."""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._analytics.get_trace_analytics(hours=hours))
