from rest_framework import serializers
from .SmartLinkSerializer import SmartLinkSerializer
from ..models import SmartLink, TargetingRule, OfferPool, SmartLinkFallback, SmartLinkRotation


class FallbackInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkFallback
        fields = ['id', 'url', 'is_active']


class RotationInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkRotation
        fields = ['method', 'auto_optimize_epc', 'optimization_interval_minutes', 'last_optimized_at']


class SmartLinkDetailSerializer(SmartLinkSerializer):
    """Extended serializer with targeting, pool summary, fallback, and rotation config."""
    has_targeting = serializers.SerializerMethodField()
    has_offer_pool = serializers.SerializerMethodField()
    active_offers_count = serializers.SerializerMethodField()
    fallback = FallbackInlineSerializer(read_only=True)
    rotation_config = RotationInlineSerializer(read_only=True)

    class Meta(SmartLinkSerializer.Meta):
        fields = SmartLinkSerializer.Meta.fields + [
            'has_targeting', 'has_offer_pool',
            'active_offers_count', 'fallback', 'rotation_config',
        ]

    def get_has_targeting(self, obj):
        return hasattr(obj, 'targeting_rule') and obj.targeting_rule is not None

    def get_has_offer_pool(self, obj):
        try:
            return obj.offer_pool is not None
        except Exception:
            return False

    def get_active_offers_count(self, obj):
        try:
            return obj.offer_pool.entries.filter(is_active=True).count()
        except Exception:
            return 0
