# api/referral/serializers.py
"""
DRF serializers for api.referral. Ensures data can be sent via API.
"""
from rest_framework import serializers


try:
    from .models import Referral, ReferralEarning, ReferralSettings
except ImportError:
    Referral = ReferralEarning = ReferralSettings = None


if Referral is not None:
    class ReferralSerializer(serializers.ModelSerializer):
        class Meta:
            model = Referral
            fields = [
                'id', 'referrer', 'referred_user', 'signup_bonus_given',
                'total_commission_earned', 'created_at',
            ]
            read_only_fields = ['created_at']


if ReferralEarning is not None:
    class ReferralEarningSerializer(serializers.ModelSerializer):
        class Meta:
            model = ReferralEarning
            fields = [
                'id', 'referral', 'referrer', 'referred_user', 'amount',
                'commission_rate', 'source_task', 'created_at',
            ]
            read_only_fields = ['created_at']


if ReferralSettings is not None:
    class ReferralSettingsSerializer(serializers.ModelSerializer):
        class Meta:
            model = ReferralSettings
            fields = [
                'id', 'direct_signup_bonus', 'referrer_signup_bonus',
                'lifetime_commission_rate', 'is_active',
            ]
