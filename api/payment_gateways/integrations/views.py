# api/payment_gateways/integrations/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.views import BaseViewSet
from .models import AdvertiserTrackerIntegration
from rest_framework import serializers


class TrackerIntegrationSerializer(serializers.ModelSerializer):
    postback_template = serializers.SerializerMethodField()
    offer_name        = serializers.CharField(source='offer.name', read_only=True)

    class Meta:
        model  = AdvertiserTrackerIntegration
        fields = ['id','tracker','app_id','offer','offer_name','is_active',
                  'postback_url','postback_template','created_at']
        read_only_fields = ['postback_url','created_at']

    def get_postback_template(self, obj):
        return obj.get_postback_url()


class TrackerIntegrationViewSet(BaseViewSet):
    queryset           = AdvertiserTrackerIntegration.objects.all().order_by('-created_at')
    serializer_class   = TrackerIntegrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(advertiser=self.request.user)

    def perform_create(self, serializer):
        serializer.save(advertiser=self.request.user)

    @action(detail=True, methods=['get'])
    def setup_guide(self, request, pk=None):
        """Get setup instructions for this tracker."""
        integration = self.get_object()
        from .AppsFlyer import AppsFlyerIntegration, ThirdPartyTrackerService
        svc      = ThirdPartyTrackerService()
        postback = svc.get_postback_template(integration.tracker, integration.offer_id)
        return self.success_response(data={
            'tracker':         integration.tracker,
            'postback_url':    postback,
            'app_id':          integration.app_id,
            'instructions':    self._get_instructions(integration.tracker, postback),
        })

    def _get_instructions(self, tracker: str, postback: str) -> list:
        return [
            f'1. Log in to your {tracker.title()} dashboard',
            f'2. Go to App Settings → Integrated Partners → yourdomain',
            f'3. Enter this postback URL: {postback[:80]}...',
            f'4. Map click_id to your tracking parameter',
            f'5. Test with a sandbox install',
            f'6. Go live after verification',
        ]
