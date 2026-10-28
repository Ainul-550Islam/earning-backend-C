# offerwall/serializers.py
"""
DRF Serializers for the offerwall app.
Covers: Offer, OfferClick, OfferConversion
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Offer, OfferClick, OfferConversion

User = get_user_model()


# ── Offer ──────────────────────────────────────────────────────────────────────

class OfferListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views — omits analytics and targeting details.
    """
    conversion_rate = serializers.FloatField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id', 'title', 'description', 'source', 'external_id',
            'payout_usd', 'virtual_payout', 'status', 'is_featured',
            'target_device', 'image_url', 'click_url',
            'conversion_rate', 'is_active',
            'created_at', 'expires_at',
        ]
        read_only_fields = [
            'id', 'conversion_rate', 'is_active', 'created_at',
        ]


class OfferDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create/update and detail views.
    Includes analytics and targeting fields.
    """
    conversion_rate = serializers.FloatField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id', 'title', 'description', 'source', 'external_id',
            'payout_usd', 'virtual_payout', 'revenue_share',
            'status', 'is_featured',
            'target_device', 'target_countries', 'min_user_level',
            'image_url', 'click_url',
            'total_clicks', 'total_conversions', 'total_paid_usd',
            'conversion_rate', 'is_active',
            'created_at', 'updated_at', 'expires_at',
        ]
        read_only_fields = [
            'id', 'total_clicks', 'total_conversions', 'total_paid_usd',
            'conversion_rate', 'is_active', 'created_at', 'updated_at',
        ]

    def validate_revenue_share(self, value):
        if not (0 <= value <= 1):
            raise serializers.ValidationError(
                "revenue_share must be between 0.0 and 1.0."
            )
        return value

    def validate_target_countries(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of ISO-2 country codes.")
        for code in value:
            if not isinstance(code, str) or len(code) != 2:
                raise serializers.ValidationError(
                    f"'{code}' is not a valid ISO-2 country code."
                )
        return [c.upper() for c in value]


# ── OfferClick ────────────────────────────────────────────────────────────────

class OfferClickSerializer(serializers.ModelSerializer):
    """
    Serializer for OfferClick — used when recording / listing clicks.
    """
    user_display = serializers.StringRelatedField(source='user', read_only=True)
    offer_title  = serializers.CharField(source='offer.title', read_only=True)

    class Meta:
        model = OfferClick
        fields = [
            'id', 'offer', 'offer_title', 'user', 'user_display',
            'ip_address', 'user_agent', 'country', 'device_type',
            'subid', 'clicked_at',
        ]
        read_only_fields = [
            'id', 'user_display', 'offer_title', 'clicked_at',
        ]
        extra_kwargs = {
            'ip_address': {'write_only': True},
            'user_agent': {'write_only': True},
        }


class OfferClickCreateSerializer(serializers.ModelSerializer):
    """Minimal serializer for creating a click record from a postback / view."""
    class Meta:
        model = OfferClick
        fields = [
            'offer', 'user', 'ip_address', 'user_agent',
            'country', 'device_type', 'subid',
        ]


# ── OfferConversion ───────────────────────────────────────────────────────────

class OfferConversionSerializer(serializers.ModelSerializer):
    """
    Full conversion serializer — used in admin, API detail views,
    and postback processing responses.
    """
    user_display  = serializers.StringRelatedField(source='user', read_only=True)
    offer_title   = serializers.CharField(source='offer.title', read_only=True)

    class Meta:
        model = OfferConversion
        fields = [
            'id', 'offer', 'offer_title', 'click', 'user', 'user_display',
            'lead_id', 'payout_usd', 'virtual_awarded',
            'status', 'fraud_score', 'fraud_reasons',
            'ip_address', 'postback_raw',
            'approved_at', 'rejected_at', 'converted_at',
        ]
        read_only_fields = [
            'id', 'user_display', 'offer_title',
            'approved_at', 'rejected_at', 'converted_at',
        ]
        extra_kwargs = {
            'postback_raw': {'write_only': True},
            'ip_address':   {'write_only': True},
        }

    def validate_fraud_score(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("fraud_score must be 0–100.")
        return value


class OfferConversionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    offer_title = serializers.CharField(source='offer.title', read_only=True)

    class Meta:
        model = OfferConversion
        fields = [
            'id', 'offer', 'offer_title', 'lead_id',
            'payout_usd', 'virtual_awarded', 'status',
            'fraud_score', 'converted_at',
        ]
        read_only_fields = ['id', 'offer_title', 'converted_at']


class OfferConversionStatusSerializer(serializers.Serializer):
    """
    Used for approve / reject actions on a conversion.
    """
    status = serializers.ChoiceField(
        choices=[
            (OfferConversion.STATUS_APPROVED, 'Approved'),
            (OfferConversion.STATUS_REJECTED, 'Rejected'),
        ]
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=255,
        help_text='Optional reason (required when rejecting)',
    )

    def validate(self, data):
        if data['status'] == OfferConversion.STATUS_REJECTED and not data.get('reason'):
            raise serializers.ValidationError(
                {'reason': 'A reason is required when rejecting a conversion.'}
            )
        return data
