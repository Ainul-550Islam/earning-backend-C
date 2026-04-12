from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import LandingPage
from ..serializers.LandingPageSerializer import LandingPageSerializer
from ..permissions import IsPublisher


class LandingPageViewSet(viewsets.ModelViewSet):
    serializer_class = LandingPageSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        return LandingPage.objects.filter(smartlink_id=self.kwargs.get('smartlink_pk'))

    def perform_create(self, serializer):
        serializer.save(smartlink_id=self.kwargs.get('smartlink_pk'))
