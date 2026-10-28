"""tasks/viewsets/TaskMonitorViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class TaskMonitorViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['task_name']

    def get_queryset(self):
        from api.tasks.models.monitoring import TaskMonitor
        return TaskMonitor.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.monitoring import TaskMonitor
        class S(serializers.ModelSerializer):
            class Meta:
                model = TaskMonitor
                fields = '__all__'
        return S

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        from api.tasks.services.TaskMonitorService import TaskMonitorService
        updated = TaskMonitorService().refresh_all_monitors()
        return Response({'updated': updated})

    @action(detail=True, methods=['post'])
    def silence(self, request, pk=None):
        obj = self.get_object()
        minutes = int(request.data.get('minutes', 60))
        obj.silence_alerts(minutes=minutes)
        return Response({'status': 'silenced', 'minutes': minutes})
