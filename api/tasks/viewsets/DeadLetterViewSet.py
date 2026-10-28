"""tasks/viewsets/DeadLetterViewSet.py"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class DeadLetterViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['-failed_at']

    def get_queryset(self):
        from api.tasks.models.queue import TaskDeadLetterQueue
        return TaskDeadLetterQueue.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.queue import TaskDeadLetterQueue
        class S(serializers.ModelSerializer):
            class Meta:
                model = TaskDeadLetterQueue
                fields = '__all__'
        return S

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        from api.tasks.services.DeadLetterService import DeadLetterService
        notes  = request.data.get('notes', '')
        result = DeadLetterService().retry_entry(int(pk), notes=notes)
        code   = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=True, methods=['post'])
    def discard(self, request, pk=None):
        from api.tasks.services.DeadLetterService import DeadLetterService
        notes  = request.data.get('notes', '')
        result = DeadLetterService().discard_entry(int(pk), notes=notes)
        return Response(result)

    @action(detail=False, methods=['post'])
    def retry_all(self, request):
        from api.tasks.services.DeadLetterService import DeadLetterService
        task_name = request.data.get('task_name')
        result    = DeadLetterService().retry_all_pending(task_name=task_name)
        return Response(result)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.tasks.services.DeadLetterService import DeadLetterService
        return Response(DeadLetterService().get_stats())
