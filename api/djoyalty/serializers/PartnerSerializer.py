# api/djoyalty/serializers/PartnerSerializer.py
from rest_framework import serializers
from ..models.campaigns import PartnerMerchant
from ..models.advanced import CoalitionEarn


class PartnerMerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerMerchant
        fields = [
            'id', 'name', 'description', 'category', 'logo', 'website',
            'earn_rate', 'burn_rate',
            'is_active', 'last_sync_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_sync_at', 'created_at', 'updated_at']


class PartnerMerchantAdminSerializer(PartnerMerchantSerializer):
    """Admin view includes API key।"""
    class Meta(PartnerMerchantSerializer.Meta):
        fields = PartnerMerchantSerializer.Meta.fields + ['api_key', 'webhook_url']


class CoalitionEarnSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    partner_name = serializers.SerializerMethodField()

    class Meta:
        model = CoalitionEarn
        fields = [
            'id', 'customer', 'customer_code',
            'partner', 'partner_name',
            'spend_amount', 'points_earned',
            'earn_rate_applied', 'reference',
            'currency', 'status', 'description',
            'created_at', 'processed_at',
        ]
        read_only_fields = ['id', 'customer_code', 'partner_name', 'created_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_partner_name(self, obj) -> str:
        return obj.partner.name if obj.partner else ''

    def validate_earn_multiplier(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Earn multiplier must be positive.')
        return value
