"""
Trace Span views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..serializers.trace_serializer import (
    TraceSpanSerializer,
    TraceSpanCreateSerializer,
    TraceSpanFinishSerializer,
)
from ..services.trace_service import TraceService


class TraceView(APIView):
    """
    Class-based API view for TraceSpan operations.

    GET  /api/v1/telemetry/traces/                → list spans (optionally filtered)
    GET  /api/v1/telemetry/traces/<trace_id>/     → retrieve all spans for a trace
    POST /api/v1/telemetry/traces/                → start a new span
    POST /api/v1/telemetry/traces/<trace_id>/finish/ (via viewset) → finish a span
    DELETE /api/v1/telemetry/traces/<trace_id>/   → delete all spans for a trace
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = TraceService()

    def get(self, request, trace_id=None):
        """
        List all spans or retrieve all spans belonging to a specific trace_id.

        Query params (list mode):
            service, status, search, limit
        """
        if trace_id is not None:
            spans = self.service.get_trace(trace_id)
            if not spans:
                return Response(
                    {'error': f'No spans found for trace_id "{trace_id}".'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = TraceSpanSerializer(spans, many=True)
            return Response(
                {
                    'trace_id': trace_id,
                    'total_spans': len(spans),
                    'spans': serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        # --- List mode ---
        from ..models.trace_span import TraceSpan
        queryset = TraceSpan.objects.all()

        service_name = request.query_params.get('service')
        span_status = request.query_params.get('status')
        search = request.query_params.get('search')

        if service_name:
            queryset = queryset.filter(service=service_name)
        if span_status:
            queryset = queryset.filter(status=span_status)
        if search:
            queryset = queryset.filter(operation_name__icontains=search)

        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return Response(
                {'error': "'limit' must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        spans = queryset.order_by('-start_time')[:limit]
        serializer = TraceSpanSerializer(spans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, trace_id=None):
        """
        Start a new trace span.
        If trace_id is provided in URL, it is used as the trace_id for the span.
        To finish a span, call the TraceViewSet's finish action instead.
        """
        data = request.data.copy()
        if trace_id:
            data['trace_id'] = trace_id

        serializer = TraceSpanCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        span = self.service.start_trace(serializer.validated_data)
        return Response(
            TraceSpanSerializer(span).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, trace_id=None):
        """
        Delete all spans for a given trace_id.
        """
        if trace_id is None:
            return Response(
                {'error': 'trace_id is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from ..models.trace_span import TraceSpan
        deleted_count, _ = TraceSpan.objects.filter(trace_id=trace_id).delete()
        if deleted_count == 0:
            return Response(
                {'error': f'No spans found for trace_id "{trace_id}".'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {'deleted': deleted_count, 'trace_id': trace_id},
            status=status.HTTP_200_OK,
        )
