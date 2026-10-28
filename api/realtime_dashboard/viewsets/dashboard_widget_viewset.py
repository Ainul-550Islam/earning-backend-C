"""
Dashboard Widget viewset for Real-time Dashboard Backend.

WIRED (v1.5.0 — 360-degree audit corrected this. The v1.2.0 claim below
was only half true: perform_create/update/destroy called WidgetService
for the cache primitives (_set_cached/_invalidate) but still called
serializer.save() directly for the actual write, leaving
create_widget/update_widget/delete_widget as dead code despite their own
docstrings also claiming WIRED. Fixed by tracing real call sites rather
than trusting the comments):
  - perform_create / perform_update / perform_destroy now delegate to
    WidgetService.create_widget/update_widget/delete_widget — the single
    owner of both the write and the cache priming/invalidation for every
    mutation.

  - data()    action → DashboardEngineService.get_widget_data()
    GET /api/widgets/<id>/data/
    Previously get_widget_data() existed in the service but had no
    HTTP endpoint — it was only callable internally by render_dashboard().

  - metrics() action → RealTimeMetricService.get_metrics_for_widget()
    GET /api/widgets/<id>/metrics/
    Previously get_metrics_for_widget() existed in the service but had
    no endpoint — impossible to call from a frontend without a full
    dashboard render.

  - by_type() action → WidgetService.get_widgets_by_type()
    GET /api/widgets/by_type/?widget_type=chart
    DRY: @require_query_param replaces the manual missing-param check.
"""
from typing import Optional, Type

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from django_filters.rest_framework import DjangoFilterBackend

from ..models.dashboard_widget import DashboardWidget
from ..serializers.dashboard_widget_serializer import (
    DashboardWidgetSerializer,
    DashboardWidgetListSerializer,
)
from ..serializers.real_time_metric_serializer import RealTimeMetricSerializer
from ..pagination import StandardResultsSetPagination
from ..filters import DashboardWidgetFilter
from ..decorators import require_widget, require_query_param
from ..services.widget_service import WidgetService
from ..services.real_time_metric_service import RealTimeMetricService
from ..services.dashboard_engine_service import DashboardEngineService
from ..exceptions import DashboardEngineError


