"""viewsets/TaskFailureRateViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class TaskFailureRateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only analytics for task failure rates per period."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['task_name', 'most_common_error']
    ordering_fields    = ['failure_pct', 'total_runs', 'period_start']
    ordering           = ['-failure_pct']

    def get_queryset(self):
        TaskFailureRate = apps.get_model('tasks', 'TaskFailureRate')
        qs = TaskFailureRate.objects.all()
        if task_name := self.request.query_params.get('task_name'):
            qs = qs.filter(task_name=task_name)
        if period := self.request.query_params.get('period'):
            qs = qs.filter(period=period)
        if min_pct := self.request.query_params.get('min_failure_pct'):
            qs = qs.filter(failure_pct__gte=float(min_pct))
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import TaskFailureRateSerializer
        return TaskFailureRateSerializer

    @action(detail=False, methods=['get'], url_path='worst')
    def worst_tasks(self, request):
        """Return top 10 tasks with the highest failure rate."""
        TaskFailureRate = apps.get_model('tasks', 'TaskFailureRate')
        qs = TaskFailureRate.objects.order_by('-failure_pct')[:10]
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='healthy')
    def healthy_tasks(self, request):
        """Return tasks with failure rate < 5%."""
        TaskFailureRate = apps.get_model('tasks', 'TaskFailureRate')
        qs = TaskFailureRate.objects.filter(failure_pct__lt=5).order_by('task_name')
        return Response(self.get_serializer(qs, many=True).data)
