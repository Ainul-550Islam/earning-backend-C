# api/djoyalty/serializers/MissingModelSerializers.py
"""
Serializers for models that previously had no API coverage.
Added via deep scan fix: CustomerSegment, CustomerSegmentMember,
LoyaltyFraudRule, LoyaltySubscription, OfferPostbackLog, SmartLinkClick.
"""
from rest_framework import serializers


# ── CustomerSegment ────────────────────────────────────────────────────────────
class CustomerSegmentSerializer(serializers.Serializer):
    """Read-only customer segment view."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    segment_type = serializers.CharField(read_only=True)
    is_dynamic = serializers.BooleanField(read_only=True)
    member_count = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_member_count(self, obj) -> int:
        try:
            return obj.members.count()
        except Exception:
            return 0

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Segment name cannot be empty.')
        return value.strip()


class CustomerSegmentWriteSerializer(serializers.Serializer):
    """Create/update a customer segment."""
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    segment_type = serializers.ChoiceField(
        choices=['manual', 'dynamic', 'rfm', 'tier', 'campaign'],
        default='manual',
    )
    is_dynamic = serializers.BooleanField(default=False)
    filter_rules = serializers.JSONField(required=False, default=dict)

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Segment name cannot be empty.')
        return value.strip()


# ── CustomerSegmentMember ──────────────────────────────────────────────────────
class CustomerSegmentMemberSerializer(serializers.Serializer):
    """Segment membership record."""
    id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True)
    customer_code = serializers.SerializerMethodField()
    segment_id = serializers.IntegerField(read_only=True)
    added_at = serializers.DateTimeField(read_only=True)
    added_by = serializers.CharField(read_only=True)

    def get_customer_code(self, obj) -> str:
        try:
            return obj.customer.code if obj.customer else ''
        except Exception:
            return ''


# ── LoyaltyFraudRule ───────────────────────────────────────────────────────────
class LoyaltyFraudRuleSerializer(serializers.Serializer):
    """Fraud detection rule -- admin read/write."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    rule_type = serializers.CharField()
    threshold = serializers.DecimalField(max_digits=12, decimal_places=2)
    window_minutes = serializers.IntegerField(default=60)
    action = serializers.ChoiceField(
        choices=['flag', 'block', 'alert', 'reduce'],
        default='flag',
    )
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_threshold(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            raise serializers.ValidationError('Threshold must be positive.')
        return value

    def validate_window_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError('Window must be at least 1 minute.')
        if value > 10080:  # 1 week
            raise serializers.ValidationError('Window cannot exceed 1 week (10080 minutes).')
        return value


# ── LoyaltySubscription ────────────────────────────────────────────────────────
class LoyaltySubscriptionSerializer(serializers.Serializer):
    """Paid loyalty membership subscription."""
    id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True)
    plan_name = serializers.CharField(read_only=True)
    billing_cycle = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True)
    next_billing_at = serializers.DateTimeField(read_only=True)
    cancelled_at = serializers.DateTimeField(read_only=True)


class LoyaltySubscriptionCreateSerializer(serializers.Serializer):
    """Create a new loyalty subscription."""
    customer_id = serializers.IntegerField()
    plan_name = serializers.CharField(max_length=100)
    billing_cycle = serializers.ChoiceField(
        choices=['monthly', 'quarterly', 'annual'],
        default='monthly',
    )

    def validate_plan_name(self, value):
        valid = ['bronze_plus', 'silver_plus', 'gold_plus', 'platinum', 'premium']
        if value.lower() not in valid:
            raise serializers.ValidationError(
                f'Plan must be one of: {", ".join(valid)}'
            )
        return value.lower()


# ── OfferPostbackLog ───────────────────────────────────────────────────────────
class OfferPostbackLogSerializer(serializers.Serializer):
    """Offer wall postback/conversion log -- read-only admin view."""
    id = serializers.IntegerField(read_only=True)
    offer_id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    payload = serializers.JSONField(read_only=True)
    ip_address = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    points_awarded = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)


# ── SmartLinkClick ─────────────────────────────────────────────────────────────
class SmartLinkClickSerializer(serializers.Serializer):
    """Smart link click analytics -- read-only."""
    id = serializers.IntegerField(read_only=True)
    smart_link_id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True, allow_null=True)
    ip_address = serializers.CharField(read_only=True)
    user_agent = serializers.CharField(read_only=True)
    referrer = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    converted = serializers.BooleanField(read_only=True)
    clicked_at = serializers.DateTimeField(read_only=True)
