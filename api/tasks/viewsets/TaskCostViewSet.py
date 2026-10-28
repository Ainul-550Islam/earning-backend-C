"""tasks/viewsets/TaskCostViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class TaskCostViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering           = ['-cost_per_run']

    def get_queryset(self):
        from api.tasks.models.analytics import TaskCostEstimate
        return TaskCostEstimate.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.analytics import TaskCostEstimate
        class S(serializers.ModelSerializer):
            class Meta:
                model  = TaskCostEstimate
                fields = '__all__'
        return S

    @action(detail=False, methods=['get'])
    def top_costly(self, request):
        """Return the most expensive tasks."""
        from api.tasks.services.TaskCostService import TaskCostService
        limit = int(request.query_params.get('limit', 10))
        data  = TaskCostService().get_top_costly_tasks(limit=limit)
        return Response(data)

    @action(detail=False, methods=['post'])
    def refresh_all(self, request):
        """Recompute cost estimates for all tasks."""
        from api.tasks.services.TaskCostService import TaskCostService
        result = TaskCostService().refresh_all()
        return Response(result)

    @action(detail=False, methods=['post'])
    def estimate(self, request):
        """Estimate cost for a specific task_name."""
        from api.tasks.services.TaskCostService import TaskCostService
        task_name = request.data.get('task_name')
        period    = request.data.get('period', 'last_7_days')
        if not task_name:
            return Response({'error': 'task_name is required'}, status=status.HTTP_400_BAD_REQUEST)
        result = TaskCostService().update_cost_estimate(task_name, estimation_period=period)
        return Response(result)
