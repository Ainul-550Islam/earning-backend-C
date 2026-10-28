"""
tasks/viewsets/ScheduledTaskViewSet.py
Full CRUD + run_now + pause/resume actions for ScheduledTask.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

logger = logging.getLogger(__name__)


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering           = ['name']

    def get_queryset(self):
        from api.tasks.models.core import ScheduledTask
        return ScheduledTask.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.core import ScheduledTask

        class ScheduledTaskSerializer(serializers.ModelSerializer):
            success_rate    = serializers.ReadOnlyField()
            is_running      = serializers.ReadOnlyField()
            is_expired      = serializers.ReadOnlyField()

            class Meta:
                model  = ScheduledTask
                fields = '__all__'
                read_only_fields = [
                    'last_run_at', 'last_run_status', 'total_runs',
                    'total_failures', 'avg_duration_sec', 'success_rate',
                    'is_running', 'is_expired',
                ]

        return ScheduledTaskSerializer

    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Manually trigger the scheduled task immediately."""
        obj = self.get_object()
        try:
            from celery import current_app
            result = current_app.send_task(
                obj.task_name,
                args=obj.task_args or [],
                kwargs=obj.task_kwargs or {},
                queue=obj.queue or 'default',
            )
            return Response({'status': 'dispatched', 'task_id': result.id})
        except Exception as e:
            logger.error(f"[ERROR] run_now failed for {obj.name}: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause the scheduled task."""
        obj = self.get_object()
        obj.pause()
        return Response({'status': 'paused', 'id': obj.pk})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused scheduled task."""
        obj = self.get_object()
        obj.resume()
        return Response({'status': 'resumed', 'id': obj.pk})
