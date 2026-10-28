"""tasks/viewsets/WorkflowInstanceViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class WorkflowInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['-created_at']

    def get_queryset(self):
        from api.tasks.models.workflow import WorkflowInstance
        return WorkflowInstance.objects.select_related('workflow').all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.workflow import WorkflowInstance
        class S(serializers.ModelSerializer):
            workflow_name    = serializers.CharField(source='workflow.name', read_only=True)
            duration_seconds = serializers.ReadOnlyField()
            class Meta:
                model = WorkflowInstance
                fields = '__all__'
        return S

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        from api.tasks.services.WorkflowService import WorkflowService
        logs = WorkflowService().get_instance_logs(int(pk))
        return Response(logs)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        from api.tasks.services.WorkflowService import WorkflowService
        reason = request.data.get('reason', '')
        result = WorkflowService().cancel_instance(int(pk), reason=reason)
        code   = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)
