from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from ..models import GeoTargeting
from ..serializers.GeoTargetingSerializer import GeoTargetingSerializer
from ..permissions import IsPublisher


class GeoTargetingViewSet(viewsets.ModelViewSet):
    """Manage geo targeting rules for a SmartLink."""
    serializer_class = GeoTargetingSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return GeoTargeting.objects.filter(rule__smartlink_id=sl_pk)

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        from ..models import TargetingRule
        rule, _ = TargetingRule.objects.get_or_create(smartlink_id=sl_pk)
        serializer.save(rule=rule)
