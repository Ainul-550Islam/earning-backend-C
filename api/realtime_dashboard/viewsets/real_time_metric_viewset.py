"""
Real-time Metric viewset for Real-time Dashboard Backend.

WIRED (v1.5.0 — verified by tracing actual call sites, not just docstrings.
Earlier versions of this file made the same "WIRED" claim below while
perform_create/update/destroy silently reimplemented the logic inline
instead of calling the service. That gap is what this pass closed):
  - perform_create  → RealTimeMetricService.create_metric()
  - perform_update  → RealTimeMetricService.update_metric()   (auto-tracks previous_value)
  - perform_destroy → RealTimeMetricService.delete_metric()

  - aggregate() action → utils.aggregate_metrics()
    POST /api/metrics/aggregate/
    utils.aggregate_metrics() was defined but NEVER called anywhere —
    the only place it could have been useful (combining multiple metrics
    into a summary) had no HTTP surface.

  - by_type() action → RealTimeMetricService.get_metrics_by_type()
    GET /api/metrics/by_type/?metric_type=gauge
    DRY: @require_query_param replaces the manual missing-param check.
"""
from typing import Any, Dict, List, Optional, Type, cast

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiParameter
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from django_filters.rest_framework import DjangoFilterBackend

from ..models.real_time_metric import RealTimeMetric
from ..serializers.real_time_metric_serializer import (
    RealTimeMetricSerializer,
    RealTimeMetricListSerializer,
)
from ..pagination import StandardResultsSetPagination
from ..filters import RealTimeMetricFilter
from ..throttling import MetricUpdateThrottle
from ..decorators import require_query_param
from ..services.real_time_metric_service import RealTimeMetricService
from ..utils import aggregate_metrics


