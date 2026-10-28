"""
User Dashboard viewset for Real-time Dashboard Backend.

WIRED (v1.2.0):
  - perform_create → DashboardService.create_dashboard()
    Previously the viewset called serializer.save(user_id=...) directly,
    bypassing DashboardService entirely.

  - widget_ids() action → DashboardEngineService.get_dashboard_widget_ids()
    GET /api/dashboards/<id>/widget_ids/
    get_dashboard_widget_ids() existed in the service but had no HTTP
    surface — callers had to trigger a full render to discover widget IDs.

  - stats() action — new: exposes business metrics per dashboard
    GET /api/dashboards/<id>/stats/
    Combines: widget count, active metric count, render feasibility.

  DRY: by_user() now uses @require_query_param to eliminate the
  manual missing-param check (previously copy-pasted from other viewsets).

SECURITY:
  - get_queryset() scopes to request.user.pk (non-staff).
  - IsDashboardOwner enforced via check_object_permissions().
  - require_dashboard calls check_object_permissions (IDOR fix).
  - perform_create always sets user_id from request.user.pk.
"""
from typing import Optional, Type

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiParameter
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from django_filters.rest_framework import DjangoFilterBackend

from ..models.user_dashboard import UserDashboard
from ..serializers.user_dashboard_serializer import (
    UserDashboardSerializer,
    UserDashboardListSerializer,
)
from ..services.dashboard_engine_service import DashboardEngineService
from ..services.dashboard_service import DashboardService
from ..services.real_time_metric_service import RealTimeMetricService
from ..exceptions import DashboardEngineError
from ..pagination import StandardResultsSetPagination
from ..permissions import IsDashboardOwner
from ..filters import UserDashboardFilter
from ..decorators import require_dashboard, require_query_param
from ..throttling import DashboardRenderThrottle


