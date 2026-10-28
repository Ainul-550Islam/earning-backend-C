"""tasks/viewsets/TaskPerformanceViewSet.py"""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

class TaskPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['task_name', 'result', 'queue', 'worker']
    ordering_fields    = ['created_at', 'duration_seconds']
    ordering           = ['-created_at']

    def get_queryset(self):
        from api.tasks.models.monitoring import TaskPerformanceLog
        return TaskPerformanceLog.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.monitoring import TaskPerformanceLog
        class S(serializers.ModelSerializer):
            class Meta:
                model = TaskPerformanceLog
                fields = '__all__'
        return S

    @action(detail=False, methods=['get'])
    def charts(self, request):
        from api.tasks.services.TaskAnalyticsService import TaskAnalyticsService
        task_name = request.query_params.get('task_name')
        days      = int(request.query_params.get('days', 7))
        trend     = TaskAnalyticsService().get_daily_trend(task_name=task_name, days=days)
        return Response({'trend': trend})
