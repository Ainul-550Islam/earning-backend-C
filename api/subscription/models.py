import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    BenefitType,
    CancellationReason,
    Currency,
    PaymentMethod,
    PaymentStatus,
    PlanInterval,
    PlanStatus,
    SubscriptionStatus,
)
from .constants import DEFAULT_CURRENCY
from .managers import (
    SubscriptionPlanManager,
    SubscriptionPaymentManager,
    UserSubscriptionManager,
)
from .validators import (
    validate_discount_percent,
    validate_payment_amount,
    validate_positive_price,
    validate_trial_days,
)


# ─── Base Model ────────────────────────────────────────────────────────────────

class TimeStampedModel(models.Model):
    """Abstract base adding created_at / updated_at to every model."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ─── SubscriptionPlan ──────────────────────────────────────────────────────────

class SubscriptionPlan(TimeStampedModel):
    """
    Defines a subscription tier (e.g. Free, Pro, Enterprise).
    Plans are immutable once active users are subscribed to them – create
    a new plan and migrate users instead of editing price/interval on live plans.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("plan name"), max_length=120, unique=True)
    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    description = models.TextField(_("description"), blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PlanStatus.choices,
        default=PlanStatus.ACTIVE,
        db_index=True,
    )

    # ─── Pricing ──────────────────────────────────────────────────────────────
    price = models.DecimalField(
        _("price"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_positive_price],
    )
    currency = models.CharField(
        _("currency"),
        max_length=3,
        choices=Currency.choices,
        default=DEFAULT_CURRENCY,
    )
    interval = models.CharField(
        _("billing interval"),
        max_length=20,
        choices=PlanInterval.choices,
        default=PlanInterval.MONTHLY,
    )
    interval_count = models.PositiveSmallIntegerField(
        _("interval count"),
        default=1,
        help_text=_("Number of intervals between billings, e.g. every 3 months."),
    )

    # ─── Trial ────────────────────────────────────────────────────────────────
    trial_period_days = models.PositiveSmallIntegerField(
        _("trial period (days)"),
        default=0,
        validators=[validate_trial_days],
    )

    # ─── Discounts ────────────────────────────────────────────────────────────
    discount_percent = models.DecimalField(
        _("discount percent"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_discount_percent],
    )
    setup_fee = models.DecimalField(
        _("one-time setup fee"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # ─── Meta ─────────────────────────────────────────────────────────────────
    is_featured = models.BooleanField(_("featured"), default=False)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    max_users = models.PositiveIntegerField(
        _("max users"),
        null=True,
        blank=True,
        help_text=_("Leave blank for unlimited."),
    )
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = SubscriptionPlanManager()

    class Meta:
        verbose_name = _("subscription plan")
        verbose_name_plural = _("subscription plans")
        ordering = ["sort_order", "price"]
        indexes = [
            models.Index(fields=["status", "price"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_interval_display()} – {self.currency} {self.price})"

    @property
    def is_free(self):
        return self.price == Decimal("0.00")

    @property
    def has_trial(self):
        return self.trial_period_days > 0

    @property
    def discounted_price(self):
        if self.discount_percent:
            discount = self.price * (self.discount_percent / Decimal("100"))
            return (self.price - discount).quantize(Decimal("0.01"))
        return self.price

    def get_trial_end(self):
        if self.has_trial:
            return timezone.now() + timezone.timedelta(days=self.trial_period_days)
        return None

    def get_next_billing_date(self, from_date=None):
        """Calculate the next billing date from a given date."""
        from_date = from_date or timezone.now()
        delta_map = {
            PlanInterval.DAILY: timezone.timedelta(days=self.interval_count),
            PlanInterval.WEEKLY: timezone.timedelta(weeks=self.interval_count),
            PlanInterval.MONTHLY: timezone.timedelta(days=30 * self.interval_count),
            PlanInterval.QUARTERLY: timezone.timedelta(days=90 * self.interval_count),
            PlanInterval.YEARLY: timezone.timedelta(days=365 * self.interval_count),
            PlanInterval.LIFETIME: None,
        }
        delta = delta_map.get(self.interval)
        return from_date + delta if delta else None


# ─── MembershipBenefit ────────────────────────────────────────────────────────

class MembershipBenefit(TimeStampedModel):
    """
    A specific feature or limit attached to a SubscriptionPlan.
    e.g.  plan=Pro, type=api_calls, value="10000", label="10 000 API calls/month"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="benefits",
        verbose_name=_("plan"),
    )
    benefit_type = models.CharField(
        _("benefit type"),
        max_length=30,
        choices=BenefitType.choices,
        default=BenefitType.FEATURE,
        db_index=True,
    )
    label = models.CharField(_("label"), max_length=200)
    value = models.CharField(
        _("value"),
        max_length=200,
        blank=True,
        help_text=_("Numeric limit, feature key, or descriptive string."),
    )
    is_highlighted = models.BooleanField(
        _("highlighted"),
        default=False,
        help_text=_("Show prominently on pricing pages."),
    )
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("membership benefit")
        verbose_name_plural = _("membership benefits")
        ordering = ["sort_order"]
        unique_together = [("plan", "label")]

    def __str__(self):
        return f"{self.plan.name} – {self.label}"


# ─── UserSubscription ─────────────────────────────────────────────────────────

class UserSubscription(TimeStampedModel):
    """
    Represents the relationship between a user and a SubscriptionPlan.
    Tracks billing cycles, trial periods, and lifecycle status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("user"),
        db_index=True,
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("plan"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True,
    )

    # ─── Billing Cycle ────────────────────────────────────────────────────────
    current_period_start = models.DateTimeField(_("period start"), null=True, blank=True)
    current_period_end = models.DateTimeField(_("period end"), null=True, blank=True, db_index=True)

    # ─── Trial ────────────────────────────────────────────────────────────────
    trial_start = models.DateTimeField(_("trial start"), null=True, blank=True)
    trial_end = models.DateTimeField(_("trial end"), null=True, blank=True, db_index=True)

    # ─── Cancellation ─────────────────────────────────────────────────────────
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancellation_reason = models.CharField(
        _("cancellation reason"),
        max_length=30,
        choices=CancellationReason.choices,
        blank=True,
    )
    cancellation_comment = models.TextField(_("cancellation comment"), blank=True)
    cancel_at_period_end = models.BooleanField(
        _("cancel at period end"),
        default=False,
        help_text=_("If True, subscription stays active until end of billing period."),
    )

    # ─── Pause ────────────────────────────────────────────────────────────────
    paused_at = models.DateTimeField(_("paused at"), null=True, blank=True)
    pause_resumes_at = models.DateTimeField(_("pause resumes at"), null=True, blank=True)

    # ─── External References ──────────────────────────────────────────────────
    external_subscription_id = models.CharField(
        _("external subscription ID"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Stripe / PayPal / gateway subscription ID."),
    )

    # ─── Counters ─────────────────────────────────────────────────────────────
    payment_retry_count = models.PositiveSmallIntegerField(_("payment retry count"), default=0)
    renewal_count = models.PositiveSmallIntegerField(_("renewal count"), default=0)

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = UserSubscriptionManager()

    class Meta:
        verbose_name = _("user subscription")
        verbose_name_plural = _("user subscriptions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "current_period_end"]),
            models.Index(fields=["external_subscription_id"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.plan.name} ({self.get_status_display()})"

    # ─── Status Helpers ───────────────────────────────────────────────────────

    @property
    def is_active(self):
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def is_trialing(self):
        return self.status == SubscriptionStatus.TRIALING

    @property
    def is_active_or_trialing(self):
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)

    @property
    def is_cancelled(self):
        return self.status == SubscriptionStatus.CANCELLED

    @property
    def is_expired(self):
        return self.status == SubscriptionStatus.EXPIRED

    @property
    def is_past_due(self):
        return self.status == SubscriptionStatus.PAST_DUE

    @property
    def is_paused(self):
        return self.status == SubscriptionStatus.PAUSED

    @property
    def days_until_renewal(self):
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(delta.days, 0)
        return None

    @property
    def is_in_trial(self):
        if self.trial_end:
            return timezone.now() < self.trial_end
        return False

    def activate(self, period_start=None, period_end=None):
        now = timezone.now()
        self.status = SubscriptionStatus.ACTIVE
        self.current_period_start = period_start or now
        if period_end:
            self.current_period_end = period_end
        self.save(update_fields=["status", "current_period_start", "current_period_end", "updated_at"])

    def cancel(self, reason="", comment="", at_period_end=False):
        self.cancellation_reason = reason
        self.cancellation_comment = comment
        self.cancel_at_period_end = at_period_end
        if not at_period_end:
            self.status = SubscriptionStatus.CANCELLED
            self.cancelled_at = timezone.now()
        self.save(update_fields=[
            "status", "cancelled_at", "cancellation_reason",
            "cancellation_comment", "cancel_at_period_end", "updated_at",
        ])

    def expire(self):
        self.status = SubscriptionStatus.EXPIRED
        self.save(update_fields=["status", "updated_at"])

    def mark_past_due(self):
        self.status = SubscriptionStatus.PAST_DUE
        self.save(update_fields=["status", "updated_at"])

    def pause(self, resume_at=None):
        self.status = SubscriptionStatus.PAUSED
        self.paused_at = timezone.now()
        self.pause_resumes_at = resume_at
        self.save(update_fields=["status", "paused_at", "pause_resumes_at", "updated_at"])

    def resume(self):
        self.status = SubscriptionStatus.ACTIVE
        self.paused_at = None
        self.pause_resumes_at = None
        self.save(update_fields=["status", "paused_at", "pause_resumes_at", "updated_at"])

    def increment_renewal(self):
        self.renewal_count += 1
        self.save(update_fields=["renewal_count", "updated_at"])


# ─── SubscriptionPayment ──────────────────────────────────────────────────────

class SubscriptionPayment(TimeStampedModel):
    """
    Immutable record of a payment event for a UserSubscription.
    Never delete – only mark as refunded.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("subscription"),
    )
    status = models.CharField(
        _("status"),
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        _("payment method"),
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CREDIT_CARD,
    )

    # ─── Amounts ──────────────────────────────────────────────────────────────
    amount = models.DecimalField(
        _("amount"),
        max_digits=10,
        decimal_places=2,
        validators=[validate_payment_amount],
    )
    currency = models.CharField(
        _("currency"),
        # max_digits=3,  # DecimalField doesn't support max_digits for CharField, so we use max_length instead
        max_length=3,
        choices=Currency.choices,
        default=DEFAULT_CURRENCY,
    )
    amount_refunded = models.DecimalField(
        _("amount refunded"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_amount = models.DecimalField(
        _("tax amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    discount_amount = models.DecimalField(
        _("discount amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # ─── External References ──────────────────────────────────────────────────
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    gateway_response = models.JSONField(
        _("gateway response"),
        default=dict,
        blank=True,
        help_text=_("Raw payment gateway response payload."),
    )
    invoice_url = models.URLField(_("invoice URL"), blank=True)

    # ─── Billing Period This Payment Covers ───────────────────────────────────
    period_start = models.DateTimeField(_("billing period start"), null=True, blank=True)
    period_end = models.DateTimeField(_("billing period end"), null=True, blank=True)

    # ─── Failure Info ─────────────────────────────────────────────────────────
    failure_code = models.CharField(_("failure code"), max_length=100, blank=True)
    failure_message = models.TextField(_("failure message"), blank=True)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)

    objects = SubscriptionPaymentManager()

    class Meta:
        verbose_name = _("subscription payment")
        verbose_name_plural = _("subscription payments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["transaction_id"]),
        ]

    def __str__(self):
        return (
            f"Payment #{self.id} – {self.subscription.user} "
            f"{self.currency} {self.amount} ({self.get_status_display()})"
        )

    @property
    def net_amount(self):
        amount = self.amount if self.amount is not None else 0
        refunded = self.amount_refunded if self.amount_refunded is not None else 0
        return amount - refunded

    @property
    def is_fully_refunded(self):
        return self.amount_refunded >= self.amount

    def mark_succeeded(self, transaction_id=None, gateway_response=None):
        self.status = PaymentStatus.SUCCEEDED
        self.paid_at = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            "status", "paid_at", "transaction_id", "gateway_response", "updated_at"
        ])

    def mark_failed(self, code="", message="", gateway_response=None):
        self.status = PaymentStatus.FAILED
        self.failure_code = code
        self.failure_message = message
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=[
            "status", "failure_code", "failure_message", "gateway_response", "updated_at"
        ])

    def refund(self, amount=None):
        from .validators import validate_refund_amount
        refund_amount = amount or self.amount
        validate_refund_amount(refund_amount, self.amount)
        self.amount_refunded = refund_amount
        self.status = (
            PaymentStatus.REFUNDED
            if refund_amount >= self.amount
            else PaymentStatus.PARTIALLY_REFUNDED
        )
        self.save(update_fields=["amount_refunded", "status", "updated_at"])

# ─── Coupon ───────────────────────────────────────────────────────────────────

class Coupon(TimeStampedModel):
    """
    Discount coupon that can be applied at subscription time.
    Supports percent-off and fixed-amount discounts, usage limits,
    plan-specific restrictions, and expiry dates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        _("coupon code"),
        max_length=50,
        unique=True,
        help_text=_("Case-insensitive coupon code users enter at checkout."),
    )
    description = models.CharField(_("description"), max_length=255, blank=True)

    # ─── Discount ─────────────────────────────────────────────────────────────
    discount_type = models.CharField(
        _("discount type"),
        max_length=10,
        choices=[("percent", "Percentage"), ("fixed", "Fixed Amount")],
        default="percent",
    )
    discount_value = models.DecimalField(
        _("discount value"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Percentage (0–100) or fixed amount depending on discount_type."),
    )
    currency = models.CharField(
        _("currency"),
        max_length=3,
        choices=Currency.choices,
        default=DEFAULT_CURRENCY,
        blank=True,
        help_text=_("Only used when discount_type is 'fixed'."),
    )

    # ─── Restrictions ─────────────────────────────────────────────────────────
    applicable_plans = models.ManyToManyField(
        SubscriptionPlan,
        blank=True,
        related_name="coupons",
        verbose_name=_("applicable plans"),
        help_text=_("Leave empty to allow on all plans."),
    )
    min_amount = models.DecimalField(
        _("minimum order amount"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Minimum plan price required to use this coupon."),
    )

    # ─── Validity ─────────────────────────────────────────────────────────────
    is_active = models.BooleanField(_("active"), default=True)
    valid_from = models.DateTimeField(_("valid from"), default=timezone.now)
    valid_until = models.DateTimeField(_("valid until"), null=True, blank=True)

    # ─── Usage Limits ─────────────────────────────────────────────────────────
    max_uses = models.PositiveIntegerField(
        _("max uses"),
        null=True,
        blank=True,
        help_text=_("Leave blank for unlimited uses."),
    )
    max_uses_per_user = models.PositiveSmallIntegerField(
        _("max uses per user"),
        default=1,
        help_text=_("How many times a single user can use this coupon."),
    )
    times_used = models.PositiveIntegerField(_("times used"), default=0, editable=False)

    class Meta:
        verbose_name = _("coupon")
        verbose_name_plural = _("coupons")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "valid_until"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.get_discount_display()})"

    def get_discount_display(self):
        if self.discount_type == "percent":
            return f"{self.discount_value}% off"
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "BDT": "৳", "INR": "₹"}
        sym = symbols.get(self.currency, self.currency)
        return f"{sym}{self.discount_value} off"

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def is_valid_for_user(self, user):
        if not self.is_valid:
            return False
        used_by_user = CouponUsage.objects.filter(coupon=self, user=user).count()
        return used_by_user < self.max_uses_per_user

    def is_valid_for_plan(self, plan):
        if not self.applicable_plans.exists():
            return True  # No restriction = valid for all plans
        return self.applicable_plans.filter(pk=plan.pk).exists()

    def calculate_discount(self, original_price):
        """Return the discounted final price (never below 0)."""
        from decimal import Decimal
        if self.discount_type == "percent":
            reduction = original_price * (self.discount_value / Decimal("100"))
        else:
            reduction = self.discount_value
        return max(original_price - reduction, Decimal("0.00"))

    def increment_usage(self):
        self.times_used = models.F("times_used") + 1
        self.save(update_fields=["times_used"])


class CouponUsage(TimeStampedModel):
    """Records each time a user successfully uses a coupon."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages",
        verbose_name=_("coupon"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        verbose_name=_("user"),
    )
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_usages",
        verbose_name=_("subscription"),
    )
    discount_applied = models.DecimalField(
        _("discount applied"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Actual amount discounted at time of use."),
    )

    class Meta:
        verbose_name = _("coupon usage")
        verbose_name_plural = _("coupon usages")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["coupon", "user"])]

    def __str__(self):
        return f"{self.user} used {self.coupon.code}"
