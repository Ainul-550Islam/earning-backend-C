"""
Dashboard Layout viewset for Real-time Dashboard Backend.

WIRED (v1.1.0): BurstUserThrottle was defined in throttling.py but never
applied to any viewset. DashboardLayout write operations (POST/PUT/PATCH/DELETE)
now use BurstUserThrottle in addition to the standard permission check.

Rationale: Layout changes invalidate cached dashboard renders for ALL users
who share that layout. Bursting 50 layout mutations in a second would cascade
into 50 × N cache invalidations where N is the subscriber count. The burst
throttle (20/min per staff user) prevents both accidental and malicious bulk
mutation storms.

DRY FIX (v1.5.0 — 360-degree audit): by_type() was the only one of 5
"filter by X" actions across the module still using a raw
`.filter(layout_type=...)` call and a manual missing-param check — every
sibling (WidgetConfigurationViewSet.by_widget, UserDashboardViewSet.by_user,
WebSocketConnectionViewSet.by_user, RealTimeMetricViewSet.by_type) had
already been converted to @require_query_param + the model's custom
manager method. Brought in line with those, and added by_creator() —
DashboardLayoutManager.by_creator() existed and DashboardLayout.created_by
has a dedicated DB index (dl_created_by_idx) but no endpoint ever queried
it.
"""
from typing import List

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from django_filters.rest_framework import DjangoFilterBackend

from ..models.dashboard_layout import DashboardLayout
from ..serializers.dashboard_layout_serializer import DashboardLayoutSerializer
from ..pagination import StandardResultsSetPagination
from ..permissions import IsAdminOrReadOnly
from ..throttling import BurstUserThrottle
from ..decorators import require_query_param


@extend_schema_view(
    list=extend_schema(tags=['layouts'], summary='List dashboard layouts'),
    retrieve=extend_schema(tags=['layouts'], summary='Get a dashboard layout'),
    create=extend_schema(tags=['layouts'], summary='Create a dashboard layout (staff only)'),
    update=extend_schema(tags=['layouts'], summary='Replace a dashboard layout (staff only)'),
    partial_update=extend_schema(tags=['layouts'], summary='Partially update a dashboard layout (staff only)'),
    destroy=extend_schema(tags=['layouts'], summary='Delete a dashboard layout (staff only)'),
)
class DashboardLayoutViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DashboardLayout model.

    Read operations (GET, HEAD, OPTIONS) are open to all authenticated users.
    Write operations (POST, PUT, PATCH, DELETE) require is_staff=True AND
    are throttled by BurstUserThrottle to prevent layout-mutation storms.
    """

    queryset = DashboardLayout.objects.all()
    serializer_class = DashboardLayoutSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'layout_type', 'created_at']
    ordering = ['name']

    def get_throttles(self) -> List[BaseThrottle]:
        """
        Apply BurstUserThrottle on write operations only.

        WIRED (v1.1.0): BurstUserThrottle was defined but never applied.
        Using get_throttles() rather than throttle_classes at class level
        lets read operations remain unthrottled while writes are rate-limited.
        This is preferable to a blanket throttle_classes = [BurstUserThrottle]
        which would also throttle admin list views.
        """
        write_actions = {'create', 'update', 'partial_update', 'destroy'}
        if self.action in write_actions:
            return [BurstUserThrottle()]
        return super().get_throttles()

    @extend_schema(
        tags=['layouts'],
        summary='List layouts by type',
        parameters=[
            OpenApiParameter(
                name='layout_type', type=str, location=OpenApiParameter.QUERY,
                required=True, description="e.g. 'grid', 'freeform' — see LayoutType choices.",
            ),
        ],
        responses={200: DashboardLayoutSerializer(many=True)},
    )
    @require_query_param('layout_type')
    @action(detail=False, methods=['get'])
    def by_type(self, request: Request) -> Response:
        """
        GET /api/layouts/by_type/?layout_type=grid
        Returns all layouts of the specified type.

        DRY FIX (v1.5.0): now uses @require_query_param (was a manual
        missing-param check) and DashboardLayout.objects.by_type() (was
        a raw .filter(layout_type=...) call) — DashboardLayoutManager
        exists specifically so this call is never repeated raw, but this
        one action had been missed when every sibling viewset was
        converted.
        """
        layout_type = request.query_params['layout_type']
        layouts = DashboardLayout.objects.by_type(layout_type)
        serializer = self.get_serializer(layouts, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['layouts'],
        summary='List layouts by creator',
        parameters=[
            OpenApiParameter(
                name='created_by', type=str, location=OpenApiParameter.QUERY,
                required=True, description='Look up layouts created by this identifier.',
            ),
        ],
        responses={200: DashboardLayoutSerializer(many=True)},
    )
    @require_query_param('created_by')
    @action(detail=False, methods=['get'])
    def by_creator(self, request: Request) -> Response:
        """
        GET /api/layouts/by_creator/?created_by=<id>

        WIRED (v1.5.0): DashboardLayoutManager.by_creator() was defined
        — and DashboardLayout.created_by has had a dedicated DB index
        (dl_created_by_idx) since the initial migration — but no endpoint
        ever queried by it. Same shape as by_type() above.
        """
        created_by = request.query_params['created_by']
        layouts = DashboardLayout.objects.by_creator(created_by)
        serializer = self.get_serializer(layouts, many=True)
        return Response(serializer.data)