@extend_schema_view(
    list=extend_schema(tags=['metrics'], summary='List real-time metrics'),
    retrieve=extend_schema(tags=['metrics'], summary='Get a real-time metric'),
    create=extend_schema(tags=['metrics'], summary='Create a real-time metric'),
    update=extend_schema(tags=['metrics'], summary='Replace a real-time metric'),
    partial_update=extend_schema(
        tags=['metrics'], summary='Partially update a real-time metric (e.g. push a new value)',
    ),
    destroy=extend_schema(tags=['metrics'], summary='Delete a real-time metric'),
)
class RealTimeMetricViewSet(viewsets.ModelViewSet):
    """ViewSet for RealTimeMetric model."""

    queryset = RealTimeMetric.objects.all()
    serializer_class = RealTimeMetricSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = RealTimeMetricFilter
    search_fields = ['name', 'description', 'unit']
    ordering_fields = ['name', 'metric_type', 'status', 'value', 'last_updated']
    ordering = ['-last_updated']
    throttle_classes = [MetricUpdateThrottle]

    def get_serializer_class(self) -> Type[BaseSerializer]:
        if self.action == 'list':
            return RealTimeMetricListSerializer
        return RealTimeMetricSerializer

    # ── Service-delegating lifecycle hooks ───────────────────────────────────

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        WIRED (v1.5.0): delegates to RealTimeMetricService.create_metric()
        — the single owner of "create a metric + prime its cache". DRF has
        already validated serializer.validated_data by the time this runs
        (is_valid(raise_exception=True) happens before perform_create in
        CreateModelMixin.create()), so no validation coverage is lost by
        not calling serializer.save() directly.
        """
        metric = RealTimeMetricService().create_metric(serializer.validated_data)
        serializer.instance = metric

    def perform_update(self, serializer: BaseSerializer) -> None:
        """
        WIRED (v1.5.0): delegates to RealTimeMetricService.update_metric()
        — the single owner of "auto-capture previous_value on value change,
        apply the update, refresh cache". Passes serializer.instance (the
        object DRF's get_object() already fetched) so update_metric()
        mutates it in place — serializer.data in the response reflects the
        change without a second DB round trip.
        """
        if serializer.instance is None:  # pragma: no cover - update serializers are always bound to an instance
            raise RuntimeError('serializer.instance is None on an update serializer — DRF contract violation')
        RealTimeMetricService().update_metric(serializer.instance, serializer.validated_data)

    def perform_destroy(self, instance: RealTimeMetric) -> None:
        """WIRED (v1.5.0): delegates to RealTimeMetricService.delete_metric()."""
        RealTimeMetricService().delete_metric(instance)

    # ── Custom actions ────────────────────────────────────────────────────────

    @extend_schema(tags=['metrics'], summary='Activate a metric', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @action(detail=True, methods=['post'])
    def activate(self, request: Request, pk: Optional[str] = None) -> Response:
        """POST /api/metrics/<id>/activate/"""
        metric = self.get_object()
        metric.status = 'active'
        metric.save()
        return Response({'success': True, 'message': f'Metric {metric.name} activated successfully'})

    @extend_schema(tags=['metrics'], summary='Deactivate a metric', request=None,
                   responses={200: {'type': 'object', 'properties': {
                       'success': {'type': 'boolean'}, 'message': {'type': 'string'}}}})
    @action(detail=True, methods=['post'])
    def deactivate(self, request: Request, pk: Optional[str] = None) -> Response:
        """POST /api/metrics/<id>/deactivate/"""
        metric = self.get_object()
        metric.status = 'inactive'
        metric.save()
        return Response({'success': True, 'message': f'Metric {metric.name} deactivated successfully'})

    @extend_schema(
        tags=['metrics'], summary='List active metrics',
        responses={200: RealTimeMetricListSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def active(self, request: Request) -> Response:
        """GET /api/metrics/active/ — list all active metrics."""
        metrics = self.queryset.active()
        serializer = self.get_serializer(metrics, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['metrics'],
        summary='List metrics by type',
        parameters=[
            OpenApiParameter(
                name='metric_type', type=str, location=OpenApiParameter.QUERY,
                required=True, description="e.g. 'gauge', 'counter' — see MetricType choices.",
            ),
        ],
        responses={200: RealTimeMetricListSerializer(many=True)},
    )
    @require_query_param('metric_type')
    @action(detail=False, methods=['get'])
    def by_type(self, request: Request) -> Response:
        """
        GET /api/metrics/by_type/?metric_type=gauge

        WIRED (v1.2.0): RealTimeMetricService.get_metrics_by_type() was
        defined but had no HTTP endpoint.
        DRY: @require_query_param replaces the manual missing-param check.
        """
        metric_type = request.query_params['metric_type']
        metrics = RealTimeMetricService().get_metrics_by_type(metric_type)
        serializer = self.get_serializer(metrics, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['metrics'],
        summary='Aggregate multiple metrics into one summary value',
        description=(
            'Business use-case: dashboards showing a single "composite" value from '
            'multiple underlying metrics (e.g. average CPU across all servers, total '
            'revenue across regions). Only active metrics among the given IDs are included.'
        ),
        request=inline_serializer(
            name='MetricAggregateRequest',
            fields={
                'metric_ids': serializers.ListField(child=serializers.IntegerField(), min_length=1),
                'aggregation': serializers.ChoiceField(
                    choices=['avg', 'sum', 'min', 'max', 'count'], required=False, default='avg',
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name='MetricAggregateResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'metric_ids': serializers.ListField(child=serializers.IntegerField()),
                    'aggregation': serializers.CharField(),
                    'count': serializers.IntegerField(),
                    'avg': serializers.FloatField(),
                    'min': serializers.FloatField(),
                    'max': serializers.FloatField(),
                    'sum': serializers.FloatField(),
                },
            ),
            400: inline_serializer(
                name='MetricAggregateBadRequest',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
            404: inline_serializer(
                name='MetricAggregateNotFound',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
        },
    )
    @action(detail=False, methods=['post'])
    def aggregate(self, request: Request) -> Response:
        """
        POST /api/metrics/aggregate/

        WIRED (v1.2.0): utils.aggregate_metrics() was defined but NEVER
        called from anywhere — completely floating.

        Request body:
            {
                "metric_ids": [1, 2, 3],
                "aggregation": "avg"   // optional: avg|sum|min|max|count
            }

        Returns a summary dict:
            {
                "success": true,
                "aggregation": "avg",
                "count": 3,
                "avg": 42.7,
                "min": 10.0,
                "max": 87.3,
                "sum": 128.1
            }

        Business use-case: dashboards showing a single "composite"
        value from multiple underlying metrics (e.g. average CPU across
        all servers, total revenue across regions).
        """
        metric_ids = request.data.get('metric_ids', [])
        aggregation = request.data.get('aggregation', 'avg')

        if not metric_ids:
            return Response(
                {'success': False, 'error': "'metric_ids' list is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metrics_qs = RealTimeMetric.objects.filter(id__in=metric_ids, status='active')
        metrics_data: List[Dict[str, Any]] = cast(
            List[Dict[str, Any]],
            list(metrics_qs.values('id', 'name', 'value', 'unit', 'metric_type')),
        )

        if not metrics_data:
            return Response(
                {'success': False, 'error': 'No active metrics found for the given IDs.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = aggregate_metrics(metrics_data)
        return Response({
            'success': True,
            'metric_ids': metric_ids,
            'aggregation': aggregation,
            **result,
        })
