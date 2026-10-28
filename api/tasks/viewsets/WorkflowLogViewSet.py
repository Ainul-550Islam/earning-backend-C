"""viewsets/WorkflowLogViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class WorkflowLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to workflow execution logs."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['task_name', 'status', 'celery_task_id']
    ordering_fields    = ['step_number', 'duration_seconds']
    ordering           = ['step_number']

    def get_queryset(self):
        WorkflowLog = apps.get_model('tasks', 'WorkflowLog')
        qs = WorkflowLog.objects.select_related('instance').all()
        if instance_id := self.request.query_params.get('instance_id'):
            qs = qs.filter(instance_id=instance_id)
        if status := self.request.query_params.get('status'):
            qs = qs.filter(status=status)
        return qs

    def get_serializer_class(self):
        from api.tasks.serializers import WorkflowLogSerializer
        return WorkflowLogSerializer

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Aggregate success/failure counts grouped by task_name."""
        from django.db.models import Count, Avg
        WorkflowLog = apps.get_model('tasks', 'WorkflowLog')
        data = (WorkflowLog.objects.values('task_name', 'status')
                .annotate(count=Count('id'), avg_duration=Avg('duration_seconds'))
                .order_by('task_name'))
        return Response(list(data))
