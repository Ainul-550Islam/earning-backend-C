"""
Log Entry views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models.log_entry import LogEntry
from ..serializers.log_serializer import (
    LogEntrySerializer,
    LogEntryCreateSerializer,
    LogBatchCreateSerializer,
)


class LogView(APIView):
    """
    Class-based API view for LogEntry CRUD operations.

    GET    /api/v1/telemetry/logs/             → list logs (with optional filters)
    GET    /api/v1/telemetry/logs/<log_id>/    → retrieve single log entry
    POST   /api/v1/telemetry/logs/             → create log entry
    DELETE /api/v1/telemetry/logs/<log_id>/    → delete log entry
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, log_id=None):
        """
        List all log entries (with optional query params) or retrieve one by ID.

        Query params (list mode):
            level, source, service, environment, search, limit
        """
        if log_id is not None:
            try:
                log = LogEntry.objects.get(id=log_id)
            except LogEntry.DoesNotExist:
                return Response(
                    {'error': f'Log entry with id {log_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = LogEntrySerializer(log)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # --- List mode ---
        queryset = LogEntry.objects.all()

        level = request.query_params.get('level')
        source = request.query_params.get('source')
        service_name = request.query_params.get('service')
        environment = request.query_params.get('environment')
        search = request.query_params.get('search')

        if level:
            queryset = queryset.filter(level=level)
        if source:
            queryset = queryset.filter(source=source)
        if service_name:
            queryset = queryset.filter(service=service_name)
        if environment:
            queryset = queryset.filter(environment=environment)
        if search:
            queryset = queryset.filter(message__icontains=search)

        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return Response(
                {'error': "'limit' must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logs = queryset.order_by('-timestamp')[:limit]
        serializer = LogEntrySerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, log_id=None):
        """
        Create a new log entry.
        Supports single creation and batch via ?batch=true.
        """
        if request.query_params.get('batch', '').lower() == 'true':
            batch_serializer = LogBatchCreateSerializer(data=request.data)
            if not batch_serializer.is_valid():
                return Response(batch_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            logs = [
                LogEntry.objects.create(**log_data)
                for log_data in batch_serializer.validated_data['logs']
            ]
            return Response(
                LogEntrySerializer(logs, many=True).data,
                status=status.HTTP_201_CREATED,
            )

        serializer = LogEntryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        log = LogEntry.objects.create(**serializer.validated_data)
        return Response(
            LogEntrySerializer(log).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, log_id=None):
        """
        Delete a log entry by ID.
        """
        if log_id is None:
            return Response(
                {'error': 'log_id is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            log = LogEntry.objects.get(id=log_id)
        except LogEntry.DoesNotExist:
            return Response(
                {'error': f'Log entry with id {log_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
