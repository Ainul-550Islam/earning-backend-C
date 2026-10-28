# api/djoyalty/serializers/MembershipSerializer.py
"""
Membership Serializers -- DRF serializers for paid_membership.py models।

FIXED: MembershipViewSet was returning raw dict responses throughout (22 raw
Response({'...'}) calls) with no type safety or validation।
Proper DRF serializers provide:
  - Input validation (plan_id, payment_method, payment_reference)
  - Consistent API schema for auto-generated docs (drf-spectacular)
  - Type-safe decimal / datetime serialization
  - SerializerMethodField for computed properties (days_remaining, is_active)
"""
from decimal import Decimal
from rest_framework import serializers


class MembershipPlanSerializer(serializers.Serializer):
    """
    Read-only serializer for MembershipPlan।
    Used in GET /memberships/plans/ and GET /memberships/plans/{id}/
    """
    id                    = serializers.IntegerField(read_only=True)
    name                  = serializers.CharField(read_only=True)
    slug                  = serializers.CharField(source='plan_code', read_only=True)
    description           = serializers.CharField(read_only=True, allow_null=True)
    billing_cycle         = serializers.CharField(read_only=True)
    price                 = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
    )
    currency              = serializers.CharField(read_only=True)
    welcome_points        = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    monthly_bonus_points  = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    earn_multiplier       = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True,
    )
    free_cashout_per_month = serializers.IntegerField(read_only=True)
    priority_support      = serializers.BooleanField(read_only=True)
    exclusive_offers      = serializers.BooleanField(read_only=True)
    early_access          = serializers.BooleanField(read_only=True)
    is_active             = serializers.BooleanField(read_only=True)
    max_members           = serializers.IntegerField(read_only=True, allow_null=True)
    current_members       = serializers.IntegerField(read_only=True)
    sort_order            = serializers.IntegerField(read_only=True)
    billing_days          = serializers.SerializerMethodField()
    min_tier              = serializers.SerializerMethodField()
    spots_remaining       = serializers.SerializerMethodField()

    def get_billing_days(self, obj) -> int:
        try:
            return obj.get_billing_days()
        except Exception:
            return 30

    def get_min_tier(self, obj) -> dict | None:
        try:
            t = obj.min_tier
            if t:
                return {'id': t.id, 'name': t.name, 'rank': t.rank}
        except Exception:
            pass
        return None

    def get_spots_remaining(self, obj) -> int | None:
        try:
            if obj.max_members is None:
                return None
            return max(0, obj.max_members - obj.current_members)
        except Exception:
            return None


class CustomerMembershipSerializer(serializers.Serializer):
    """
    Read-only serializer for CustomerMembership।
    Used in GET /memberships/my/ and admin list endpoints。
    """
    id                         = serializers.IntegerField(read_only=True)
    plan                       = MembershipPlanSerializer(read_only=True)
    status                     = serializers.CharField(read_only=True)
    started_at                 = serializers.DateTimeField(read_only=True)
    current_period_start       = serializers.DateTimeField(read_only=True)
    current_period_end         = serializers.DateTimeField(read_only=True)
    cancelled_at               = serializers.DateTimeField(
        read_only=True, allow_null=True,
    )
    trial_ends_at              = serializers.DateTimeField(
        read_only=True, allow_null=True,
    )
    payment_method             = serializers.CharField(read_only=True)
    auto_renew                 = serializers.BooleanField(read_only=True)
    cashouts_used_this_month   = serializers.IntegerField(read_only=True)
    last_bonus_credited_at     = serializers.DateTimeField(
        read_only=True, allow_null=True,
    )
    created_at                 = serializers.DateTimeField(read_only=True)
    is_active                  = serializers.SerializerMethodField()
    days_remaining             = serializers.SerializerMethodField()
    free_cashouts_remaining    = serializers.SerializerMethodField()
    current_earn_multiplier    = serializers.SerializerMethodField()

    def get_is_active(self, obj) -> bool:
        try:
            return obj.is_active() if callable(obj.is_active) else bool(obj.is_active)
        except Exception:
            return obj.status == 'active'

    def get_days_remaining(self, obj) -> int:
        try:
            return obj.days_remaining() if callable(obj.days_remaining) else 0
        except Exception:
            return 0

    def get_free_cashouts_remaining(self, obj) -> int:
        try:
            limit = obj.plan.free_cashout_per_month if obj.plan else 0
            return max(0, limit - obj.cashouts_used_this_month)
        except Exception:
            return 0

    def get_current_earn_multiplier(self, obj) -> str:
        try:
            return str(obj.plan.earn_multiplier if obj.plan else Decimal('1.00'))
        except Exception:
            return '1.00'


class MembershipSubscribeSerializer(serializers.Serializer):
    """
    Input serializer for POST /memberships/subscribe/
    Validates plan_id, payment_method, payment_reference।
    """
    plan_id           = serializers.IntegerField(
        required=True,
        help_text='ID of the MembershipPlan to subscribe to',
    )
    payment_method    = serializers.ChoiceField(
        choices=['bkash', 'nagad', 'sslcommerz', 'bank', 'manual'],
        required=False,
        default='bkash',
    )
    payment_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=200,
        help_text='Transaction reference from payment gateway',
    )
    auto_renew        = serializers.BooleanField(
        required=False,
        default=True,
    )


class MembershipRenewSerializer(serializers.Serializer):
    """
    Input serializer for POST /memberships/my/renew/
    """
    payment_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=200,
    )
    payment_method    = serializers.ChoiceField(
        choices=['bkash', 'nagad', 'sslcommerz', 'bank', 'manual'],
        required=False,
        default='bkash',
    )


class MembershipBenefitsSerializer(serializers.Serializer):
    """
    Response serializer for GET /memberships/my/benefits/
    """
    earn_multiplier         = serializers.CharField(read_only=True)
    can_free_cashout        = serializers.BooleanField(read_only=True)
    free_cashouts_remaining = serializers.IntegerField(read_only=True)
    has_priority_support    = serializers.BooleanField(read_only=True)
    has_exclusive_offers    = serializers.BooleanField(read_only=True)
    has_early_access        = serializers.BooleanField(read_only=True)
    monthly_bonus_points    = serializers.CharField(read_only=True)
    plan_name               = serializers.CharField(read_only=True, allow_blank=True)
    status                  = serializers.CharField(read_only=True)


class AdminCreditBonusSerializer(serializers.Serializer):
    """
    Input serializer for POST /memberships/admin/{id}/credit-bonus/
    """
    force = serializers.BooleanField(
        required=False,
        default=False,
        help_text='Force credit even if already credited this month',
    )
    note  = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=500,
    )
