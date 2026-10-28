# api/cms/serializers_new/VirtualCurrencySerializer.py
"""
Serializers for Virtual Currency, Wallet, OfferWall, Locker, Click, and Conversion Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.cpalead import (
    VirtualCurrency, UserVirtualBalance, VirtualTransaction,
    OfferWallConfig, ContentLocker, ClickLog, ConversionLog, OfferCache,
)

User = get_user_model()


class VirtualCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = VirtualCurrency
        fields = [
            'uuid', 'name', 'symbol', 'usd_ratio',
            'min_earn_per_offer', 'max_earn_per_offer', 'daily_earn_cap', 'is_active',
        ]
        read_only_fields = ['uuid']

    def validate_usd_ratio(self, value):
        if value <= 0:
            raise serializers.ValidationError("usd_ratio must be greater than 0.")
        return value


class UserVirtualBalanceSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)
    currency_display = serializers.StringRelatedField(source='currency', read_only=True)

    class Meta:
        model = UserVirtualBalance
        fields = [
            'id', 'user', 'user_display', 'currency', 'currency_display',
            'balance', 'total_earned', 'total_spent',
            'today_earned', 'last_earn_date', 'created_at',
        ]
        read_only_fields = ['id', 'total_earned', 'total_spent', 'today_earned', 'last_earn_date', 'created_at']


class VirtualTransactionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = VirtualTransaction
        fields = [
            'uuid', 'user', 'user_display', 'tx_type', 'amount',
            'balance_before', 'balance_after', 'usd_equivalent', 'description',
        ]
        read_only_fields = ['uuid', 'balance_before', 'balance_after']

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError("Transaction amount cannot be zero.")
        return value


class OfferWallConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferWallConfig
        fields = [
            'uuid', 'name', 'offerwall_title', 'header_title', 'currency',
            'publisher_id', 'website_id', 'custom_css',
        ]
        read_only_fields = ['uuid']
        extra_kwargs = {
            'publisher_id': {'write_only': True},
            'website_id': {'write_only': True},
        }


class ContentLockerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentLocker
        fields = [
            'uuid', 'name', 'locker_type', 'offerwall',
            'title', 'description', 'locked_content', 'preview_content',
        ]
        read_only_fields = ['uuid']


class ClickLogSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = ClickLog
        fields = [
            'uuid', 'click_id', 'user', 'user_display', 'session_key',
            'offer_id', 'campaign_id', 'click_source', 'ip_address',
        ]
        read_only_fields = ['uuid']
        extra_kwargs = {'ip_address': {'write_only': True}}


class ConversionLogSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = ConversionLog
        fields = [
            'uuid', 'subid', 'lead_id', 'payout_usd', 'campaign_id',
            'user', 'user_display', 'virtual_amount_awarded', 'usd_amount_awarded',
        ]
        read_only_fields = ['uuid', 'virtual_amount_awarded', 'usd_amount_awarded']


class OfferCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCache
        fields = [
            'id', 'offer_id', 'offerwall', 'offer_type', 'title',
            'description', 'payout_usd', 'payout_virtual', 'icon_url',
        ]
        read_only_fields = ['id']
