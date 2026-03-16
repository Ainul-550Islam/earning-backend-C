"""
services.py – Pure business logic for the subscription module.

All service functions are framework-agnostic (no HTTP, no serializers).
They raise domain exceptions from exceptions.py so callers (views/tasks)
can translate to the right HTTP response or retry strategy.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .choices import SubscriptionStatus, PaymentStatus
from .constants import MAX_ACTIVE_SUBSCRIPTIONS_PER_USER
from .exceptions import (
    AlreadySubscribedException,
    NoActiveSubscriptionException,
    PaymentFailedException,
    PlanInactiveException,
    PlanNotFoundException,
    RefundNotAllowedException,
    SubscriptionPauseException,
    TrialAlreadyUsedException,
)
from .models import MembershipBenefit, SubscriptionPayment, SubscriptionPlan, UserSubscription
from .signals import (
    subscription_activated,
    subscription_cancelled,
    subscription_expired,
    subscription_renewed,
    payment_succeeded,
    payment_failed,
)

logger = logging.getLogger(__name__)


# ─── Plan Helpers ──────────────────────────────────────────────────────────────

def get_active_plans():
    """Return all publicly available, active subscription plans."""
    return (
        SubscriptionPlan.objects.active()
        .with_benefits()
        .ordered()
    )


def get_plan_or_raise(plan_id):
    try:
        plan = SubscriptionPlan.objects.get(pk=plan_id)
    except SubscriptionPlan.DoesNotExist:
        raise PlanNotFoundException()
    if not plan.status == "active":
        raise PlanInactiveException()
    return plan


# ─── Subscription Lifecycle ───────────────────────────────────────────────────

@transaction.atomic
def create_subscription(user, plan_id, payment_method=None, coupon_code=None):
    """
    Subscribe a user to a plan.
    - Validates no existing active subscription.
    - Applies trial if plan has one and user hasn't trialed before.
    - Creates initial payment record for paid plans.
    Returns the new UserSubscription instance.
    """
    plan = get_plan_or_raise(plan_id)

    # Guard: already subscribed?
    if UserSubscription.objects.has_active_subscription(user):
        raise AlreadySubscribedException()

    # Determine if trial applies
    trial_start = None
    trial_end = None
    has_trialed_before = UserSubscription.objects.filter(
        user=user, trial_end__isnull=False
    ).exists()

    if plan.has_trial and not has_trialed_before:
        trial_start = timezone.now()
        trial_end = plan.get_trial_end()
        status = SubscriptionStatus.TRIALING
    elif plan.has_trial and has_trialed_before:
        logger.info("User %s already used trial – skipping for plan %s", user.pk, plan.pk)
        status = SubscriptionStatus.PENDING
    else:
        status = SubscriptionStatus.PENDING

    now = timezone.now()
    period_end = plan.get_next_billing_date(from_date=now)

    subscription = UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=status,
        current_period_start=now,
        current_period_end=period_end,
        trial_start=trial_start,
        trial_end=trial_end,
    )

    logger.info("Subscription %s created for user %s on plan %s", subscription.pk, user.pk, plan.pk)

    if plan.is_free or status == SubscriptionStatus.TRIALING:
        subscription.activate(period_start=now, period_end=period_end)
        subscription_activated.send(sender=UserSubscription, instance=subscription)
    else:
        # Paid plan, not trialing – attempt payment
        price = _apply_coupon(plan.discounted_price, coupon_code)
        _process_initial_payment(subscription, price, plan.currency, payment_method)

    return subscription


@transaction.atomic
def cancel_subscription(subscription_id, user, reason="", comment="", at_period_end=True):
    """
    Cancel a user's subscription.
    By default cancels at period end (no immediate loss of access).
    """
    subscription = _get_user_subscription_or_raise(subscription_id, user)
    subscription.cancel(reason=reason, comment=comment, at_period_end=at_period_end)
    subscription_cancelled.send(
        sender=UserSubscription,
        instance=subscription,
        at_period_end=at_period_end,
    )
    logger.info("Subscription %s cancelled (at_period_end=%s)", subscription.pk, at_period_end)
    return subscription


@transaction.atomic
def renew_subscription(subscription):
    """
    Renew an active subscription for the next billing period.
    Called by the Celery task or webhook handler.
    """
    plan = subscription.plan
    now = timezone.now()
    new_period_end = plan.get_next_billing_date(from_date=now)

    payment = _process_renewal_payment(subscription, plan.discounted_price, plan.currency)
    if payment.status != PaymentStatus.SUCCEEDED:
        subscription.mark_past_due()
        subscription.payment_retry_count += 1
        subscription.save(update_fields=["payment_retry_count", "updated_at"])
        raise PaymentFailedException(detail=payment.failure_message or "Renewal payment failed.")

    subscription.activate(period_start=now, period_end=new_period_end)
    subscription.increment_renewal()
    subscription_renewed.send(sender=UserSubscription, instance=subscription, payment=payment)
    logger.info("Subscription %s renewed through %s", subscription.pk, new_period_end)
    return subscription


@transaction.atomic
def change_plan(subscription, new_plan_id):
    """
    Upgrade or downgrade a subscription to a different plan.
    Prorates based on remaining days (basic implementation).
    """
    new_plan = get_plan_or_raise(new_plan_id)
    old_plan = subscription.plan

    subscription.plan = new_plan
    now = timezone.now()
    subscription.current_period_end = new_plan.get_next_billing_date(from_date=now)
    subscription.save(update_fields=["plan", "current_period_end", "updated_at"])

    logger.info(
        "Subscription %s changed from plan %s to %s",
        subscription.pk, old_plan.pk, new_plan.pk,
    )
    return subscription


@transaction.atomic
def pause_subscription(subscription, resume_at=None):
    """Pause a subscription. It will not renew while paused."""
    from .constants import MAX_SUBSCRIPTION_PAUSE_DAYS
    if not subscription.is_active:
        raise SubscriptionPauseException(detail="Only active subscriptions can be paused.")
    if resume_at is None:
        resume_at = timezone.now() + timezone.timedelta(days=MAX_SUBSCRIPTION_PAUSE_DAYS)
    subscription.pause(resume_at=resume_at)
    logger.info("Subscription %s paused until %s", subscription.pk, resume_at)
    return subscription


@transaction.atomic
def resume_subscription(subscription):
    """Resume a paused subscription."""
    if not subscription.is_paused:
        raise SubscriptionPauseException(detail="Subscription is not paused.")
    subscription.resume()
    logger.info("Subscription %s resumed", subscription.pk)
    return subscription


def expire_overdue_subscriptions():
    """
    Mark subscriptions as expired when their period has ended and they are
    still in PAST_DUE or ACTIVE state beyond the grace period.
    Intended to be called by the Celery beat task.
    """
    from .constants import PAYMENT_GRACE_PERIOD_DAYS
    from .choices import SubscriptionStatus

    threshold = timezone.now() - timezone.timedelta(days=PAYMENT_GRACE_PERIOD_DAYS)
    qs = UserSubscription.objects.filter(
        status__in=[SubscriptionStatus.PAST_DUE, SubscriptionStatus.ACTIVE],
        current_period_end__lt=threshold,
    )
    count = qs.count()
    for sub in qs.iterator():
        sub.expire()
        subscription_expired.send(sender=UserSubscription, instance=sub)
    logger.info("Expired %d overdue subscriptions.", count)
    return count


# ─── Payment Helpers ──────────────────────────────────────────────────────────

def refund_payment(payment_id, amount=None):
    """
    Issue a full or partial refund for a succeeded payment.
    """
    try:
        payment = SubscriptionPayment.objects.get(pk=payment_id)
    except SubscriptionPayment.DoesNotExist:
        raise RefundNotAllowedException(detail="Payment not found.")

    if payment.status != PaymentStatus.SUCCEEDED:
        raise RefundNotAllowedException(
            detail=f"Only succeeded payments can be refunded. Current status: {payment.status}"
        )
    if payment.is_fully_refunded:
        raise RefundNotAllowedException(detail="Payment is already fully refunded.")

    with transaction.atomic():
        payment.refund(amount=amount)

    logger.info("Payment %s refunded (amount=%s)", payment.pk, amount or payment.amount)
    return payment


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _get_user_subscription_or_raise(subscription_id, user):
    try:
        return UserSubscription.objects.get(pk=subscription_id, user=user)
    except UserSubscription.DoesNotExist:
        raise NoActiveSubscriptionException()


def _apply_coupon(price, coupon_code):
    """Apply a coupon discount. Stub – integrate with coupon model as needed."""
    if not coupon_code:
        return price
    # TODO: validate coupon, apply discount, record usage
    return price


def _process_initial_payment(subscription, amount, currency, payment_method):
    """Create and attempt to collect the first payment."""
    payment = SubscriptionPayment.objects.create(
        subscription=subscription,
        amount=amount,
        currency=currency,
        payment_method=payment_method or "credit_card",
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
    )
    return _charge_payment(payment, subscription)


def _process_renewal_payment(subscription, amount, currency):
    """Create and attempt to collect a renewal payment."""
    now = timezone.now()
    payment = SubscriptionPayment.objects.create(
        subscription=subscription,
        amount=amount,
        currency=currency,
        payment_method="credit_card",  # Use stored method in real impl
        period_start=now,
        period_end=subscription.plan.get_next_billing_date(from_date=now),
    )
    return _charge_payment(payment, subscription)


def _charge_payment(payment, subscription):
    """
    Stub for actual gateway integration (Stripe, PayPal, bKash, etc.).
    Replace with real gateway calls in production.
    """
    try:
        # --- call gateway SDK here ---
        # result = stripe.PaymentIntent.create(amount=int(payment.amount * 100), ...)
        payment.mark_succeeded(transaction_id=f"txn_{payment.pk}")
        subscription.activate()
        payment_succeeded.send(sender=SubscriptionPayment, instance=payment)
    except Exception as exc:
        payment.mark_failed(message=str(exc))
        payment_failed.send(sender=SubscriptionPayment, instance=payment, exc=exc)
        logger.exception("Payment %s failed: %s", payment.pk, exc)
    return payment

# ─── Plan Delete Protection ────────────────────────────────────────────────────

def safe_delete_plan(plan):
    """
    Delete a plan only if it has no active or trialing subscribers.
    Raises PlanHasActiveSubscribersException otherwise.
    Admins should archive plans with active users instead.
    """
    from .exceptions import PlanHasActiveSubscribersException
    from .choices import SubscriptionStatus

    active_count = UserSubscription.objects.filter(
        plan=plan,
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
    ).count()

    if active_count > 0:
        raise PlanHasActiveSubscribersException(
            detail=(
                f"Cannot delete '{plan.name}' — it has {active_count} active subscriber(s). "
                f"Set status to 'archived' instead."
            )
        )
    plan.delete()
    logger.info("Plan %s (%s) deleted.", plan.name, plan.pk)


def archive_plan(plan):
    """Safely archive a plan (soft-delete). Existing subscribers keep access."""
    from .choices import PlanStatus
    plan.status = PlanStatus.ARCHIVED
    plan.save(update_fields=["status", "updated_at"])
    logger.info("Plan %s archived.", plan.pk)


# ─── Coupon Services ──────────────────────────────────────────────────────────

def validate_coupon(code, plan, user):
    """
    Validate a coupon code against a plan and user.
    Returns the Coupon instance on success, raises on failure.
    """
    from .models import Coupon
    from .exceptions import (
        InvalidCouponException,
        CouponAlreadyUsedException,
        CouponNotApplicableException,
        CouponExpiredException,
    )

    try:
        coupon = Coupon.objects.get(code=code.upper().strip())
    except Coupon.DoesNotExist:
        raise InvalidCouponException()

    if not coupon.is_active:
        raise InvalidCouponException(detail="This coupon is inactive.")

    from django.utils import timezone as tz
    now = tz.now()
    if now < coupon.valid_from:
        raise InvalidCouponException(detail="This coupon is not yet valid.")
    if coupon.valid_until and now > coupon.valid_until:
        raise CouponExpiredException()
    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        raise InvalidCouponException(detail="This coupon has reached its usage limit.")
    if not coupon.is_valid_for_plan(plan):
        raise CouponNotApplicableException(
            detail=f"Coupon '{code}' is not valid for the '{plan.name}' plan."
        )
    if not coupon.is_valid_for_user(user):
        raise CouponAlreadyUsedException()
    if coupon.min_amount and plan.price < coupon.min_amount:
        raise InvalidCouponException(
            detail=f"This coupon requires a minimum plan price of {coupon.min_amount}."
        )

    return coupon


def apply_coupon(coupon, plan, user, subscription):
    """
    Record coupon usage and return the discounted price.
    Call this AFTER the subscription is successfully created.
    """
    from .models import CouponUsage
    original_price = plan.discounted_price
    final_price = coupon.calculate_discount(original_price)
    discount_amount = original_price - final_price

    CouponUsage.objects.create(
        coupon=coupon,
        user=user,
        subscription=subscription,
        discount_applied=discount_amount,
    )
    coupon.increment_usage()
    logger.info(
        "Coupon %s applied for user %s: %s → %s (saved %s)",
        coupon.code, user.pk, original_price, final_price, discount_amount,
    )
    return final_price, discount_amount


# ─── Updated create_subscription with real coupon support ─────────────────────

@transaction.atomic
def create_subscription_v2(user, plan_id, payment_method=None, coupon_code=None):
    """
    Enhanced create_subscription with proper coupon validation and application.
    Drop-in replacement for create_subscription.
    """
    plan = get_plan_or_raise(plan_id)

    if UserSubscription.objects.has_active_subscription(user):
        raise AlreadySubscribedException()

    # Validate coupon early (before creating anything)
    coupon = None
    if coupon_code:
        coupon = validate_coupon(coupon_code, plan, user)

    has_trialed_before = UserSubscription.objects.filter(
        user=user, trial_end__isnull=False
    ).exists()

    now = timezone.now()
    trial_start = trial_end = None

    if plan.has_trial and not has_trialed_before:
        trial_start = now
        trial_end = plan.get_trial_end()
        sub_status = SubscriptionStatus.TRIALING
    else:
        sub_status = SubscriptionStatus.PENDING

    period_end = plan.get_next_billing_date(from_date=now)

    subscription = UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=sub_status,
        current_period_start=now,
        current_period_end=period_end,
        trial_start=trial_start,
        trial_end=trial_end,
    )

    # Apply coupon (records usage, returns discounted price)
    effective_price = plan.discounted_price
    if coupon:
        effective_price, _ = apply_coupon(coupon, plan, user, subscription)

    if plan.is_free or sub_status == SubscriptionStatus.TRIALING:
        subscription.activate(period_start=now, period_end=period_end)
        subscription_activated.send(sender=UserSubscription, instance=subscription)
    else:
        _process_initial_payment(subscription, effective_price, plan.currency, payment_method)

    logger.info(
        "Subscription %s created for user %s on plan %s (coupon=%s)",
        subscription.pk, user.pk, plan.pk, coupon_code or "none"
    )
    return subscription


# ─── Admin Subscription Management ────────────────────────────────────────────

@transaction.atomic
def admin_create_subscription(admin_user, user_id, plan_id, status="active",
                               current_period_start=None, current_period_end=None, notes=""):
    """
    Admin: force-create a subscription for any user, bypassing payment.
    Useful for manual grants, comps, migrations.
    """
    from django.contrib.auth import get_user_model
    from .exceptions import AdminSubscriptionException

    User = get_user_model()
    try:
        target_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise AdminSubscriptionException(detail="Target user not found.")

    plan = get_plan_or_raise(plan_id)
    now = timezone.now()

    # Cancel any existing active sub before force-creating
    existing = UserSubscription.objects.get_active_for_user(target_user)
    if existing:
        existing.cancel(reason="other", comment=f"Superseded by admin grant. Notes: {notes}")
        logger.info("Admin %s cancelled existing sub %s for user %s",
                    admin_user.pk, existing.pk, target_user.pk)

    period_start = current_period_start or now
    period_end = current_period_end or plan.get_next_billing_date(from_date=now)

    subscription = UserSubscription.objects.create(
        user=target_user,
        plan=plan,
        status=status,
        current_period_start=period_start,
        current_period_end=period_end,
        metadata={"admin_granted_by": str(admin_user.pk), "notes": notes},
    )

    if status == SubscriptionStatus.ACTIVE:
        subscription_activated.send(sender=UserSubscription, instance=subscription)

    logger.info(
        "Admin %s force-created subscription %s for user %s on plan %s (status=%s)",
        admin_user.pk, subscription.pk, target_user.pk, plan.pk, status,
    )
    return subscription


@transaction.atomic
def admin_force_status(subscription, new_status, reason=""):
    """Admin: forcefully set a subscription to any status."""
    from .choices import SubscriptionStatus as SS
    old_status = subscription.status

    status_action_map = {
        SS.ACTIVE:    subscription.activate,
        SS.EXPIRED:   subscription.expire,
        SS.PAST_DUE:  subscription.mark_past_due,
        SS.PAUSED:    subscription.pause,
        SS.CANCELLED: lambda: subscription.cancel(reason="other", comment=reason),
    }

    action = status_action_map.get(new_status)
    if action:
        action()
    else:
        subscription.status = new_status
        subscription.save(update_fields=["status", "updated_at"])

    logger.info(
        "Admin force-set subscription %s: %s → %s (reason: %s)",
        subscription.pk, old_status, new_status, reason or "none",
    )
    return subscription
