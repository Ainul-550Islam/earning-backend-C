from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import OfferBlacklist
from ..serializers.SmartLinkSerializer import SmartLinkSerializer
from ..permissions import IsPublisher
from rest_framework import serializers as drf_serializers


class OfferBlacklistSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = OfferBlacklist
        fields = ['id', 'offer', 'reason', 'created_at']
        read_only_fields = ['created_at']


class OfferBlacklistViewSet(viewsets.ModelViewSet):
    """Manage offer blacklist entries for a SmartLink."""
    serializer_class = OfferBlacklistSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        return OfferBlacklist.objects.filter(smartlink_id=self.kwargs.get('smartlink_pk'))

    def perform_create(self, serializer):
        serializer.save(
            smartlink_id=self.kwargs.get('smartlink_pk'),
            added_by=self.request.user,
        )
