# api/djoyalty/serializers/UserTierSerializer.py
from rest_framework import serializers
from ..models.tiers import UserTier, TierHistory, TierBenefit


class TierBenefitInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = TierBenefit
        fields = ['id', 'title', 'description', 'benefit_type', 'value']


class UserTierSerializer(serializers.ModelSerializer):
    tier_name = serializers.SerializerMethodField()
    tier_label = serializers.SerializerMethodField()
    tier_color = serializers.SerializerMethodField()
    tier_icon = serializers.SerializerMethodField()
    tier_rank = serializers.SerializerMethodField()
    earn_multiplier = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    days_in_tier = serializers.SerializerMethodField()

    class Meta:
        model = UserTier
        fields = [
            'id', 'customer', 'customer_code',
            'tier', 'tier_name', 'tier_label', 'tier_color', 'tier_icon',
            'tier_rank', 'earn_multiplier',
            'is_current', 'points_at_assignment',
            'assigned_at', 'achieved_at', 'expires_at',
            'benefits', 'days_in_tier',
            'created_at',
        ]
        read_only_fields = [
            'id', 'customer_code', 'tier_name', 'tier_label', 'tier_color',
            'tier_icon', 'tier_rank', 'earn_multiplier', 'benefits', 'days_in_tier', 'created_at',
        ]

    def get_tier_name(self, obj) -> str:
        return obj.tier.name if obj.tier else ''

    def get_tier_label(self, obj) -> str:
        return obj.tier.label if obj.tier else ''

    def get_tier_color(self, obj) -> str:
        return obj.tier.color if obj.tier else '#888888'

    def get_tier_icon(self, obj) -> str:
        return obj.tier.icon if obj.tier else '⭐'

    def get_tier_rank(self, obj) -> int:
        return obj.tier.rank if obj.tier else 1

    def get_earn_multiplier(self, obj) -> str:
        return str(obj.tier.earn_multiplier) if obj.tier else '1.00'

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_benefits(self, obj) -> list:
        if not obj.tier:
            return []
        benefits = TierBenefit.objects.filter(tier=obj.tier, is_active=True)
        return TierBenefitInlineSerializer(benefits, many=True).data

    def get_days_in_tier(self, obj) -> int:
        if not obj.assigned_at:
            return 0
        from django.utils import timezone
        return (timezone.now() - obj.assigned_at).days


class UserTierHistorySerializer(serializers.ModelSerializer):
    from_tier_name = serializers.SerializerMethodField()
    to_tier_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = TierHistory
        fields = [
            'id', 'customer', 'customer_code',
            'from_tier', 'from_tier_name',
            'to_tier', 'to_tier_name',
            'change_type', 'reason', 'points_at_change',
            'changed_at', 'changed_by', 'created_at',
        ]
        read_only_fields = ['id', 'from_tier_name', 'to_tier_name', 'customer_code', 'created_at']

    def get_from_tier_name(self, obj) -> str | None:
        return obj.from_tier.name if obj.from_tier else None

    def get_to_tier_name(self, obj) -> str:
        return obj.to_tier.name if obj.to_tier else ''

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class MyTierSerializer(serializers.Serializer):
    """Read-only summary for /my_tier/ endpoint।"""
    current_tier = serializers.CharField()
    tier_label = serializers.CharField()
    tier_icon = serializers.CharField()
    tier_color = serializers.CharField()
    tier_rank = serializers.IntegerField()
    earn_multiplier = serializers.CharField()
    points_balance = serializers.CharField()
    lifetime_earned = serializers.CharField()
    next_tier = serializers.CharField(allow_null=True)
    points_needed = serializers.CharField(allow_null=True)
    upgrade_progress_pct = serializers.FloatField()
    assigned_at = serializers.CharField(allow_null=True)
    days_in_tier = serializers.IntegerField()
    benefits = TierBenefitInlineSerializer(many=True)
    tier_history = UserTierHistorySerializer(many=True)
