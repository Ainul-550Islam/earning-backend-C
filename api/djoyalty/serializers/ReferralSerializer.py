# api/djoyalty/serializers/ReferralSerializer.py
from rest_framework import serializers
from ..models.referral import ReferralLink, ReferralClick, ReferralConversion, ReferralProgram


class ReferralLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralLink
        fields = [
            'id', 'code', 'short_url', 'destination_url',
            'total_clicks', 'unique_clicks', 'total_conversions',
            'total_points_earned', 'total_commission_earned',
            'is_active', 'created_at',
        ]
        read_only_fields = [
            'id', 'total_clicks', 'unique_clicks', 'total_conversions',
            'total_points_earned', 'total_commission_earned', 'created_at',
        ]


class ReferralClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralClick
        fields = [
            'id', 'ip_address', 'country_code', 'device_type',
            'is_unique', 'converted', 'clicked_at',
        ]
        read_only_fields = ['id', 'clicked_at']


class ReferralConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralConversion
        fields = [
            'id', 'conversion_type', 'referrer_points', 'referred_points',
            'commission_amount', 'commission_percent', 'order_value',
            'status', 'level', 'converted_at',
        ]
        read_only_fields = ['id', 'converted_at']


class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralProgram
        fields = [
            'id', 'name', 'description',
            'referrer_signup_points', 'referrer_first_purchase_points',
            'referrer_ongoing_commission_pct', 'referred_welcome_points',
            'max_levels', 'level2_commission_pct', 'level3_commission_pct',
            'max_referrals_per_customer', 'require_first_purchase',
            'is_active', 'valid_from', 'valid_until',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        referrer = data.get('referrer')
        referred = data.get('referred_customer')
        if referrer and referred and referrer == referred:
            from rest_framework import serializers
            raise serializers.ValidationError('Cannot refer yourself.')
        return data
