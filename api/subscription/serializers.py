from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from .choices import CancellationReason, PaymentMethod
from .models import MembershipBenefit, SubscriptionPayment, SubscriptionPlan, UserSubscription


# ─── MembershipBenefit ────────────────────────────────────────────────────────

class MembershipBenefitSerializer(serializers.ModelSerializer):
    benefit_type_display = serializers.CharField(
        source="get_benefit_type_display", read_only=True
    )

    class Meta:
        model = MembershipBenefit
        fields = [
            "id", "benefit_type", "benefit_type_display",
            "label", "value", "is_highlighted", "sort_order",
        ]


# ─── SubscriptionPlan ─────────────────────────────────────────────────────────

class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for plan listing."""
    benefits = MembershipBenefitSerializer(many=True, read_only=True)
    interval_display = serializers.CharField(source="get_interval_display", read_only=True)
    discounted_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_free = serializers.BooleanField(read_only=True)
    has_trial = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id", "name", "slug", "description", "status",
            "price", "discounted_price", "currency", "interval", "interval_display",
            "interval_count", "trial_period_days", "discount_percent", "setup_fee",
            "is_featured", "sort_order", "is_free", "has_trial", "benefits",
        ]


class SubscriptionPlanDetailSerializer(SubscriptionPlanListSerializer):
    """Full serializer including metadata, used in admin/detail views."""
    class Meta(SubscriptionPlanListSerializer.Meta):
        fields = SubscriptionPlanListSerializer.Meta.fields + ["metadata", "max_users", "created_at", "updated_at"]


class SubscriptionPlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "name", "slug", "description", "status",
            "price", "currency", "interval", "interval_count",
            "trial_period_days", "discount_percent", "setup_fee",
            "is_featured", "sort_order", "max_users", "metadata",
        ]

    def validate_price(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_trial_period_days(self, value):
        if value < 0:
            raise serializers.ValidationError("Trial days cannot be negative.")
        return value


# ─── UserSubscription ─────────────────────────────────────────────────────────

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanListSerializer(read_only=True)
    plan_id = serializers.UUIDField(write_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_trialing = serializers.BooleanField(read_only=True)
    days_until_renewal = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            "id", "plan", "plan_id", "status", "status_display",
            "current_period_start", "current_period_end",
            "trial_start", "trial_end",
            "cancel_at_period_end", "cancelled_at",
            "paused_at", "pause_resumes_at",
            "renewal_count", "is_active", "is_trialing", "days_until_renewal",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "current_period_start", "current_period_end",
            "trial_start", "trial_end", "cancelled_at", "renewal_count",
            "created_at", "updated_at",
        ]


class SubscribeSerializer(serializers.Serializer):
    """Input serializer for creating a new subscription."""
    plan_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.CREDIT_CARD,
        required=False,
    )
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(pk=value, status="active").exists():
            raise serializers.ValidationError("Plan not found or is inactive.")
        return value


class CancelSubscriptionSerializer(serializers.Serializer):
    """Input serializer for cancellation."""
    reason = serializers.ChoiceField(
        choices=CancellationReason.choices,
        required=False,
        default=CancellationReason.OTHER,
    )
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    at_period_end = serializers.BooleanField(default=True)


class ChangePlanSerializer(serializers.Serializer):
    new_plan_id = serializers.UUIDField()

    def validate_new_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(pk=value, status="active").exists():
            raise serializers.ValidationError("Target plan not found or inactive.")
        return value


class PauseSubscriptionSerializer(serializers.Serializer):
    resume_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_resume_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Resume date must be in the future.")
        return value


# ─── SubscriptionPayment ─────────────────────────────────────────────────────

class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    net_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_fully_refunded = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscriptionPayment
        fields = [
            "id", "subscription", "status", "status_display",
            "payment_method", "payment_method_display",
            "amount", "currency", "amount_refunded", "net_amount",
            "tax_amount", "discount_amount", "is_fully_refunded",
            "transaction_id", "invoice_url",
            "period_start", "period_end",
            "failure_code", "failure_message", "paid_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class RefundPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Leave blank for full refund.",
    )

    def validate_amount(self, value):
        if value is not None and value <= Decimal("0.00"):
            raise serializers.ValidationError("Refund amount must be positive.")
        return value

# ─── MembershipBenefit Write ──────────────────────────────────────────────────

class MembershipBenefitWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipBenefit
        fields = [
            "id", "plan", "benefit_type", "label", "value",
            "is_highlighted", "sort_order", "metadata",
        ]

    def validate(self, data):
        plan = data.get("plan") or (self.instance.plan if self.instance else None)
        label = data.get("label") or (self.instance.label if self.instance else None)
        qs = MembershipBenefit.objects.filter(plan=plan, label=label)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"label": "A benefit with this label already exists for the plan."}
            )
        return data


# ─── Coupon ───────────────────────────────────────────────────────────────────

class CouponSerializer(serializers.ModelSerializer):
    discount_display = serializers.CharField(source="get_discount_display", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    applicable_plans = SubscriptionPlanListSerializer(many=True, read_only=True)
    applicable_plan_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        from .models import Coupon
        model = Coupon
        fields = [
            "id", "code", "description",
            "discount_type", "discount_value", "currency",
            "applicable_plans", "applicable_plan_ids",
            "min_amount", "is_active",
            "valid_from", "valid_until",
            "max_uses", "max_uses_per_user", "times_used",
            "discount_display", "is_valid",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "times_used", "created_at", "updated_at"]

    def validate_code(self, value):
        return value.upper().strip()

    def validate_discount_value(self, value):
        from decimal import Decimal
        if value <= Decimal("0"):
            raise serializers.ValidationError("Discount value must be positive.")
        discount_type = self.initial_data.get(
            "discount_type",
            self.instance.discount_type if self.instance else "percent"
        )
        if discount_type == "percent" and value > Decimal("100"):
            raise serializers.ValidationError("Percentage discount cannot exceed 100.")
        return value

    def create(self, validated_data):
        from .models import Coupon, SubscriptionPlan
        plan_ids = validated_data.pop("applicable_plan_ids", [])
        coupon = Coupon.objects.create(**validated_data)
        if plan_ids:
            plans = SubscriptionPlan.objects.filter(pk__in=plan_ids)
            coupon.applicable_plans.set(plans)
        return coupon

    def update(self, instance, validated_data):
        plan_ids = validated_data.pop("applicable_plan_ids", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if plan_ids is not None:
            from .models import SubscriptionPlan
            plans = SubscriptionPlan.objects.filter(pk__in=plan_ids)
            instance.applicable_plans.set(plans)
        return instance


class CouponValidateSerializer(serializers.Serializer):
    """Public endpoint: check if a coupon is valid for a given plan."""
    code = serializers.CharField(max_length=50)
    plan_id = serializers.UUIDField()


class CouponUsageSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        from .models import CouponUsage
        model = CouponUsage
        fields = [
            "id", "coupon", "coupon_code", "user", "username",
            "subscription", "discount_applied", "created_at",
        ]
        read_only_fields = fields


# ─── Admin Subscription Management ───────────────────────────────────────────

class AdminSubscriptionCreateSerializer(serializers.Serializer):
    """Admin: manually create/force a subscription for any user."""
    user_id = serializers.IntegerField()
    plan_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[
            ("active", "Active"),
            ("trialing", "Trialing"),
            ("pending", "Pending"),
        ],
        default="active",
    )
    current_period_start = serializers.DateTimeField(required=False, allow_null=True)
    current_period_end = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Plan not found.")
        return value

    def validate_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User not found.")
        return value


class AdminForceStatusSerializer(serializers.Serializer):
    """Admin: force a subscription to any status."""
    status = serializers.ChoiceField(choices=[
        ("active", "Active"),
        ("trialing", "Trialing"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("paused", "Paused"),
        ("pending", "Pending"),
    ])
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
