# api/payment_gateways/blacklist/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .models import TrafficBlacklist, OfferQualityScore
from .BlacklistEngine import BlacklistEngine
from rest_framework import serializers


class TrafficBlacklistSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    class Meta:
        model  = TrafficBlacklist
        fields = ['id','block_type','value','reason','is_active','expires_at',
                  'block_count','offer','owner_email','created_at']
        read_only_fields = ['block_count','created_at']

class QualityScoreSerializer(serializers.ModelSerializer):
    publisher_email = serializers.EmailField(source='publisher.email', read_only=True)
    offer_name      = serializers.CharField(source='offer.name', read_only=True)
    class Meta:
        model  = OfferQualityScore
        fields = ['id','publisher_email','offer_name','total_clicks','total_conversions',
                  'conversion_rate','fraud_rate','quality_score','is_blacklisted']


class TrafficBlacklistViewSet(BaseViewSet):
    """Advertiser traffic blacklist management."""
    queryset           = TrafficBlacklist.objects.all().order_by('-created_at')
    serializer_class   = TrafficBlacklistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, created_by_type='advertiser')

    @action(detail=False, methods=['post'])
    def check(self, request):
        """Check if a traffic source would be blocked."""
        engine = BlacklistEngine()
        result = engine.is_blocked(
            offer_id=request.data.get('offer_id'),
            advertiser_id=request.user.id,
            ip=request.data.get('ip',''),
            country=request.data.get('country',''),
            device=request.data.get('device',''),
        )
        return self.success_response(data=result)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def auto_blacklist(self, request):
        """Admin: auto-blacklist low quality publishers."""
        threshold = int(request.data.get('threshold', 20))
        engine    = BlacklistEngine()
        count     = engine.auto_blacklist_low_quality(threshold)
        return self.success_response(
            data={'blacklisted': count},
            message=f'{count} publishers auto-blacklisted (quality < {threshold})'
        )


class OfferQualityViewSet(BaseViewSet):
    """Quality scores for publisher-offer combinations."""
    queryset           = OfferQualityScore.objects.all().order_by('quality_score')
    serializer_class   = QualityScoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        # Advertisers see scores for their offers
        return super().get_queryset().filter(offer__advertiser=self.request.user)
