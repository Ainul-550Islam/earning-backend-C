"""
Widget Configuration viewset for Real-time Dashboard Backend.

DRY FIX (v1.3.0): by_widget() used a manual missing-param check:
    widget_id = request.query_params.get('widget_id')
    if not widget_id:
        return Response({'success': False, 'error': '...'}, status=400)

This is the same pattern already used in 4 other viewsets.
Replaced with @require_query_param('widget_id') — single implementation.
"""
from typing import Type

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from django_filters.rest_framework import DjangoFilterBackend

from ..models.widget_configuration import WidgetConfiguration
from ..serializers.widget_configuration_serializer import (
    WidgetConfigurationSerializer,
    WidgetConfigurationListSerializer,
)
from ..pagination import StandardResultsSetPagination
from ..filters import WidgetConfigurationFilter
from ..decorators import require_query_param


@extend_schema_view(
    list=extend_schema(tags=['widget-configurations'], summary='List widget configurations'),
    retrieve=extend_schema(tags=['widget-configurations'], summary='Get a widget configuration'),
    create=extend_schema(tags=['widget-configurations'], summary='Create a widget configuration'),
    update=extend_schema(tags=['widget-configurations'], summary='Replace a widget configuration'),
    partial_update=extend_schema(tags=['widget-configurations'], summary='Partially update a widget configuration'),
    destroy=extend_schema(tags=['widget-configurations'], summary='Delete a widget configuration'),
)
class WidgetConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for WidgetConfiguration model."""

    # select_related('widget') prevents N+1: the str(obj) for WidgetConfiguration
    # calls widget.name, so without it every list row fires an extra query.
    queryset = WidgetConfiguration.objects.select_related('widget').all()
    serializer_class = WidgetConfigurationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WidgetConfigurationFilter
    search_fields = ['key', 'widget__name']
    ordering_fields = ['widget', 'config_type', 'key', 'created_at']
    ordering = ['widget', 'config_type', 'key']

    def get_serializer_class(self) -> Type[BaseSerializer]:
        if self.action == 'list':
            return WidgetConfigurationListSerializer
        return WidgetConfigurationSerializer

    @extend_schema(
        tags=['widget-configurations'],
        summary='List configuration entries for a widget',
        parameters=[
            OpenApiParameter(
                name='widget_id', type=int, location=OpenApiParameter.QUERY,
                required=True, description='The DashboardWidget ID to fetch key/value config for.',
            ),
        ],
        responses={200: WidgetConfigurationListSerializer(many=True)},
    )
    @require_query_param('widget_id')
    @action(detail=False, methods=['get'])
    def by_widget(self, request: Request) -> Response:
        """
        GET /api/configurations/by_widget/?widget_id=<id>

        DRY FIX (v1.3.0): manual missing-param check replaced with
        @require_query_param — the same decorator used by all other
        viewsets. The decorator returns 400 with a consistent error
        envelope if widget_id is absent.
        """
        widget_id = request.query_params['widget_id']
        configurations = self.queryset.by_widget(widget_id)
        serializer = self.get_serializer(configurations, many=True)
        return Response(serializer.data)
