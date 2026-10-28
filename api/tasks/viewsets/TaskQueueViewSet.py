"""tasks/viewsets/TaskQueueViewSet.py"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

logger = logging.getLogger(__name__)

class TaskQueueViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['-priority_level', 'name']

    def get_queryset(self):
        from api.tasks.models.queue import TaskQueue
        return TaskQueue.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.queue import TaskQueue
        class S(serializers.ModelSerializer):
            class Meta:
                model = TaskQueue
                fields = '__all__'
        return S

    @action(detail=False, methods=['get'])
    def with_depth(self, request):
        """Return all queues with their current depth."""
        from api.tasks.services.QueueDepthService import QueueDepthService
        depths = QueueDepthService().get_all_depths()
        return Response(depths)

    @action(detail=True, methods=['get'])
    def workers(self, request, pk=None):
        """Return workers consuming this queue."""
        from api.tasks.models.monitoring import WorkerHealth
        queue = self.get_object()
        workers = WorkerHealth.objects.filter(
            queue_names__contains=queue.name,
            status__in=['online', 'idle', 'busy'],
        ).values('worker_id', 'hostname', 'status', 'active_tasks', 'last_heartbeat')
        return Response(list(workers))
