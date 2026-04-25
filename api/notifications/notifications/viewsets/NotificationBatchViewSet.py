# earning_backend/api/notifications/viewsets/NotificationBatchViewSet.py
"""
NotificationBatchViewSet — track bulk-send batch jobs.

Endpoints:
  GET  /batches/         — list batches
  GET  /batches/{id}/    — retrieve batch with progress
  POST /batches/{id}/cancel/ — cancel a queued/processing batch
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class NotificationBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for NotificationBatch — read-only + cancel action."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from notifications.models.schedule import NotificationBatch
        qs = NotificationBatch.objects.all().select_related('template', 'segment', 'created_by')
        batch_status = self.request.query_params.get('status')
        if batch_status:
            qs = qs.filter(status=batch_status)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from notifications.models.schedule import NotificationBatch

        class BatchSerializer(serializers.ModelSerializer):
            progress_pct = serializers.FloatField(read_only=True)
            success_rate = serializers.FloatField(read_only=True)

            class Meta:
                model = NotificationBatch
                fields = [
                    'id', 'name', 'description', 'status', 'total_count',
                    'sent_count', 'delivered_count', 'failed_count', 'skipped_count',
                    'progress_pct', 'success_rate', 'context', 'started_at',
                    'completed_at', 'celery_task_id', 'created_by', 'created_at',
                ]
                read_only_fields = ['__all__']

        return BatchSerializer

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a queued or processing batch."""
        from notifications.models.schedule import NotificationBatch
        from django.utils import timezone

        batch = self.get_object()
        if batch.status not in ('draft', 'queued', 'processing'):
            return Response(
                {'success': False, 'error': f'Cannot cancel batch in status: {batch.status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch.status = 'cancelled'
        batch.save(update_fields=['status', 'updated_at'])
        return Response({'success': True, 'id': batch.pk, 'status': 'cancelled'})
