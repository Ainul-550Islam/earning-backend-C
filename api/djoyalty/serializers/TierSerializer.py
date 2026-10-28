# api/djoyalty/serializers/TierSerializer.py
from rest_framework import serializers
from ..models.tiers import LoyaltyTier, TierBenefit, TierConfig


class TierBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = TierBenefit
        fields = ['id', 'title', 'description', 'benefit_type', 'value', 'is_active', 'sort_order']
        read_only_fields = ['id']


class LoyaltyTierSerializer(serializers.ModelSerializer):
    benefits = TierBenefitSerializer(many=True, read_only=True)
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyTier
        fields = [
            'id', 'name', 'label', 'description',
            'min_points', 'max_points', 'earn_multiplier',
            'rank', 'color', 'icon', 'sort_order',
            'is_active', 'perks_summary',
            'benefits', 'customer_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_count', 'created_at', 'updated_at']

    def get_customer_count(self, obj) -> int:
        return obj.user_assignments.filter(is_current=True).count()

    def validate_min_points(self, value):
        from decimal import Decimal
        if Decimal(str(value)) < 0:
            raise serializers.ValidationError('Minimum points cannot be negative.')
        return value

    def validate_earn_multiplier(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Earn multiplier must be greater than 0.')
        if Decimal(str(value)) > Decimal('50'):
            raise serializers.ValidationError('Earn multiplier cannot exceed 50x.')
        return value

    def validate(self, data):
        min_pts = data.get('min_points')
        max_pts = data.get('max_points')
        if min_pts is not None and max_pts is not None:
            from decimal import Decimal
            if Decimal(str(max_pts)) <= Decimal(str(min_pts)):
                raise serializers.ValidationError(
                    'max_points must be greater than min_points.'
                )
        return data


class TierConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TierConfig
        fields = [
            'id', 'tenant', 'evaluation_period',
            'downgrade_grace_days', 'downgrade_protection_months',
            'freeze_enabled', 'auto_upgrade', 'auto_downgrade',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