@extend_schema_view(
    list=extend_schema(tags=['widgets'], summary='List dashboard widgets'),
    retrieve=extend_schema(tags=['widgets'], summary='Get a dashboard widget'),
    create=extend_schema(tags=['widgets'], summary='Create a dashboard widget'),
    update=extend_schema(tags=['widgets'], summary='Replace a dashboard widget'),
    partial_update=extend_schema(tags=['widgets'], summary='Partially update a dashboard widget'),
    destroy=extend_schema(tags=['widgets'], summary='Delete a dashboard widget'),
)
class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """ViewSet for DashboardWidget model."""

    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DashboardWidgetFilter
    search_fields = ['name', 'description', 'created_by']
    ordering_fields = ['name', 'widget_type', 'status', 'created_at', 'refresh_interval']
    ordering = ['-created_at']

    def get_serializer_class(self) -> Type[BaseSerializer]:
        if self.action == 'list':
            return DashboardWidgetListSerializer
        return DashboardWidgetSerializer

    # ── Service-delegating lifecycle hooks ───────────────────────────────────

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        WIRED (v1.5.0): delegates to WidgetService.create_widget() — the
        single owner of "create a widget + prime its cache". Previously
        this only reached into WidgetService for the cache primitive and
        called serializer.save() directly, leaving create_widget() dead.
        """
        widget = WidgetService().create_widget(serializer.validated_data)
        serializer.instance = widget

    def perform_update(self, serializer: BaseSerializer) -> None:
        """
        WIRED (v1.5.0): delegates to WidgetService.update_widget(), passing
        serializer.instance so the service mutates the same object DRF
        will serialize into the response — no redundant re-fetch.
        """
        if serializer.instance is None:  # pragma: no cover - update serializers are always bound to an instance
            raise RuntimeError('serializer.instance is None on an update serializer — DRF contract violation')
        WidgetService().update_widget(serializer.instance, serializer.validated_data)

    def perform_destroy(self, instance: DashboardWidget) -> None:
        """WIRED (v1.5.0): delegates to WidgetService.delete_widget()."""
        WidgetService().delete_widget(instance)

    # ── Custom actions ────────────────────────────────────────────────────────

    @extend_schema(tags=['widgets'], summary='Activate a widget', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @require_widget
    @action(detail=True, methods=['post'])
    def activate(self, request: Request, pk: Optional[str] = None) -> Response:
        """Activate a widget."""
        widget = request.widget  # type: ignore[attr-defined]  # injected by @require_widget
        widget.status = 'active'
        widget.save()
        return Response({'success': True, 'message': f'Widget {widget.name} activated successfully'})

    @extend_schema(tags=['widgets'], summary='Deactivate a widget', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @require_widget
    @action(detail=True, methods=['post'])
    def deactivate(self, request: Request, pk: Optional[str] = None) -> Response:
        """Deactivate a widget."""
        widget = request.widget  # type: ignore[attr-defined]  # injected by @require_widget
        widget.status = 'inactive'
        widget.save()
        return Response({'success': True, 'message': f'Widget {widget.name} deactivated successfully'})

    @extend_schema(
        tags=['widgets'], summary='List active widgets',
        responses={200: DashboardWidgetListSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def active(self, request: Request) -> Response:
        """GET /api/widgets/active/ — list all active widgets."""
        widgets = self.queryset.active()
        serializer = self.get_serializer(widgets, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['widgets'],
        summary='Get widget data',
        description='Returns the widget config plus its live metric snapshots, without a full dashboard render.',
    )
    @action(detail=True, methods=['get'])
    def data(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        GET /api/widgets/<id>/data/

        WIRED (v1.2.0): DashboardEngineService.get_widget_data() was
        previously unreachable from outside the module. Now exposed so
        frontends can refresh a single widget's data without triggering
        a full dashboard render.

        Returns the widget config + its live metric snapshots.
        """
        widget = self.get_object()
        try:
            widget_data = DashboardEngineService().get_widget_data(widget.pk)
        except DashboardEngineError as exc:
            return Response(
                {'success': False, 'error': str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'success': True, 'data': widget_data})

    @extend_schema(
        tags=['widgets'],
        summary='List metrics linked to this widget',
        responses={200: {'type': 'object', 'properties': {
            'success': {'type': 'boolean'},
            'metrics': {'type': 'array', 'items': {'type': 'object'}},
        }}},
    )
    @action(detail=True, methods=['get'])
    def metrics(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        GET /api/widgets/<id>/metrics/

        WIRED (v1.2.0): RealTimeMetricService.get_metrics_for_widget()
        was previously unreachable from the API. Now exposed so frontends
        can fetch only the metrics linked to a specific widget.

        Metrics declare their widget via metadata['widget_id'].
        """
        widget = self.get_object()
        metric_list = RealTimeMetricService().get_metrics_for_widget(widget.pk)
        serializer = RealTimeMetricSerializer(metric_list, many=True)
        return Response({'success': True, 'metrics': serializer.data})

    @extend_schema(
        tags=['widgets'],
        summary='List widgets by type',
        parameters=[
            OpenApiParameter(
                name='widget_type', type=str, location=OpenApiParameter.QUERY,
                required=True, description="e.g. 'chart', 'gauge', 'table' — see WidgetType choices.",
            ),
        ],
        responses={200: DashboardWidgetListSerializer(many=True)},
    )
    @require_query_param('widget_type')
    @action(detail=False, methods=['get'])
    def by_type(self, request: Request) -> Response:
        """
        GET /api/widgets/by_type/?widget_type=chart

        WIRED (v1.2.0): WidgetService.get_widgets_by_type() was defined
        but had no HTTP endpoint.
        DRY: @require_query_param replaces the manual missing-param check.
        """
        widget_type = request.query_params['widget_type']
        widgets = WidgetService().get_widgets_by_type(widget_type)
        serializer = self.get_serializer(widgets, many=True)
        return Response(serializer.data)
