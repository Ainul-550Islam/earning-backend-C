# api/djoyalty/serializers/UserTierSerializer.py
"""
UserTier serializer — Customer এর current ও historical tier data।
TierSerializer.py তে UserTierSerializer আছে কিন্তু world plan এ এটা
আলাদা ফাইল হিসেবে আছে। এখানে extended version রাখা হয়েছে।
"""
from rest_framework import serializers
from ..models.tiers import UserTier, TierHistory, TierBenefit, LoyaltyTier
from ..utils import get_next_tier, get_points_needed_for_next_tier
from ..constants import TIER_THRESHOLDS
from decimal import Decimal


class TierBenefitInlineSerializer(serializers.ModelSerializer):
    """Tier benefit compact view।"""

    class Meta:
        model = TierBenefit
        fields = ['id', 'title', 'description', 'benefit_type', 'value', 'is_active']


class LoyaltyTierCompactSerializer(serializers.ModelSerializer):
    """Compact tier info — nested use এর জন্য।"""
    benefits = TierBenefitInlineSerializer(many=True, read_only=True, source='benefits')

    class Meta:
        model = LoyaltyTier
        fields = ['id', 'name', 'label', 'icon', 'color', 'rank', 'earn_multiplier', 'min_points', 'benefits']


class UserTierSerializer(serializers.ModelSerializer):
    """
    Customer এর current/historical tier।
    Progress information সহ।
    """
    tier_detail = LoyaltyTierCompactSerializer(source='tier', read_only=True)
    customer_code = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    tier_name = serializers.SerializerMethodField()
    tier_label = serializers.SerializerMethodField()
    tier_icon = serializers.SerializerMethodField()
    tier_color = serializers.SerializerMethodField()
    tier_rank = serializers.SerializerMethodField()
    next_tier = serializers.SerializerMethodField()
    upgrade_progress = serializers.SerializerMethodField()
    points_needed_for_upgrade = serializers.SerializerMethodField()
    benefits = serializers.SerializerMethodField()
    days_in_tier = serializers.SerializerMethodField()

    class Meta:
        model = UserTier
        fields = [
            'id',
            'customer',
            'customer_code',
            'customer_name',
            'tier',
            'tier_detail',
            'tier_name',
            'tier_label',
            'tier_icon',
            'tier_color',
            'tier_rank',
            'is_current',
            'assigned_at',
            'valid_until',
            'points_at_assignment',
            'next_tier',
            'upgrade_progress',
            'points_needed_for_upgrade',
            'benefits',
            'days_in_tier',
        ]
        read_only_fields = ['assigned_at']

    def get_customer_code(self, obj):
        return obj.customer.code if obj.customer else ''

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else ''

    def get_tier_name(self, obj):
        return obj.tier.name if obj.tier else ''

    def get_tier_label(self, obj):
        return obj.tier.label if obj.tier else ''

    def get_tier_icon(self, obj):
        return obj.tier.icon if obj.tier else '⭐'

    def get_tier_color(self, obj):
        return obj.tier.color if obj.tier else '#888888'

    def get_tier_rank(self, obj):
        return obj.tier.rank if obj.tier else 0

    def get_next_tier(self, obj):
        """পরবর্তী tier এর নাম।"""
        if not obj.tier:
            return None
        next_name = get_next_tier(obj.tier.name)
        if not next_name:
            return None
        try:
            next_tier_obj = LoyaltyTier.objects.filter(name=next_name).first()
            if next_tier_obj:
                return {
                    'name': next_tier_obj.name,
                    'label': next_tier_obj.label,
                    'icon': next_tier_obj.icon,
                    'min_points': str(next_tier_obj.min_points),
                }
        except Exception:
            pass
        return {'name': next_name, 'label': next_name.title(), 'icon': '⭐', 'min_points': '0'}

    def get_upgrade_progress(self, obj):
        """Upgrade progress percentage (0–100)।"""
        if not obj.tier or not obj.customer:
            return 0.0
        try:
            lp = obj.customer.loyalty_points.first()
            if not lp:
                return 0.0
            lifetime = lp.lifetime_earned
            current_tier_name = obj.tier.name
            next_tier_name = get_next_tier(current_tier_name)
            if not next_tier_name:
                return 100.0  # Diamond — max tier
            current_threshold = TIER_THRESHOLDS.get(current_tier_name, Decimal('0'))
            next_threshold = TIER_THRESHOLDS.get(next_tier_name, Decimal('0'))
            tier_range = next_threshold - current_threshold
            if tier_range <= 0:
                return 100.0
            progress_in_tier = lifetime - current_threshold
            pct = float(min(progress_in_tier / tier_range * 100, 100))
            return round(max(pct, 0.0), 1)
        except Exception:
            return 0.0

    def get_points_needed_for_upgrade(self, obj):
        """Next tier এর জন্য কত পয়েন্ট বাকি।"""
        if not obj.tier or not obj.customer:
            return None
        try:
            lp = obj.customer.loyalty_points.first()
            if not lp:
                return None
            needed = get_points_needed_for_next_tier(lp.lifetime_earned, obj.tier.name)
            return str(needed) if needed is not None else None
        except Exception:
            return None

    def get_benefits(self, obj):
        """Current tier এর active benefits।"""
        if not obj.tier:
            return []
        benefits = TierBenefit.objects.filter(tier=obj.tier, is_active=True)
        return TierBenefitInlineSerializer(benefits, many=True).data

    def get_days_in_tier(self, obj):
        """এই tier এ কত দিন আছে।"""
        from django.utils import timezone
        if not obj.assigned_at:
            return 0
        delta = timezone.now() - obj.assigned_at
        return delta.days


