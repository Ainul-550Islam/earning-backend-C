"""
Alert ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import AlertFilter
from ..mixins import TelemetryMixin, ResponseMixin
from ..permissions import CanManageAlerts
from ..logic import AlertLogic
from ..services.analytics_service import AnalyticsService
from ..models.alert import Alert
from ..serializers.alert_serializer import (
    AlertSerializer,
    AlertCreateSerializer,
    AlertAcknowledgeSerializer,
    AlertStatisticsSerializer,
    AlertBatchCreateSerializer,
)


class AlertViewSet(TelemetryMixin, ResponseMixin, viewsets.ModelViewSet):
    """
    DRF ViewSet for Alert.

    GET    /api/v1/telemetry/alerts/                    → list (filtered)
    POST   /api/v1/telemetry/alerts/                    → create
    GET    /api/v1/telemetry/alerts/<pk>/               → retrieve
    PUT    /api/v1/telemetry/alerts/<pk>/               → update
    DELETE /api/v1/telemetry/alerts/<pk>/               → destroy
    POST   /api/v1/telemetry/alerts/<pk>/acknowledge/   → acknowledge
    POST   /api/v1/telemetry/alerts/<pk>/resolve/       → resolve
    POST   /api/v1/telemetry/alerts/batch/              → batch create
    GET    /api/v1/telemetry/alerts/statistics/         → stats
    GET    /api/v1/telemetry/alerts/analytics/          → analytics
    GET    /api/v1/telemetry/alerts/open/               → open only
    GET    /api/v1/telemetry/alerts/critical/           → critical only
    """

    queryset           = Alert.objects.all().order_by('-triggered_at')
    serializer_class   = AlertSerializer
    permission_classes = [CanManageAlerts]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = AlertFilter
    ordering_fields = ['triggered_at', 'severity', 'status', 'service']
    ordering        = ['-triggered_at']
    search_fields   = ['name', 'message', 'source', 'service']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic     = AlertLogic()
        self._analytics = AnalyticsService()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AlertCreateSerializer
        if self.action == 'acknowledge':
            return AlertAcknowledgeSerializer
        return AlertSerializer

    def create(self, request, *args, **kwargs):
        serializer = AlertCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert = self._logic.create_alert(serializer.validated_data)
        return Response(AlertSerializer(alert).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        """POST /alerts/<pk>/acknowledge/ — body: {"user": "ops-user"}"""
        serializer = AlertAcknowledgeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        if not self._logic.acknowledge(pk, serializer.validated_data['user']):
            return self.error_response(f'Alert {pk} not found.', status_code=404)
        return Response(AlertSerializer(Alert.objects.get(pk=pk)).data)

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        """POST /alerts/<pk>/resolve/"""
        if not self._logic.resolve(pk):
            return self.error_response(f'Alert {pk} not found.', status_code=404)
        return Response(AlertSerializer(Alert.objects.get(pk=pk)).data)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """POST /alerts/batch/ — body: {"alerts": [...]}"""
        serializer = AlertBatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        alerts = self._logic.batch_create(serializer.validated_data['alerts'])
        return Response(
            AlertSerializer(alerts, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """GET /alerts/statistics/?hours=24"""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(AlertStatisticsSerializer(self._logic.get_statistics(hours=hours)).data)

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics_view(self, request):
        """GET /alerts/analytics/?hours=24"""
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._analytics.get_alert_analytics(hours=hours))

    @action(detail=False, methods=['get'], url_path='open')
    def open_alerts(self, request):
        """GET /alerts/open/?service=<name>"""
        service = request.query_params.get('service')
        return Response(AlertSerializer(self._logic.get_open(service=service), many=True).data)

    @action(detail=False, methods=['get'], url_path='critical')
    def critical_alerts(self, request):
        """GET /alerts/critical/?service=<name>"""
        service = request.query_params.get('service')
        return Response(AlertSerializer(self._logic.get_critical(service=service), many=True).data)
