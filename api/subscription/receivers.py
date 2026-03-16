"""
receivers.py – Signal receivers for the subscription module.
Connected in AppConfig.ready() to avoid duplicate connections.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .constants import (
    EMAIL_SUBSCRIPTION_CREATED,
    EMAIL_SUBSCRIPTION_CANCELLED,
    EMAIL_SUBSCRIPTION_EXPIRED,
    EMAIL_PAYMENT_SUCCEEDED,
    EMAIL_PAYMENT_FAILED,
    EMAIL_TRIAL_ENDING,
)

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _send_template_email(subject, template, context, to_email):
    """Render an HTML template email and send it (with plain-text fallback)."""
    try:
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Email '%s' sent to %s", subject, to_email)
    except Exception as exc:
        logger.exception("Failed to send email '%s' to %s: %s", subject, to_email, exc)


# ─── Subscription Receivers ───────────────────────────────────────────────────

def on_subscription_activated(sender, instance, **kwargs):
    """Welcome email + analytics event on activation."""
    user = instance.user
    logger.info("Subscription activated: %s for user %s", instance.pk, user.pk)
    _send_template_email(
        subject=f"Welcome to {instance.plan.name}!",
        template=EMAIL_SUBSCRIPTION_CREATED,
        context={"subscription": instance, "user": user},
        to_email=user.email,
    )


def on_subscription_cancelled(sender, instance, at_period_end=True, **kwargs):
    user = instance.user
    logger.info(
        "Subscription cancelled: %s (at_period_end=%s)", instance.pk, at_period_end
    )
    _send_template_email(
        subject="Your subscription has been cancelled",
        template=EMAIL_SUBSCRIPTION_CANCELLED,
        context={"subscription": instance, "user": user, "at_period_end": at_period_end},
        to_email=user.email,
    )


def on_subscription_expired(sender, instance, **kwargs):
    user = instance.user
    logger.info("Subscription expired: %s for user %s", instance.pk, user.pk)
    _send_template_email(
        subject="Your subscription has expired",
        template=EMAIL_SUBSCRIPTION_EXPIRED,
        context={"subscription": instance, "user": user},
        to_email=user.email,
    )


def on_subscription_renewed(sender, instance, payment=None, **kwargs):
    logger.info("Subscription renewed: %s", instance.pk)


def on_trial_ending_soon(sender, instance, days_remaining=None, **kwargs):
    user = instance.user
    logger.info(
        "Trial ending soon: %s (%d days left)", instance.pk, days_remaining or 0
    )
    _send_template_email(
        subject=f"Your free trial ends in {days_remaining} day(s)",
        template=EMAIL_TRIAL_ENDING,
        context={"subscription": instance, "user": user, "days_remaining": days_remaining},
        to_email=user.email,
    )


# ─── Payment Receivers ────────────────────────────────────────────────────────

def on_payment_succeeded(sender, instance, **kwargs):
    user = instance.subscription.user
    logger.info("Payment succeeded: %s for user %s", instance.pk, user.pk)
    _send_template_email(
        subject=f"Payment received – {instance.currency} {instance.amount}",
        template=EMAIL_PAYMENT_SUCCEEDED,
        context={"payment": instance, "user": user},
        to_email=user.email,
    )


def on_payment_failed(sender, instance, exc=None, **kwargs):
    user = instance.subscription.user
    logger.warning(
        "Payment failed: %s for user %s – %s", instance.pk, user.pk, exc
    )
    _send_template_email(
        subject="Payment failed – action required",
        template=EMAIL_PAYMENT_FAILED,
        context={"payment": instance, "user": user},
        to_email=user.email,
    )