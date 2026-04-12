from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import SmartLinkGroup
from ..serializers.SmartLinkGroupSerializer import SmartLinkGroupSerializer
from ..permissions import IsPublisher


class SmartLinkGroupViewSet(viewsets.ModelViewSet):
    """Manage SmartLink groups (folders/campaigns)."""
    serializer_class = SmartLinkGroupSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SmartLinkGroup.objects.all()
        return SmartLinkGroup.objects.filter(publisher=user)

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)
