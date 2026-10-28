"""viewsets/TaskPriorityViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class TaskPriorityViewSet(viewsets.ModelViewSet):
    """Manage per-task queue priority and timeout settings."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['task_name', 'queue']
    ordering_fields    = ['priority', 'task_name', 'created_at']
    ordering           = ['-priority']

    def get_queryset(self):
        TaskPriority = apps.get_model('tasks', 'TaskPriority')
        qs = TaskPriority.objects.all()
        if queue := self.request.query_params.get('queue'):
            qs = qs.filter(queue=queue)
        if active_only := self.request.query_params.get('active_only'):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import TaskPrioritySerializer
        return TaskPrioritySerializer

    @action(detail=False, methods=['get'], url_path='by-queue')
    def by_queue(self, request):
        """Return tasks grouped by queue, ordered by priority."""
        from collections import defaultdict
        qs = self.get_queryset().filter(is_active=True).order_by('queue', '-priority')
        grouped = defaultdict(list)
        for item in self.get_serializer(qs, many=True).data:
            grouped[item['queue']].append(item)
        return Response(dict(grouped))

    @action(detail=True, methods=['post'], url_path='boost')
    def boost_priority(self, request, pk=None):
        """Increase priority by given amount (default 10)."""
        obj = self.get_object()
        amount = int(request.data.get('amount', 10))
        obj.priority = min(obj.priority + amount, 100)
        obj.save(update_fields=['priority'])
        return Response({'priority': obj.priority})
