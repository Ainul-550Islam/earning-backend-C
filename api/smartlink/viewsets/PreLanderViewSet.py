from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import PreLander
from ..serializers.PreLanderSerializer import PreLanderSerializer
from ..permissions import IsPublisher


class PreLanderViewSet(viewsets.ModelViewSet):
    serializer_class = PreLanderSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        return PreLander.objects.filter(smartlink_id=self.kwargs.get('smartlink_pk'))

    def perform_create(self, serializer):
        serializer.save(smartlink_id=self.kwargs.get('smartlink_pk'))
