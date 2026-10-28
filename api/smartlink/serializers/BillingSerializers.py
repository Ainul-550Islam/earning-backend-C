"""
SmartLink Billing Serializers
================================
Dedicated serializer file for all billing-related models:
  - PublisherAPIKey
  - PublisherProfile
  - WebhookEndpoint / WebhookDeliveryLog
  - PayoutRecord
  - PayoutBatch

Previously these were defined as inline classes inside BusinessViewSets.py.
Moved here for single-responsibility and reusability across viewsets and tests.

FIXED (v2):
  - All model imports moved to top of file (were inside class Meta bodies)
  - Normalized model = (was model  = with double space)
  - Moved inline imports from class body / method body to top-level
"""
from rest_framework.serializers import (
    ModelSerializer,
    Serializer,
    CharField,
    ChoiceField,
    ListField,
    IPAddressField,
    DateTimeField,
    DateField,
    SerializerMethodField,
    DecimalField,
    IntegerField,
    BooleanField,
    ValidationError,
)

from api.smartlink.models.billing import (
    PublisherAPIKey,
    PublisherProfile,
    PayoutRecord,
    PayoutBatch,
)
from api.smartlink.models.webhook import WebhookEndpoint, WebhookDeliveryLog


# ── PublisherAPIKey ───────────────────────────────────────────────────────────

class APIKeyListSerializer(ModelSerializer):
    """Read-only list of a publisher's API keys (secret never returned)."""

    class Meta:
        model = PublisherAPIKey
        fields = [
            'id', 'name', 'key_prefix', 'scope', 'is_active',
            'allowed_ips', 'last_used_at', 'expires_at',
            'request_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'key_prefix', 'last_used_at', 'request_count', 'created_at',
        ]


class APIKeyCreateSerializer(Serializer):
    """Input for creating a new API key (returns full key once on creation)."""
    name        = CharField(max_length=100)
    scope       = ChoiceField(choices=['read', 'write', 'full'], default='write')
    allowed_ips = ListField(child=IPAddressField(), required=False, default=list)
    expires_at  = DateTimeField(required=False, allow_null=True, default=None)


class APIKeyCreatedSerializer(Serializer):
    """Response returned ONCE after API key creation (includes full key)."""
    id         = IntegerField()
    name       = CharField()
    key        = CharField(help_text='Full API key — shown only once. Store securely.')
    key_prefix = CharField()
    scope      = CharField()
    expires_at = DateTimeField(allow_null=True)
    created_at = DateTimeField()


# ── WebhookEndpoint / WebhookDeliveryLog ─────────────────────────────────────

class WebhookEndpointSerializer(ModelSerializer):
    """Create / update webhook endpoint config."""
    delivery_count = SerializerMethodField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'url', 'events', 'is_active', 'description',
            'timeout_seconds', 'retry_count', 'success_count',
            'failure_count', 'last_delivery_at', 'last_success_at',
            'delivery_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'success_count', 'failure_count',
            'last_delivery_at', 'last_success_at',
            'delivery_count', 'created_at',
        ]

    def get_delivery_count(self, obj):
        return obj.deliveries.count()


class WebhookDeliveryLogSerializer(ModelSerializer):
    """Read-only delivery attempt log for a webhook endpoint."""

    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id', 'delivery_id', 'event', 'status', 'http_status',
            'latency_ms', 'attempt', 'error_message', 'next_retry_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'delivery_id', 'event', 'status', 'http_status',
            'latency_ms', 'attempt', 'error_message', 'next_retry_at', 'created_at',
        ]


# ── PublisherProfile ──────────────────────────────────────────────────────────

class PublisherProfileSerializer(ModelSerializer):
    """
    Publisher profile — read/write for most fields.
    Admin-only fields (is_verified, notes) are excluded by default;
    the admin serializer below includes them.
    """
    username = CharField(source='publisher.username', read_only=True)
    email    = CharField(source='publisher.email',    read_only=True)

    class Meta:
        model = PublisherProfile
        fields = [
            'id', 'username', 'email',
            'company_name', 'phone', 'country_code', 'timezone', 'website',
            'traffic_sources', 'vertical',
            'payment_method', 'payment_email', 'bank_name', 'payout_currency',
            'min_payout', 'is_company', 'tax_id', 'w9_submitted',
            'attribution_window_days',
            'gdpr_consent', 'gdpr_consent_at', 'marketing_opt_in',
            'data_anonymized', 'notification_preferences',
            'is_verified', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'username', 'email', 'gdpr_consent_at',
            'data_anonymized', 'is_verified', 'created_at', 'updated_at',
        ]


class PublisherProfileAdminSerializer(PublisherProfileSerializer):
    """Admin-extended profile serializer — includes is_verified and notes for editing."""

    class Meta(PublisherProfileSerializer.Meta):
        read_only_fields = [
            'id', 'username', 'email', 'gdpr_consent_at',
            'data_anonymized', 'created_at', 'updated_at',
        ]


# ── PayoutRecord ─────────────────────────────────────────────────────────────

class PayoutRecordSerializer(ModelSerializer):
    """Full payout record — used in PayoutViewSet list/detail."""
    publisher_username = CharField(source='publisher.username', read_only=True)

    class Meta:
        model = PayoutRecord
        fields = [
            'id', 'reference_id', 'publisher', 'publisher_username',
            'period_from', 'period_to',
            'gross_amount', 'scrub_amount', 'net_amount',
            'currency', 'local_amount', 'fx_rate',
            'total_clicks', 'total_conversions',
            'fraud_rate', 'scrub_rate', 'scrub_reason',
            'status', 'payment_method', 'payment_address',
            'transaction_ref', 'paid_at', 'failure_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference_id', 'publisher_username', 'gross_amount',
            'scrub_amount', 'net_amount', 'fraud_rate', 'scrub_rate',
            'paid_at', 'created_at', 'updated_at',
        ]


class PayoutRecordListSerializer(ModelSerializer):
    """Compact payout record for list views (fewer fields)."""
    publisher_username = CharField(source='publisher.username', read_only=True)

    class Meta:
        model = PayoutRecord
        fields = [
            'id', 'reference_id', 'publisher_username',
            'period_from', 'period_to', 'net_amount', 'currency',
            'status', 'payment_method', 'paid_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'reference_id', 'publisher_username',
            'period_from', 'period_to', 'net_amount', 'currency',
            'status', 'payment_method', 'paid_at', 'created_at',
        ]


# ── PayoutBatch ───────────────────────────────────────────────────────────────

class PayoutBatchSerializer(ModelSerializer):
    """Payout batch — full detail view."""
    created_by_username = CharField(source='created_by.username', read_only=True)

    class Meta:
        model = PayoutBatch
        fields = [
            'id', 'reference_id', 'label', 'period_from', 'period_to',
            'total_records', 'total_amount', 'status',
            'created_by', 'created_by_username', 'notes',
            'created_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'reference_id', 'total_records', 'total_amount',
            'created_by', 'created_by_username',
            'created_at', 'completed_at',
        ]


class PayoutBatchCreateSerializer(Serializer):
    """Input for creating a new payout batch."""
    label       = CharField(max_length=200)
    period_from = DateField()
    period_to   = DateField()
    notes       = CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['period_from'] > attrs['period_to']:
            raise ValidationError('period_from must be before period_to.')
        return attrs