@extend_schema_view(
    list=extend_schema(tags=['dashboards'], summary='List your dashboards'),
    retrieve=extend_schema(tags=['dashboards'], summary='Get a dashboard'),
    create=extend_schema(tags=['dashboards'], summary='Create a dashboard'),
    update=extend_schema(tags=['dashboards'], summary='Replace a dashboard'),
    partial_update=extend_schema(tags=['dashboards'], summary='Partially update a dashboard'),
    destroy=extend_schema(tags=['dashboards'], summary='Delete a dashboard'),
)
class UserDashboardViewSet(viewsets.ModelViewSet):
    """ViewSet for UserDashboard model."""

    serializer_class = UserDashboardSerializer
    permission_classes = [IsAuthenticated, IsDashboardOwner]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = UserDashboardFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'status', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self) -> QuerySet:
        """Scope to requesting user's dashboards. Staff sees all."""
        user = self.request.user
        if user.is_staff:
            return UserDashboard.objects.all().select_related('layout')
        return UserDashboard.objects.filter(
            user_id=str(user.pk)
        ).select_related('layout')

    def get_serializer_class(self) -> Type[BaseSerializer]:
        if self.action == 'list':
            return UserDashboardListSerializer
        return UserDashboardSerializer

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        WIRED (v1.5.0): delegates to DashboardService.create_dashboard().
        user_id is always set from request.user.pk — client-supplied
        values are silently overridden (it's also read_only=True on the
        serializer, so there is no single point of failure for the
        ownership invariant). DashboardService.get_user_dashboards()
        remains the single owner of user-scoped dashboard queries (used
        in middleware etc.).
        """
        data = {**serializer.validated_data, 'user_id': str(self.request.user.pk)}
        dashboard = DashboardService().create_dashboard(data)
        serializer.instance = dashboard

    # ── Ownership-guarded actions ─────────────────────────────────────────────

    @extend_schema(tags=['dashboards'], summary='Activate a dashboard', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @require_dashboard
    @action(detail=True, methods=['post'])
    def activate(self, request: Request, pk: Optional[str] = None) -> Response:
        """POST /api/dashboards/<id>/activate/"""
        dashboard = request.dashboard  # type: ignore[attr-defined]  # injected by @require_dashboard
        dashboard.status = UserDashboard.DashboardStatus.ACTIVE
        dashboard.save()
        return Response({'success': True, 'message': f'Dashboard {dashboard.name} activated successfully'})

    @extend_schema(tags=['dashboards'], summary='Deactivate a dashboard', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @require_dashboard
    @action(detail=True, methods=['post'])
    def deactivate(self, request: Request, pk: Optional[str] = None) -> Response:
        """POST /api/dashboards/<id>/deactivate/"""
        dashboard = request.dashboard  # type: ignore[attr-defined]  # injected by @require_dashboard
        dashboard.status = UserDashboard.DashboardStatus.INACTIVE
        dashboard.save()
        return Response({'success': True, 'message': f'Dashboard {dashboard.name} deactivated successfully'})

    @extend_schema(
        tags=['dashboards'],
        summary='Render a dashboard',
        description='Full render: resolves the layout, every widget, and their live metric data in one call.',
        responses={
            200: inline_serializer(
                name='DashboardRenderResponse',
                fields={'success': serializers.BooleanField(), 'dashboard': serializers.DictField()},
            ),
            404: inline_serializer(
                name='DashboardRenderNotFound',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
        },
    )
    @action(detail=True, methods=['get'], throttle_classes=[DashboardRenderThrottle])
    def render(self, request: Request, pk: Optional[str] = None) -> Response:
        """GET /api/dashboards/<id>/render/ — full render via ownership-checked get_object()."""
        dashboard = self.get_object()
        try:
            data = DashboardEngineService().render_dashboard(dashboard.pk)
        except DashboardEngineError as exc:
            return Response({'success': False, 'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True, 'dashboard': data})

    @extend_schema(
        tags=['dashboards'],
        summary='List widget IDs on a dashboard',
        responses={
            200: inline_serializer(
                name='DashboardWidgetIdsResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'widget_ids': serializers.ListField(child=serializers.IntegerField()),
                },
            ),
        },
    )
    @action(detail=True, methods=['get'])
    def widget_ids(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        GET /api/dashboards/<id>/widget_ids/

        WIRED (v1.2.0): DashboardEngineService.get_dashboard_widget_ids()
        was defined and bug-fixed (JSONField crash) but had no HTTP endpoint.
        Callers previously had to trigger a full render just to get the list.

        Returns: {"success": true, "widget_ids": [1, 3, 7]}
        """
        dashboard = self.get_object()
        try:
            widget_ids = DashboardEngineService().get_dashboard_widget_ids(dashboard.pk)
        except DashboardEngineError as exc:
            return Response({'success': False, 'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True, 'widget_ids': widget_ids})

    @extend_schema(
        tags=['dashboards'],
        summary='Get dashboard summary stats',
        description='Widget count, active metric count, and widget IDs — without triggering a full render.',
        responses={
            200: inline_serializer(
                name='DashboardStatsResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'dashboard_id': serializers.IntegerField(),
                    'widget_count': serializers.IntegerField(),
                    'active_metric_count': serializers.IntegerField(),
                    'widget_ids': serializers.ListField(child=serializers.IntegerField()),
                },
            ),
        },
    )
    @action(detail=True, methods=['get'])
    def stats(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        GET /api/dashboards/<id>/stats/

        NEW endpoint (v1.2.0): business-level summary for a dashboard.
        Combines data from DashboardEngineService and RealTimeMetricService
        without triggering a full render.

        Returns:
            {
                "success": true,
                "dashboard_id": 1,
                "widget_count": 4,
                "active_metric_count": 12,
                "widget_ids": [1, 3, 7, 9]
            }
        """
        dashboard = self.get_object()
        try:
            widget_ids = DashboardEngineService().get_dashboard_widget_ids(dashboard.pk)
        except DashboardEngineError:
            widget_ids = []

        active_metric_count = sum(
            RealTimeMetricService().get_metrics_for_widget(wid).__len__()
            for wid in widget_ids
        )

        return Response({
            'success': True,
            'dashboard_id': dashboard.pk,
            'widget_count': len(widget_ids),
            'active_metric_count': active_metric_count,
            'widget_ids': widget_ids,
        })

    # ── Staff-only actions ────────────────────────────────────────────────────

    @extend_schema(
        tags=['dashboards'],
        summary='List dashboards for a given user (staff only)',
        parameters=[
            OpenApiParameter(
                name='user_id', type=str, location=OpenApiParameter.QUERY,
                required=True, description='Look up dashboards owned by this user ID. Requires is_staff.',
            ),
        ],
        responses={
            200: UserDashboardListSerializer(many=True),
            403: inline_serializer(
                name='DashboardByUserForbidden',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
        },
    )
    @require_query_param('user_id')
    @action(detail=False, methods=['get'])
    def by_user(self, request: Request) -> Response:
        """
        GET /api/dashboards/by_user/?user_id=X  (staff only)

        DRY: @require_query_param replaces the manual missing-param check.
        """
        if not request.user.is_staff:
            return Response(
                {'success': False, 'error': 'Only staff users can query by arbitrary user_id.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        user_id = request.query_params['user_id']
        dashboards = UserDashboard.objects.select_related('layout').filter(user_id=user_id)
        serializer = self.get_serializer(dashboards, many=True)
        return Response(serializer.data)
