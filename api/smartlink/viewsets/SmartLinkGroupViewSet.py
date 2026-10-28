from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from api.smartlink.models import SmartLinkGroup
from api.smartlink.serializers.SmartLinkGroupSerializer import SmartLinkGroupSerializer
from api.smartlink.permissions import IsPublisher


class SmartLinkGroupViewSet(viewsets.ModelViewSet):
    """Manage SmartLink groups (folders/campaigns)."""
    serializer_class = SmartLinkGroupSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SmartLinkGroup.objects.prefetch_related("smartlinks")
        return SmartLinkGroup.objects.filter(publisher=user)

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)