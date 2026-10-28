"""tasks/viewsets/WorkerHealthViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class WorkerHealthViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['-last_heartbeat']

    def get_queryset(self):
        from api.tasks.models.monitoring import WorkerHealth
        return WorkerHealth.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.monitoring import WorkerHealth
        class S(serializers.ModelSerializer):
            is_stale  = serializers.ReadOnlyField()
            load_pct  = serializers.ReadOnlyField()
            class Meta:
                model = WorkerHealth
                fields = '__all__'
        return S

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        from api.tasks.services.WorkerHealthService import WorkerHealthService
        summary = WorkerHealthService().refresh()
        return Response(summary)
