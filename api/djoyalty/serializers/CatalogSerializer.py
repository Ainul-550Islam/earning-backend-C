# api/djoyalty/serializers/CatalogSerializer.py
from rest_framework import serializers
from ..models.catalog import (
    RewardCatalogCategory, RewardCatalogItem,
    SmartLink, WebhookSubscription, WebhookDeliveryLog, DigitalWalletCard,
)


class RewardCatalogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardCatalogCategory
        fields = ['id', 'name', 'icon', 'sort_order', 'is_active', 'parent']
        read_only_fields = ['id']


class RewardCatalogItemSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = RewardCatalogItem
        fields = [
            'id', 'name', 'description', 'short_description',
            'reward_type', 'points_cost', 'cash_value', 'currency',
            'stock_quantity', 'redeemed_count', 'max_per_customer',
            'image_url', 'gallery', 'is_active', 'is_featured',
            'valid_from', 'valid_until', 'sort_order', 'terms',
            'supplier_name', 'fulfillment_type',
            'category', 'category_name', 'is_available',
        ]
        read_only_fields = ['id', 'redeemed_count', 'is_available']

    def get_is_available(self, obj):
        return obj.is_available()


class SmartLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartLink
        fields = [
            'id', 'slug', 'name', 'description', 'default_url',
            'geo_rules', 'device_rules', 'total_clicks', 'unique_clicks',
            'total_conversions', 'is_active', 'valid_until', 'created_at',
        ]
        read_only_fields = ['id', 'total_clicks', 'unique_clicks', 'total_conversions', 'created_at']


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = WebhookSubscription
        fields = [
            'id', 'name', 'url', 'subscribed_events', 'is_active', 'is_verified',
            'total_deliveries', 'successful_deliveries', 'failed_deliveries',
            'last_delivery_at', 'max_retries', 'api_version', 'success_rate',
        ]
        read_only_fields = ['id', 'total_deliveries', 'successful_deliveries',
                            'failed_deliveries', 'last_delivery_at', 'success_rate']
        extra_kwargs = {'secret': {'write_only': True}}

    def get_success_rate(self, obj):
        return obj.success_rate()


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id', 'event_type', 'attempt_number', 'http_status',
            'duration_ms', 'success', 'error_message', 'delivered_at',
        ]
        read_only_fields = ['id', 'delivered_at']


class DigitalWalletCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = DigitalWalletCard
        fields = [
            'id', 'wallet_type', 'card_number', 'barcode_value', 'barcode_type',
            'program_name', 'card_title', 'background_color', 'text_color',
            'logo_url', 'pkpass_url', 'google_pass_url', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
