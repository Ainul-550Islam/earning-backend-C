from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from .constants import MIN_PLAN_PRICE, MAX_PLAN_PRICE, MAX_TRIAL_DAYS


def validate_positive_price(value):
    if value < MIN_PLAN_PRICE:
        raise ValidationError(
            f"Price must be at least {MIN_PLAN_PRICE}. Got {value}."
        )
    if value > MAX_PLAN_PRICE:
        raise ValidationError(
            f"Price cannot exceed {MAX_PLAN_PRICE}. Got {value}."
        )


def validate_trial_days(value):
    if value < 0:
        raise ValidationError("Trial days cannot be negative.")
    if value > MAX_TRIAL_DAYS:
        raise ValidationError(
            f"Trial days cannot exceed {MAX_TRIAL_DAYS}. Got {value}."
        )


def validate_discount_percent(value):
    if value < Decimal("0.00") or value > Decimal("100.00"):
        raise ValidationError(
            f"Discount percent must be between 0 and 100. Got {value}."
        )


def validate_future_date(value):
    if value <= timezone.now():
        raise ValidationError("Date must be in the future.")


def validate_plan_active(plan):
    from .choices import PlanStatus
    if plan.status != PlanStatus.ACTIVE:
        raise ValidationError(
            f"Plan '{plan.name}' is not active and cannot be subscribed to."
        )


def validate_period_dates(start, end):
    if start >= end:
        raise ValidationError(
            "Period end date must be after period start date."
        )


def validate_payment_amount(value):
    if value <= Decimal("0.00"):
        raise ValidationError("Payment amount must be greater than zero.")


def validate_no_active_subscription(user):
    """Raise if user already has an active or trialing subscription."""
    from .models import UserSubscription
    from .choices import SubscriptionStatus
    exists = UserSubscription.objects.filter(
        user=user,
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
    ).exists()
    if exists:
        raise ValidationError(
            "User already has an active subscription. "
            "Cancel the current subscription before subscribing to a new plan."
        )


def validate_refund_amount(refund_amount, original_amount):
    if refund_amount <= Decimal("0.00"):
        raise ValidationError("Refund amount must be greater than zero.")
    if refund_amount > original_amount:
        raise ValidationError(
            f"Refund amount ({refund_amount}) cannot exceed "
            f"the original payment amount ({original_amount})."
        )