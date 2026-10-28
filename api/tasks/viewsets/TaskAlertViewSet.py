"""tasks/viewsets/TaskAlertViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class TaskAlertViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['task_name', 'alert_type']

    def get_queryset(self):
        from api.tasks.models.monitoring import TaskAlert
        return TaskAlert.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.monitoring import TaskAlert
        class S(serializers.ModelSerializer):
            is_in_cooldown = serializers.ReadOnlyField()
            class Meta:
                model = TaskAlert
                fields = '__all__'
        return S

    @action(detail=False, methods=['post'])
    def evaluate_all(self, request):
        from api.tasks.services.TaskAlertService import TaskAlertService
        fired = TaskAlertService().evaluate_all()
        return Response({'fired': fired, 'count': len(fired)})

    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        from api.tasks.services.TaskAlertService import TaskAlertService
        result = TaskAlertService().trigger_manual(int(pk))
        return Response(result)
