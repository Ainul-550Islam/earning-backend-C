# api/djoyalty/serializers/TierSerializer.py
from rest_framework import serializers
from ..models.tiers import LoyaltyTier, UserTier, TierBenefit

class TierBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = TierBenefit
        fields = ['id', 'title', 'description', 'benefit_type', 'value', 'is_active']

class LoyaltyTierSerializer(serializers.ModelSerializer):
    benefits = TierBenefitSerializer(many=True, read_only=True)
    class Meta:
        model = LoyaltyTier
        fields = ['id', 'name', 'label', 'min_points', 'max_points', 'earn_multiplier', 'color', 'icon', 'description', 'is_active', 'rank', 'benefits']

class UserTierSerializer(serializers.ModelSerializer):
    tier_name = serializers.SerializerMethodField()
    tier_label = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    class Meta:
        model = UserTier
        fields = ['id', 'customer', 'customer_name', 'tier', 'tier_name', 'tier_label', 'is_current', 'assigned_at', 'valid_until', 'points_at_assignment']
    def get_tier_name(self, obj): return obj.tier.name if obj.tier else ''
    def get_tier_label(self, obj): return obj.tier.label if obj.tier else ''
    def get_customer_name(self, obj): return str(obj.customer) if obj.customer else ''
