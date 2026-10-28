"""
Metric views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models.metric_event import MetricEvent
from ..serializers.metric_serializer import (
    MetricEventSerializer,
    MetricEventCreateSerializer,
    MetricStatisticsSerializer,
    MetricBatchCreateSerializer,
)
from ..services.metrics_collector import MetricsCollectorService


class MetricView(APIView):
    """
    Class-based API view for MetricEvent CRUD operations.

    GET  /api/v1/telemetry/metrics/              → list metrics (with optional filters)
    GET  /api/v1/telemetry/metrics/<metric_id>/  → retrieve single metric
    POST /api/v1/telemetry/metrics/              → create metric
    DELETE /api/v1/telemetry/metrics/<metric_id>/ → delete metric
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = MetricsCollectorService()

    def get(self, request, metric_id=None):
        """
        List all metrics (with optional query params) or retrieve a single metric by ID.

        Query params (list mode):
            name, metric_type, source, service, environment, limit
        """
        if metric_id is not None:
            try:
                metric = MetricEvent.objects.get(id=metric_id)
            except MetricEvent.DoesNotExist:
                return Response(
                    {'error': f'Metric with id {metric_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = MetricEventSerializer(metric)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # --- List mode ---
        name = request.query_params.get('name')
        metric_type = request.query_params.get('metric_type')
        source = request.query_params.get('source')
        service_name = request.query_params.get('service')
        environment = request.query_params.get('environment')

        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return Response(
                {'error': "'limit' must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metrics = self.service.get_metrics(
            name=name,
            metric_type=metric_type,
            source=source,
            service=service_name,
            environment=environment,
            limit=limit,
        )
        serializer = MetricEventSerializer(metrics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, metric_id=None):
        """
        Create a new metric event.
        Supports single creation and batch via ?batch=true.
        """
        if request.query_params.get('batch', '').lower() == 'true':
            batch_serializer = MetricBatchCreateSerializer(data=request.data)
            if not batch_serializer.is_valid():
                return Response(batch_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            metrics = self.service.batch_collect_metrics(
                batch_serializer.validated_data['metrics']
            )
            return Response(
                MetricEventSerializer(metrics, many=True).data,
                status=status.HTTP_201_CREATED,
            )

        serializer = MetricEventCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        metric = self.service.collect_metric(serializer.validated_data)
        return Response(
            MetricEventSerializer(metric).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, metric_id=None):
        """
        Delete a metric by ID.
        """
        if metric_id is None:
            return Response(
                {'error': 'metric_id is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            metric = MetricEvent.objects.get(id=metric_id)
        except MetricEvent.DoesNotExist:
            return Response(
                {'error': f'Metric with id {metric_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        metric.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
