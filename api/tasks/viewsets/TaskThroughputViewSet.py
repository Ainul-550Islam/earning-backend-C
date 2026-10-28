"""viewsets/TaskThroughputViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps
from django.db.models import Avg, Max

logger = logging.getLogger(__name__)


class TaskThroughputViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only analytics for per-queue task throughput snapshots."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['queue_name']
    ordering_fields    = ['snapshot_at', 'tasks_per_minute', 'tasks_per_hour']
    ordering           = ['-snapshot_at']

    def get_queryset(self):
        TaskThroughput = apps.get_model('tasks', 'TaskThroughput')
        qs = TaskThroughput.objects.all()
        if queue := self.request.query_params.get('queue_name'):
            qs = qs.filter(queue_name=queue)
        if period := self.request.query_params.get('period'):
            qs = qs.filter(period=period)
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import TaskThroughputSerializer
        return TaskThroughputSerializer

    @action(detail=False, methods=['get'], url_path='averages')
    def averages(self, request):
        """Return average throughput per queue."""
        TaskThroughput = apps.get_model('tasks', 'TaskThroughput')
        data = (TaskThroughput.objects
                .values('queue_name')
                .annotate(
                    avg_per_minute=Avg('tasks_per_minute'),
                    avg_per_hour=Avg('tasks_per_hour'),
                    peak_per_minute=Max('tasks_per_minute'),
                )
                .order_by('queue_name'))
        return Response(list(data))

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        """Return most recent snapshot per queue."""
        TaskThroughput = apps.get_model('tasks', 'TaskThroughput')
        from django.db.models import OuterRef, Subquery
        latest_ids = (TaskThroughput.objects
                      .filter(queue_name=OuterRef('queue_name'))
                      .order_by('-snapshot_at')
                      .values('id')[:1])
        qs = TaskThroughput.objects.filter(id__in=Subquery(latest_ids))
        return Response(self.get_serializer(qs, many=True).data)
