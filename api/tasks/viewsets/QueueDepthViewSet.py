"""tasks/viewsets/QueueDepthViewSet.py"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class QueueDepthViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    ordering = ['-checked_at']

    def get_queryset(self):
        from api.tasks.models.monitoring import QueueDepth
        return QueueDepth.objects.all()

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.tasks.models.monitoring import QueueDepth
        class S(serializers.ModelSerializer):
            class Meta:
                model = QueueDepth
                fields = '__all__'
        return S

    @action(detail=False, methods=['get'])
    def current(self, request):
        from api.tasks.services.QueueDepthService import QueueDepthService
        return Response(QueueDepthService().get_all_depths())

    @action(detail=False, methods=['post'])
    def snapshot(self, request):
        from api.tasks.services.QueueDepthService import QueueDepthService
        snapshots = QueueDepthService().snapshot_all()
        return Response({'snapshots': snapshots, 'count': len(snapshots)})

    @action(detail=False, methods=['get'])
    def threshold_check(self, request):
        from api.tasks.services.QueueDepthService import QueueDepthService
        alerts = QueueDepthService().check_thresholds()
        return Response({'alerts': alerts})
