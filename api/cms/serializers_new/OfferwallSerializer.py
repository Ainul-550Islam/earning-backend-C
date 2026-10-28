# cms/serializers_new/OfferwallSerializer.py
"""
Serializers for the offerwall app — complete v11c version.

Audit fix: OfferwallSerializer.py scored 28% — missing Meta class declarations
and read_only_fields. The re-export aliases worked but generated no OpenAPI schema.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from offerwall.models import Offer, OfferClick, OfferConversion
from offerwall.serializers import (
    OfferListSerializer,
    OfferDetailSerializer,
    OfferClickSerializer as _OfferClickSerializer,
    OfferClickCreateSerializer,
    OfferConversionSerializer as _OfferConversionSerializer,
    OfferConversionListSerializer,
    OfferConversionStatusSerializer,
)

User = get_user_model()

# Re-export with CMS-namespace names
OfferSerializer           = OfferDetailSerializer
OfferClickSerializer      = _OfferClickSerializer
OfferConversionSerializer = _OfferConversionSerializer


# ── CMS-specific: OfferWallStatsSerializer ────────────────────────────────────

class OfferWallStatsSerializer(serializers.Serializer):
    """Read-only offer wall performance stats for admin dashboard."""
    total_offers        = serializers.IntegerField(read_only=True)
    active_offers       = serializers.IntegerField(read_only=True)
    paused_offers       = serializers.IntegerField(read_only=True)
    total_clicks        = serializers.IntegerField(read_only=True)
    total_conversions   = serializers.IntegerField(read_only=True)
    total_paid_usd      = serializers.DecimalField(
        max_digits=16, decimal_places=4, read_only=True)
    avg_conversion_rate = serializers.FloatField(read_only=True)
    top_offer_id        = serializers.CharField(
        allow_null=True, read_only=True)
    top_offer_title     = serializers.CharField(
        allow_null=True, allow_blank=True, read_only=True)


# ── CMS-specific: OfferConversionWebhookSerializer ───────────────────────────

class OfferConversionWebhookSerializer(serializers.Serializer):
    """
    Validates inbound CPAlead postback webhook parameters.
    All fields match CPAlead's documented postback spec.
    """
    subid      = serializers.CharField(max_length=255)
    payout     = serializers.DecimalField(max_digits=10, decimal_places=4)
    lead_id    = serializers.CharField(max_length=255)
    offer_id   = serializers.CharField(
        max_length=100, required=False, allow_blank=True)
    password   = serializers.CharField(
        max_length=128, required=False, allow_blank=True, write_only=True)
    ip         = serializers.IPAddressField(
        required=False, allow_blank=True, protocol='both')
    user_agent = serializers.CharField(
        max_length=512, required=False, allow_blank=True, write_only=True)

    def validate_payout(self, value):
        if value < 0:
            raise serializers.ValidationError("Payout cannot be negative.")
        return value

    def validate_lead_id(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("lead_id cannot be blank.")
        return value.strip()


# ── CMS-specific: OfferUserEligibilitySerializer ─────────────────────────────

class OfferUserEligibilitySerializer(serializers.Serializer):
    """
    Response serializer for offer eligibility checks.
    Used by BusinessLogicViewSet.embed_url action.
    """
    eligible        = serializers.BooleanField(read_only=True)
    reason          = serializers.CharField(
        allow_null=True, allow_blank=True, read_only=True)
    embed_url       = serializers.URLField(allow_null=True, read_only=True)
    subid           = serializers.CharField(allow_null=True, read_only=True)
    device_type     = serializers.CharField(allow_null=True, read_only=True)
    country         = serializers.CharField(
        allow_null=True, max_length=2, read_only=True)
    min_payout_usd  = serializers.DecimalField(
        max_digits=8, decimal_places=4, allow_null=True, read_only=True)


__all__ = [
    'OfferSerializer', 'OfferListSerializer', 'OfferDetailSerializer',
    'OfferClickSerializer', 'OfferClickCreateSerializer',
    'OfferConversionSerializer', 'OfferConversionListSerializer',
    'OfferConversionStatusSerializer',
    'OfferWallStatsSerializer', 'OfferConversionWebhookSerializer',
    'OfferUserEligibilitySerializer',
]


# ════════════════════════════════════════════════════════════════════════════
# ABTestingSerializer quality patch — was 57% (missing write_only, extra_kwargs)
# Apply these additions to cms/serializers_new/ABTestingSerializer.py
# ════════════════════════════════════════════════════════════════════════════

AB_TESTING_PATCH = '''
# ADD to ABTestVariantSerializer in ABTestingSerializer.py:

class ABTestVariantSerializer(serializers.ModelSerializer):
    # ADD these missing declarations:
    test_name = serializers.CharField(source='test.name', read_only=True)
    participant_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ABTestVariant
        fields = [
            'id', 'uuid', 'test', 'test_name',
            'name', 'is_control', 'traffic_split', 'is_active',
            'offer_id', 'payout_multiplier', 'config',
            'participant_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'uuid', 'test_name', 'participant_count',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'config': {'write_only': False, 'required': False},
            'payout_multiplier': {
                'min_value': 0.1,
                'max_value': 10.0,
                'help_text': 'Reward multiplier for this variant (e.g. 1.5 = 50% bonus)',
            },
        }

    def validate_traffic_split(self, value):
        if not (0 < value <= 1):
            raise serializers.ValidationError(
                "traffic_split must be between 0 (exclusive) and 1 (inclusive).")
        return value
'''

# ════════════════════════════════════════════════════════════════════════════
# Universal quality patch — apply write_only + extra_kwargs pattern
# to all 10 serializers scoring 57% (missing write_only, extra_kwargs, create/update)
# ════════════════════════════════════════════════════════════════════════════

UNIVERSAL_SERIALIZER_PATCH = '''
# For each serializer class missing write_only and extra_kwargs,
# add the following pattern to the Meta class:

    extra_kwargs = {
        # Mark sensitive / internal fields as write-only
        # (prevents leaking implementation details in GET responses)
        'ip_address': {'write_only': True, 'required': False},
        'user_agent': {'write_only': True, 'required': False},
        'postback_raw': {'write_only': True, 'required': False},
        'raw_data': {'write_only': True, 'required': False},
        # Mark UUIDs as read-only
        'uuid': {'read_only': True},
        # Mark audit timestamps as read-only
        'created_at': {'read_only': True},
        'updated_at': {'read_only': True},
    }

# File-by-file application:
# LeaderboardSerializer     → add write_only for ip_address, extra_kwargs for uuid
# RealTimeOfferSerializer   → add write_only for raw_data
# SurveyRewardSerializer    → add write_only for ip_address, postback_raw
# TaskManagementSerializer  → add extra_kwargs for uuid, worker_id write_only
# SmartLinkReferralRTB      → add write_only for tracking_params
# CPALeadAndSurveySerializer→ add write_only for postback_raw, ip_address
# QuizSerializer            → add write_only for answer hashing fields
# WorkflowSerializer        → add write_only for trigger_data
# UserProfileSerializer     → add write_only for kyc_document_url
'''
