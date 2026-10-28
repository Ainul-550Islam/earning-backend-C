"""
Dashboard ViewSet — DRY wiring: filters.py + permissions.py + mixins.py + logic.py
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..filters import DashboardWidgetFilter
from ..mixins import TelemetryMixin, ResponseMixin
from ..permissions import CanManageDashboards
from ..logic import DashboardLogic
from ..services.dashboard_service import DashboardService
from ..models.dashboard_widget import DashboardWidget
from ..serializers.dashboard_serializer import (
    DashboardWidgetSerializer,
    DashboardWidgetCreateSerializer,
    DashboardWidgetUpdateSerializer,
)


class DashboardViewSet(TelemetryMixin, ResponseMixin, viewsets.ModelViewSet):
    """
    DRF ViewSet for DashboardWidget.

    GET    /api/v1/telemetry/dashboards/                → list (filtered)
    POST   /api/v1/telemetry/dashboards/                → create
    GET    /api/v1/telemetry/dashboards/<pk>/           → retrieve
    PUT    /api/v1/telemetry/dashboards/<pk>/           → full update
    PATCH  /api/v1/telemetry/dashboards/<pk>/           → partial update
    DELETE /api/v1/telemetry/dashboards/<pk>/           → destroy
    GET    /api/v1/telemetry/dashboards/<pk>/data/      → live widget data
    POST   /api/v1/telemetry/dashboards/<pk>/activate/  → activate
    POST   /api/v1/telemetry/dashboards/<pk>/deactivate/ → deactivate
    POST   /api/v1/telemetry/dashboards/batch/          → batch create
    GET    /api/v1/telemetry/dashboards/by-dashboard/   → widgets for a dashboard
    """

    queryset           = DashboardWidget.objects.all().order_by('position_y', 'position_x')
    serializer_class   = DashboardWidgetSerializer
    permission_classes = [CanManageDashboards]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = DashboardWidgetFilter
    ordering_fields = ['position_y', 'position_x', 'name', 'widget_type']
    ordering        = ['position_y', 'position_x']
    search_fields   = ['name', 'widget_type', 'data_source']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logic   = DashboardLogic()
        self._service = DashboardService()

    def get_serializer_class(self):
        if self.action == 'create':
            return DashboardWidgetCreateSerializer
        if self.action == 'partial_update':
            return DashboardWidgetUpdateSerializer
        return DashboardWidgetSerializer

    def create(self, request, *args, **kwargs):
        serializer = DashboardWidgetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        widget = self._logic.create_widget(serializer.validated_data)
        return Response(DashboardWidgetSerializer(widget).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._logic.delete_widget(instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='data')
    def data(self, request, pk=None):
        """GET /dashboards/<pk>/data/?hours=24 — live data for this widget."""
        widget = self._logic.get_widget(pk)
        if widget is None:
            return self.error_response(f'Widget {pk} not found.', status_code=404)
        try:
            hours = int(request.query_params.get('hours', 24))
        except ValueError:
            return self.error_response("'hours' must be a valid integer.")
        return Response(self._service.get_widget_data(widget, hours=hours))

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """POST /dashboards/<pk>/activate/"""
        if not self._logic.update_widget(pk, {'is_active': True}):
            return self.error_response(f'Widget {pk} not found.', status_code=404)
        return Response(DashboardWidgetSerializer(self._logic.get_widget(pk)).data)

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """POST /dashboards/<pk>/deactivate/"""
        if not self._logic.update_widget(pk, {'is_active': False}):
            return self.error_response(f'Widget {pk} not found.', status_code=404)
        return Response(DashboardWidgetSerializer(self._logic.get_widget(pk)).data)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """POST /dashboards/batch/ — body: {"widgets": [...]}"""
        widgets_data = request.data.get('widgets', [])
        if not widgets_data:
            return self.error_response("'widgets' list cannot be empty.")

        created, errors = [], []
        for i, item in enumerate(widgets_data):
            serializer = DashboardWidgetCreateSerializer(data=item)
            if serializer.is_valid():
                created.append(self._logic.create_widget(serializer.validated_data))
            else:
                errors.append({'index': i, 'errors': serializer.errors})

        if errors:
            return Response({
                'created': DashboardWidgetSerializer(created, many=True).data,
                'errors':  errors,
            }, status=status.HTTP_207_MULTI_STATUS)

        return Response(
            DashboardWidgetSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='by-dashboard')
    def by_dashboard(self, request):
        """GET /dashboards/by-dashboard/?dashboard_id=<id>"""
        dashboard_id = request.query_params.get('dashboard_id')
        if not dashboard_id:
            return self.error_response("'dashboard_id' is required.")
        try:
            dashboard_id = int(dashboard_id)
        except ValueError:
            return self.error_response("'dashboard_id' must be an integer.")
        return Response(
            DashboardWidgetSerializer(
                self._logic.get_widgets(dashboard_id=dashboard_id), many=True
            ).data
        )
