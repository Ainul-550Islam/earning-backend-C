"""
Health ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg

from ..filters import HealthStatusFilter
from ..mixins import TelemetryMixin, ResponseMixin
from ..permissions import TelemetryBasePermission
from ..logic import HealthLogic
from ..services.analytics_service import AnalyticsService
from ..models.health_status import HealthStatus
from ..serializers.health_serializer import (
    HealthStatusSerializer,
    HealthStatusCreateSerializer,
)


class HealthViewSet(TelemetryMixin, ResponseMixin, viewsets.ModelViewSet):
    """
    DRF ViewSet for HealthStatus.

    GET    /api/v1/telemetry/health/              → list (filtered)
    POST   /api/v1/telemetry/health/              → create
    GET    /api/v1/telemetry/health/<pk>/         → retrieve
    PUT    /api/v1/telemetry/health/<pk>/         → update
    DELETE /api/v1/telemetry/health/<pk>/         → destroy
    POST   /api/v1/telemetry/health/upsert/       → create-or-update
    GET    /api/v1/telemetry/health/healthy/      → healthy services
    GET    /api/v1/telemetry/health/unhealthy/    → degraded + unhealthy
    GET    /api/v1/telemetry/health/analytics/    → analytics
    GET    /api/v1/telemetry/health/summary/      → quick summary
    """

    queryset           = HealthStatus.objects.all().order_by('-last_check')
    serializer_class   = HealthStatusSerializer
    permission_classes = [TelemetryBasePermission]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = HealthStatusFilter
    ordering_fields = ['last_check', 'health_score', 'service_name', 'status']
    ordering        = ['-last_check']
    search_fields   = ['service_name', 'component_name']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic     = HealthLogic()
        self._analytics = AnalyticsService()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update', 'upsert'):
            return HealthStatusCreateSerializer
        return HealthStatusSerializer

    def create(self, request, *args, **kwargs):
        serializer = HealthStatusCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        health = HealthStatus.objects.create(**serializer.validated_data)
        return Response(HealthStatusSerializer(health).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='upsert')
    def upsert(self, request):
        """POST /health/upsert/ — idempotent create-or-update per (service, component, env)."""
        serializer = HealthStatusCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        obj, created = self._logic.upsert(serializer.validated_data)
        http_status  = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(HealthStatusSerializer(obj).data, status=http_status)

    @action(detail=False, methods=['get'], url_path='healthy')
    def healthy(self, request):
        """GET /health/healthy/?environment=<env>"""
        qs = HealthStatus.objects.filter(status='healthy')
        env = request.query_params.get('environment')
        if env:
            qs = qs.filter(environment=env)
        return Response(HealthStatusSerializer(qs.order_by('-last_check'), many=True).data)

    @action(detail=False, methods=['get'], url_path='unhealthy')
    def unhealthy(self, request):
        """GET /health/unhealthy/?environment=<env>"""
        qs = HealthStatus.objects.filter(status__in=['degraded', 'unhealthy'])
        env = request.query_params.get('environment')
        if env:
            qs = qs.filter(environment=env)
        return Response(HealthStatusSerializer(qs.order_by('health_score'), many=True).data)

    @action(detail=False, methods=['get'], url_path='analytics')
    def analytics_view(self, request):
        """GET /health/analytics/"""
        return Response(self._analytics.get_health_analytics())

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """GET /health/summary/ — counts by status + average score."""
        total         = HealthStatus.objects.values('service_name').distinct().count()
        healthy_count = HealthStatus.objects.filter(status='healthy').count()
        degraded      = HealthStatus.objects.filter(status='degraded').count()
        unhealthy     = HealthStatus.objects.filter(status='unhealthy').count()
        unknown       = HealthStatus.objects.filter(status='unknown').count()
        avg_score     = HealthStatus.objects.aggregate(avg=Avg('health_score'))['avg'] or 0.0

        return Response({
            'total_services':   total,
            'healthy':          healthy_count,
            'degraded':         degraded,
            'unhealthy':        unhealthy,
            'unknown':          unknown,
            'avg_health_score': round(avg_score, 2),
            'health_percentage': round(
                (healthy_count / total * 100) if total > 0 else 0.0, 2
            ),
        })
