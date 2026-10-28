"""
tasks/viewsets/TaskResultViewSet.py
CRUD + filtering for TaskResult (Celery task execution records).
"""
import logging
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

logger = logging.getLogger(__name__)


class TaskResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for TaskResult records.
    Admin-only: lists all task execution results with filtering.
    """
    permission_classes  = [IsAuthenticated, IsAdminUser]
    filter_backends     = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields    = ['status', 'task_name', 'queue', 'worker']
    search_fields       = ['task_name', 'task_id', 'worker']
    ordering_fields     = ['date_created', 'duration_seconds', 'status']
    ordering            = ['-date_created']

    def get_queryset(self):
        try:
            from api.tasks.models.core import TaskResult
            return TaskResult.objects.all()
        except Exception:
            from api.tasks.models.core import TaskResult
            return TaskResult.objects.none()

    def get_serializer_class(self):
        from rest_framework import serializers

        class TaskResultSerializer(serializers.ModelSerializer):
            class Meta:
                try:
                    from api.tasks.models.core import TaskResult
                    model  = TaskResult
                except Exception:
                    model  = None
                fields = [
                    'id', 'task_id', 'task_name', 'status',
                    'date_created', 'date_started', 'date_done',
                    'duration_seconds', 'result', 'traceback',
                    'worker', 'queue', 'retry_count',
                ]

        return TaskResultSerializer

    @action(detail=False, methods=['get'], url_path='by-task/(?P<task_name>[^/.]+)')
    def by_task(self, request, task_name=None):
        """Return results filtered by task name."""
        qs = self.get_queryset().filter(task_name=task_name)
        serializer = self.get_serializer(qs[:100], many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return aggregate stats: count by status."""
        from django.db.models import Count
        qs     = self.get_queryset()
        counts = qs.values('status').annotate(count=Count('id'))
        return Response({'status_counts': list(counts)})
