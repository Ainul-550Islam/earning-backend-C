from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from api.smartlink.models import DeviceTargeting
from api.smartlink.serializers.DeviceTargetingSerializer import DeviceTargetingSerializer
from api.smartlink.permissions import IsPublisher


class DeviceTargetingViewSet(viewsets.ModelViewSet):
    """Manage device targeting rules for a SmartLink."""
    serializer_class = DeviceTargetingSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return DeviceTargeting.objects.filter(rule__smartlink_id=sl_pk)

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        from api.smartlink.models import TargetingRule
        rule, _ = TargetingRule.objects.get_or_create(smartlink_id=sl_pk)
        serializer.save(rule=rule)