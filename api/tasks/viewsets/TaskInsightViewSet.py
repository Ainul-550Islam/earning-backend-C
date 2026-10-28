"""tasks/viewsets/TaskInsightViewSet.py"""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

class TaskInsightViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['task_name', 'date', 'queue']
    ordering_fields    = ['date', 'run_count', 'failure_count', 'avg_duration']
    ordering           = ['-date']

    def get_queryset(self):
        from api.tasks.models.analytics import TaskInsight
        return TaskInsight.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.analytics import TaskInsight
        class S(serializers.ModelSerializer):
            success_rate  = serializers.ReadOnlyField()
            failure_rate  = serializers.ReadOnlyField()
            class Meta:
                model  = TaskInsight
                fields = '__all__'
        return S

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """Return daily trend for a task_name over N days."""
        from api.tasks.services.TaskAnalyticsService import TaskAnalyticsService
        task_name = request.query_params.get('task_name')
        days      = int(request.query_params.get('days', 14))
        data      = TaskAnalyticsService().get_daily_trend(task_name=task_name, days=days)
        return Response(data)

    @action(detail=False, methods=['get'])
    def top_tasks(self, request):
        """Return top tasks by completions or failure_rate."""
        from api.tasks.services.TaskAnalyticsService import TaskAnalyticsService
        by    = request.query_params.get('by', 'completions')
        limit = int(request.query_params.get('limit', 10))
        days  = int(request.query_params.get('days', 7))
        data  = TaskAnalyticsService().get_top_tasks(by=by, limit=limit, days=days)
        return Response(data)

    @action(detail=False, methods=['get'])
    def platform_stats(self, request):
        """Return platform-wide aggregate stats."""
        from api.tasks.services.TaskAnalyticsService import TaskAnalyticsService
        days = int(request.query_params.get('days', 30))
        data = TaskAnalyticsService().get_platform_stats(days=days)
        return Response(data)

    @action(detail=False, methods=['post'])
    def recalculate(self, request):
        """Trigger daily analytics rollup for a specific date."""
        from api.tasks.analytics_tasks import daily_analytics_rollup
        date_str = request.data.get('date')
        result   = daily_analytics_rollup.apply_async(kwargs={'date_str': date_str})
        return Response({'task_id': result.id, 'status': 'queued'})