class UserTierHistorySerializer(serializers.ModelSerializer):
    """Tier change history।"""
    from_tier_name = serializers.SerializerMethodField()
    to_tier_name = serializers.SerializerMethodField()
    from_tier_icon = serializers.SerializerMethodField()
    to_tier_icon = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()
    change_label = serializers.SerializerMethodField()

    class Meta:
        model = TierHistory
        fields = [
            'id', 'customer', 'customer_code',
            'from_tier', 'from_tier_name', 'from_tier_icon',
            'to_tier', 'to_tier_name', 'to_tier_icon',
            'change_type', 'change_label',
            'reason', 'points_at_change', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_from_tier_name(self, obj):
        return obj.from_tier.name if obj.from_tier else 'none'

    def get_to_tier_name(self, obj):
        return obj.to_tier.name if obj.to_tier else ''

    def get_from_tier_icon(self, obj):
        return obj.from_tier.icon if obj.from_tier else '—'

    def get_to_tier_icon(self, obj):
        return obj.to_tier.icon if obj.to_tier else '⭐'

    def get_customer_code(self, obj):
        return obj.customer.code if obj.customer else ''

    def get_change_label(self, obj):
        labels = {
            'upgrade': '⬆️ Upgraded',
            'downgrade': '⬇️ Downgraded',
            'initial': '🎉 Initial Assignment',
        }
        return labels.get(obj.change_type, obj.change_type)


class MyTierSerializer(serializers.Serializer):
    """
    'My tier' — Customer facing, single-view summary।
    /api/djoyalty/user-tiers/my_tier/ endpoint এর জন্য।
    """
    current_tier = serializers.CharField(read_only=True)
    tier_label = serializers.CharField(read_only=True)
    tier_icon = serializers.CharField(read_only=True)
    tier_color = serializers.CharField(read_only=True)
    tier_rank = serializers.IntegerField(read_only=True)
    earn_multiplier = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    points_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    lifetime_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    next_tier = serializers.CharField(allow_null=True, read_only=True)
    points_needed = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, read_only=True)
    upgrade_progress_pct = serializers.FloatField(read_only=True)
    assigned_at = serializers.DateTimeField(read_only=True)
    days_in_tier = serializers.IntegerField(read_only=True)
    benefits = TierBenefitInlineSerializer(many=True, read_only=True)
    tier_history = UserTierHistorySerializer(many=True, read_only=True)
