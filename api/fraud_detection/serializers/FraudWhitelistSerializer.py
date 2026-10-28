# =============================================================================
# fraud_detection/serializers/FraudWhitelistSerializer.py
# =============================================================================
from __future__ import annotations

from rest_framework import serializers

from api.fraud_detection.models import FraudWhitelist
from api.fraud_detection.choices import EntityType


class FraudWhitelistSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model  = FraudWhitelist
        fields = [
            'id', 'whitelist_id', 'entity_type', 'entity_value', 'reason',
            'is_active', 'whitelisted_by', 'expires_at', 'is_expired',
            'integrity_hash', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'whitelist_id', 'integrity_hash', 'created_at', 'updated_at']


class FraudWhitelistListSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model  = FraudWhitelist
        fields = ['id', 'whitelist_id', 'entity_type', 'entity_value', 'is_active', 'is_expired', 'expires_at']


class FraudWhitelistCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudWhitelist
        fields = ['entity_type', 'entity_value', 'reason', 'expires_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['whitelisted_by'] = request.user
        return FraudWhitelist.objects.create(**validated_data)


class FraudWhitelistUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudWhitelist
        fields = ['reason', 'expires_at', 'is_active']


class FraudWhitelistDeactivateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class FraudWhitelistBulkCreateSerializer(serializers.Serializer):
    entries = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=100,
    )


class FraudWhitelistBulkUpdateSerializer(serializers.Serializer):
    ids        = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    is_active  = serializers.BooleanField(required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class FraudWhitelistBulkDeactivateSerializer(serializers.Serializer):
    ids    = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    reason = serializers.CharField(required=False, allow_blank=True)


class FraudWhitelistStatisticsSerializer(serializers.Serializer):
    total        = serializers.IntegerField()
    active       = serializers.IntegerField()
    expired      = serializers.IntegerField()
    by_type      = serializers.DictField(child=serializers.IntegerField())


class FraudWhitelistSearchSerializer(serializers.Serializer):
    q           = serializers.CharField(required=True, min_length=1)
    entity_type = serializers.ChoiceField(choices=EntityType.choices, required=False)
    is_active   = serializers.BooleanField(required=False)
