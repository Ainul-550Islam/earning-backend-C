"""viewsets/TaskRetryConfigViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class TaskRetryConfigViewSet(viewsets.ModelViewSet):
    """Manage per-task retry and backoff configuration."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['task_name', 'description']
    ordering_fields    = ['task_name', 'max_retries']
    ordering           = ['task_name']

    def get_queryset(self):
        TaskRetryConfig = apps.get_model('tasks', 'TaskRetryConfig')
        return TaskRetryConfig.objects.all()

    def get_serializer_class(self):
        from api.tasks.serializers import TaskRetryConfigSerializer
        return TaskRetryConfigSerializer

    @action(detail=False, methods=['get'], url_path='for-task')
    def for_task(self, request):
        """Return retry config for a specific task name."""
        task_name = request.query_params.get('task_name', '')
        TaskRetryConfig = apps.get_model('tasks', 'TaskRetryConfig')
        try:
            obj = TaskRetryConfig.objects.get(task_name=task_name)
            return Response(self.get_serializer(obj).data)
        except TaskRetryConfig.DoesNotExist:
            return Response({'error': f'No retry config for task: {task_name}'}, status=404)

    @action(detail=True, methods=['post'], url_path='reset-defaults')
    def reset_defaults(self, request, pk=None):
        """Reset retry config to sensible defaults."""
        obj = self.get_object()
        obj.max_retries             = 3
        obj.retry_delay_seconds     = 60
        obj.backoff_multiplier      = 2.0
        obj.max_retry_delay_seconds = 3600
        obj.jitter                  = True
        obj.save()
        return Response(self.get_serializer(obj).data)
