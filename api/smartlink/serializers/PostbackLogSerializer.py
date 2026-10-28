from rest_framework import serializers
from api.smartlink.models.postback_log import PostbackLog


class PostbackLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for PostbackLog records.
    Used in admin views and publisher dispute resolution.
    All postback records are immutable — no write operations.
    """

    class Meta:
        model = PostbackLog
        fields = [
            'id',
            'click_id',
            'offer_id',
            'event',
            'payout',
            'currency',
            'transaction_id',
            'sub1',
            'adv_sub1',
            'ip',
            'is_duplicate',
            'is_attributed',
            'raw_params',
            'created_at',
        ]
        read_only_fields = fields


class PostbackLogCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer used internally by the postback receiver endpoint.
    Validates and records incoming S2S postback payloads.
    External callers should POST to /postback/v1/ — not this serializer directly.
    """

    class Meta:
        model = PostbackLog
        fields = [
            'click_id',
            'offer_id',
            'event',
            'payout',
            'currency',
            'transaction_id',
            'sub1',
            'adv_sub1',
            'ip',
            'raw_params',
        ]

    def validate_payout(self, value):
        if value < 0:
            raise serializers.ValidationError('Payout must be non-negative.')
        return value

    def validate_event(self, value):
        allowed = {'lead', 'sale', 'install', 'registration', 'deposit', 'custom'}
        if value not in allowed:
            raise serializers.ValidationError(
                f"Event '{value}' is not recognised. Allowed: {', '.join(sorted(allowed))}"
            )
        return value

    def validate_currency(self, value):
        if len(value) != 3:
            raise serializers.ValidationError('Currency must be a 3-letter ISO 4217 code.')
        return value.upper()
