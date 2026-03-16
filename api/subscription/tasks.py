"""
tasks.py – Celery tasks for the subscription module.

Schedule via Celery Beat in settings:
    CELERY_BEAT_SCHEDULE = {
        "expire-subscriptions": {
            "task": "subscription.tasks.expire_subscriptions",
            "schedule": crontab(hour=0, minute=0),  # Daily at midnight
        },
        "send-renewal-reminders": {
            "task": "subscription.tasks.send_renewal_reminders",
            "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM
        },
        "retry-failed-payments": {
            "task": "subscription.tasks.retry_failed_payments",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
        },
        "send-trial-ending-notices": {
            "task": "subscription.tasks.send_trial_ending_notices",
            "schedule": crontab(hour=9, minute=30),
        },
    }
"""
import logging
from celery import shared_task
from django.utils import timezone

from .constants import (
    MAX_PAYMENT_RETRY_ATTEMPTS,
    PAYMENT_RETRY_INTERVALS_DAYS,
    RENEWAL_REMINDER_DAYS,
    TRIAL_ENDING_REMINDER_DAYS,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="subscription.tasks.expire_subscriptions",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def expire_subscriptions(self):
    """
    Expire all subscriptions whose billing period has ended beyond the grace period.
    Runs nightly.
    """
    from .services import expire_overdue_subscriptions
    try:
        count = expire_overdue_subscriptions()
        logger.info("[expire_subscriptions] Expired %d subscriptions.", count)
        return {"expired": count}
    except Exception as exc:
        logger.exception("[expire_subscriptions] Error: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="subscription.tasks.send_renewal_reminders",
    max_retries=2,
    default_retry_delay=120,
)
def send_renewal_reminders(self):
    """
    Send email reminders to users whose subscriptions are expiring soon.
    Runs daily at 9 AM.
    """
    from .models import UserSubscription
    from .signals import subscription_activated  # reuse signal mechanism

    sent = 0
    for days in RENEWAL_REMINDER_DAYS:
        threshold_start = timezone.now() + timezone.timedelta(days=days - 1)
        threshold_end = timezone.now() + timezone.timedelta(days=days)
        expiring = UserSubscription.objects.active().filter(
            current_period_end__gte=threshold_start,
            current_period_end__lt=threshold_end,
            cancel_at_period_end=False,
        ).select_related("user", "plan")

        for sub in expiring.iterator():
            _send_renewal_reminder.delay(str(sub.pk), days)
            sent += 1

    logger.info("[send_renewal_reminders] Queued %d renewal reminder emails.", sent)
    return {"queued": sent}


@shared_task(
    bind=True,
    name="subscription.tasks._send_renewal_reminder",
    max_retries=3,
    default_retry_delay=60,
)
def _send_renewal_reminder(self, subscription_id, days_remaining):
    """Send a single renewal reminder email. Called by send_renewal_reminders."""
    from django.core.mail import send_mail
    from .models import UserSubscription
    try:
        sub = UserSubscription.objects.select_related("user", "plan").get(pk=subscription_id)
        send_mail(
            subject=f"Your {sub.plan.name} subscription renews in {days_remaining} day(s)",
            message=(
                f"Hi {sub.user.get_full_name() or sub.user.username},\n\n"
                f"Your {sub.plan.name} subscription will renew on "
                f"{sub.current_period_end.strftime('%B %d, %Y')}.\n\n"
                "No action needed – we'll charge your payment method on file.\n"
            ),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[sub.user.email],
            fail_silently=True,
        )
        logger.info("[renewal_reminder] Sent to user %s (%d days)", sub.user.pk, days_remaining)
    except Exception as exc:
        logger.exception("[renewal_reminder] Failed for subscription %s: %s", subscription_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="subscription.tasks.retry_failed_payments",
    max_retries=2,
    default_retry_delay=300,
)
def retry_failed_payments(self):
    """
    Retry failed payments for past-due subscriptions.
    Respects MAX_PAYMENT_RETRY_ATTEMPTS and retry intervals.
    """
    from .models import UserSubscription, SubscriptionPayment
    from .choices import SubscriptionStatus, PaymentStatus
    from .services import _process_renewal_payment

    retried = 0
    past_due = UserSubscription.objects.filter(
        status=SubscriptionStatus.PAST_DUE,
        payment_retry_count__lt=MAX_PAYMENT_RETRY_ATTEMPTS,
    ).select_related("user", "plan")

    for sub in past_due.iterator():
        # Check if enough time has passed since last retry
        last_payment = (
            SubscriptionPayment.objects.filter(subscription=sub)
            .order_by("-created_at")
            .first()
        )
        if last_payment:
            retry_idx = min(sub.payment_retry_count, len(PAYMENT_RETRY_INTERVALS_DAYS) - 1)
            wait_days = PAYMENT_RETRY_INTERVALS_DAYS[retry_idx]
            next_retry_at = last_payment.created_at + timezone.timedelta(days=wait_days)
            if timezone.now() < next_retry_at:
                continue

        _retry_single_payment.delay(str(sub.pk))
        retried += 1

    logger.info("[retry_failed_payments] Queued %d payment retries.", retried)
    return {"queued": retried}


@shared_task(
    bind=True,
    name="subscription.tasks._retry_single_payment",
    max_retries=1,
)
def _retry_single_payment(self, subscription_id):
    """Retry payment for a single past-due subscription."""
    from .models import UserSubscription
    from .services import renew_subscription
    try:
        sub = UserSubscription.objects.select_related("plan").get(pk=subscription_id)
        renew_subscription(sub)
        logger.info("[retry_payment] Success for subscription %s", subscription_id)
    except Exception as exc:
        logger.warning("[retry_payment] Failed for subscription %s: %s", subscription_id, exc)


@shared_task(
    bind=True,
    name="subscription.tasks.send_trial_ending_notices",
    max_retries=2,
)
def send_trial_ending_notices(self):
    """Notify users whose trials are ending soon."""
    from .models import UserSubscription
    from .signals import trial_ending_soon

    sent = 0
    for days in TRIAL_ENDING_REMINDER_DAYS:
        expiring = UserSubscription.objects.expiring_trials(days=days).select_related("user", "plan")
        for sub in expiring.iterator():
            trial_ending_soon.send(sender=UserSubscription, instance=sub, days_remaining=days)
            sent += 1

    logger.info("[send_trial_ending_notices] Sent %d trial ending notices.", sent)
    return {"sent": sent}