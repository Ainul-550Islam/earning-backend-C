# api/cms/serializers_new/SmartLinkReferralRTBSerializer.py
"""
Serializers for SmartLink, Referral, and RTB Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.smartlink import SmartLink, SmartLinkRule, SmartLinkClick
from ..models_new.referral import ReferralCode, ReferralRelationship, ReferralEarning
from ..models_new.rtb import RTBConfig, RTBAdSlot, RTBBidLog

User = get_user_model()


# ── SmartLink ──────────────────────────────────────────────────────────────────

class SmartLinkRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkRule
        fields = [
            'id', 'smartlink', 'offer_id', 'offer_url', 'offer_title',
            'payout_usd', 'target_countries', 'target_devices', 'weight',
        ]
        read_only_fields = ['id']

    def validate_weight(self, value):
        if value < 0:
            raise serializers.ValidationError("weight must be non-negative.")
        return value


class SmartLinkSerializer(serializers.ModelSerializer):
    rules = SmartLinkRuleSerializer(many=True, read_only=True)

    class Meta:
        model = SmartLink
        fields = [
            'uuid', 'name', 'slug', 'description', 'rotation_mode',
            'fallback_url', 'is_active', 'total_clicks', 'rules',
        ]
        read_only_fields = ['uuid', 'total_clicks']


class SmartLinkClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLinkClick
        fields = [
            'uuid', 'smartlink', 'rule_used', 'user', 'ip_address',
            'country_code', 'device_type', 'subid',
        ]
        read_only_fields = ['uuid']


# ── Referral ───────────────────────────────────────────────────────────────────

class ReferralCodeSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = ReferralCode
        fields = [
            'id', 'user', 'user_display', 'code', 'is_active',
            'total_referrals', 'total_bonus_usd', 'total_bonus_coins',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'code', 'total_referrals', 'total_bonus_usd', 'total_bonus_coins']


class ReferralRelationshipSerializer(serializers.ModelSerializer):
    referrer_display = serializers.StringRelatedField(source='referrer', read_only=True)
    referred_display = serializers.StringRelatedField(source='referred', read_only=True)

    class Meta:
        model = ReferralRelationship
        fields = [
            'id', 'referrer', 'referrer_display', 'referred', 'referred_display',
            'referral_code', 'bonus_rate', 'total_bonus_earned_usd',
            'total_bonus_earned_coins', 'is_active', 'joined_at',
        ]
        read_only_fields = ['id', 'joined_at', 'total_bonus_earned_usd', 'total_bonus_earned_coins']


class ReferralEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralEarning
        fields = [
            'uuid', 'referrer', 'referred', 'relationship',
            'source', 'original_amount_usd', 'bonus_rate', 'bonus_usd',
        ]
        read_only_fields = ['uuid', 'bonus_usd']


# ── RTB ────────────────────────────────────────────────────────────────────────

class RTBAdSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RTBAdSlot
        fields = [
            'uuid', 'rtb_config', 'name', 'slot_type', 'page_location',
            'floor_price_usd', 'is_active', 'impressions',
        ]
        read_only_fields = ['uuid', 'impressions']


class RTBConfigSerializer(serializers.ModelSerializer):
    ad_slots = RTBAdSlotSerializer(many=True, read_only=True)

    class Meta:
        model = RTBConfig
        fields = [
            'uuid', 'name', 'publisher_id', 'is_active',
            'floor_price_cpc_usd', 'floor_price_cpa_usd', 'floor_price_cpi_usd',
            'preferred_countries', 'ad_slots',
        ]
        read_only_fields = ['uuid']


class RTBBidLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RTBBidLog
        fields = [
            'uuid', 'ad_slot', 'bid_request_id', 'winning_bid_usd',
            'num_bidders', 'floor_price', 'ad_category', 'user_country',
        ]
        read_only_fields = ['uuid']
