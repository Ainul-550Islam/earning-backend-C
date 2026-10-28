"""tasks/viewsets/WorkflowViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class WorkflowViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['name']

    def get_queryset(self):
        from api.tasks.models.workflow import TaskWorkflow
        return TaskWorkflow.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.workflow import TaskWorkflow
        class S(serializers.ModelSerializer):
            step_count = serializers.ReadOnlyField()
            class Meta:
                model = TaskWorkflow
                fields = '__all__'
        return S

    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        from api.tasks.services.WorkflowService import WorkflowService
        result = WorkflowService().trigger_workflow(
            workflow_id=int(pk),
            input_data=request.data.get('input_data', {}),
            triggered_by=request.user,
            trigger_type='manual',
        )
        code = status.HTTP_202_ACCEPTED if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        from api.tasks.services.WorkflowService import WorkflowService
        instances = WorkflowService().list_instances(workflow_id=int(pk), limit=50)
        return Response(instances)

    @action(detail=True, methods=['get'])
    def steps(self, request, pk=None):
        from api.tasks.models.workflow import WorkflowStep
        steps = list(
            WorkflowStep.objects.filter(workflow_id=int(pk))
            .order_by('step_number')
            .values()
        )
        return Response(steps)
