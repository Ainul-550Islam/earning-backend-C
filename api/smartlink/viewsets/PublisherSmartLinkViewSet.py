from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from api.smartlink.models.publisher import PublisherSmartLink
from api.smartlink.serializers.PublisherSmartLinkSerializer import PublisherSmartLinkSerializer
from api.smartlink.permissions import IsPublisher


class PublisherSmartLinkViewSet(viewsets.ReadOnlyModelViewSet):
    """Publisher view of their SmartLink assignments."""
    serializer_class = PublisherSmartLinkSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        return PublisherSmartLink.objects.filter(
            publisher=self.request.user, is_active=True
        ).select_related('smartlink')