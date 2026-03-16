# api/ad_networks/views_extra.py
# NetworkStatisticViewSet, KnownBadIPViewSet, SmartOfferRecommendationViewSet

from rest_framework import viewsets, serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from .models import NetworkStatistic, KnownBadIP, SmartOfferRecommendation


# ── Serializers ──────────────────────────────────────────────────

class NetworkStatisticSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = NetworkStatistic
        fields = ['id', 'ad_network', 'date', 'clicks', 'conversions',
                  'payout', 'commission']


class KnownBadIPSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = KnownBadIP
        fields = ['id', 'ip_address', 'threat_type', 'source',
                  'confidence_score', 'expires_at', 'is_active',
                  'description', 'first_seen', 'last_seen']
        extra_kwargs = {
            'expires_at':   {'required': False},
            'description':  {'required': False},
        }


class SmartOfferRecommendationSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model  = SmartOfferRecommendation
        fields = ['id', 'user', 'offer', 'score', 'reason',
                  'is_displayed', 'is_clicked', 'is_converted',
                  'category_preference']
        extra_kwargs = {
            'reason':               {'required': False},
            'category_preference':  {'required': False},
        }


# ── ViewSets ─────────────────────────────────────────────────────

class NetworkStatisticViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only daily statistics per ad network"""
    permission_classes = [IsAuthenticated]
    serializer_class   = NetworkStatisticSerializer

    def get_queryset(self):
        qs = NetworkStatistic.objects.select_related('ad_network').order_by('-date')
        params = self.request.query_params

        ad_network = params.get('ad_network')
        if ad_network:
            qs = qs.filter(ad_network_id=ad_network)

        date = params.get('date')
        if date:
            qs = qs.filter(date=date)

        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs


class KnownBadIPViewSet(viewsets.ModelViewSet):
    """CRUD for known bad IPs"""
    permission_classes = [IsAuthenticated]
    serializer_class   = KnownBadIPSerializer

    def get_queryset(self):
        qs = KnownBadIP.objects.order_by('-first_seen')
        params = self.request.query_params

        threat_type = params.get('threat_type')
        if threat_type:
            qs = qs.filter(threat_type=threat_type)

        source = params.get('source')
        if source:
            qs = qs.filter(source=source)

        is_active = params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')

        return qs


class SmartOfferRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only offer recommendations"""
    permission_classes = [IsAuthenticated]
    serializer_class   = SmartOfferRecommendationSerializer

    def get_queryset(self):
        qs = SmartOfferRecommendation.objects.select_related('user', 'offer').order_by('-score')
        params = self.request.query_params

        user = params.get('user')
        if user:
            qs = qs.filter(user_id=user)

        offer = params.get('offer')
        if offer:
            qs = qs.filter(offer_id=offer)

        is_displayed = params.get('is_displayed')
        if is_displayed is not None:
            qs = qs.filter(is_displayed=is_displayed.lower() == 'true')

        is_converted = params.get('is_converted')
        if is_converted is not None:
            qs = qs.filter(is_converted=is_converted.lower() == 'true')

        return qs