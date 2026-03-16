"""receivers.py – Signal handlers for the inventory module."""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .constants import (
    EMAIL_ITEM_DELIVERED,
    EMAIL_ITEM_DELIVERY_FAILED,
    EMAIL_CODE_EXPIRING_SOON,
    EMAIL_LOW_STOCK_ALERT,
)

logger = logging.getLogger(__name__)


def _send_email(subject: str, template: str, context: dict, to_email: str) -> None:
    try:
        html = render_to_string(template, context)
        send_mail(
            subject=subject,
            message=strip_tags(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html,
            fail_silently=False,
        )
        logger.info("Email '%s' sent to %s", subject, to_email)
    except Exception as exc:
        logger.exception("Failed to send email '%s' to %s: %s", subject, to_email, exc)


def on_item_delivered(sender, instance, **kwargs):
    """Send delivery confirmation email to user."""
    user = instance.user
    code_value = instance.redemption_code.code if instance.redemption_code else None
    _send_email(
        subject=f"Your reward '{instance.item.name}' has been delivered!",
        template=EMAIL_ITEM_DELIVERED,
        context={"inventory": instance, "user": user, "code": code_value},
        to_email=user.email,
    )


def on_item_delivery_failed(sender, instance, error="", **kwargs):
    """Notify user of delivery failure."""
    user = instance.user
    logger.warning(
        "Delivery failed for inventory %s (user=%s, item=%s): %s",
        instance.pk, user.pk, instance.item.name, error,
    )
    _send_email(
        subject=f"Reward delivery failed – '{instance.item.name}'",
        template=EMAIL_ITEM_DELIVERY_FAILED,
        context={"inventory": instance, "user": user, "error": error},
        to_email=user.email,
    )


def on_item_expiring_soon(sender, instance, days_remaining=None, **kwargs):
    user = instance.user
    _send_email(
        subject=f"Your reward '{instance.item.name}' expires in {days_remaining} day(s)",
        template=EMAIL_CODE_EXPIRING_SOON,
        context={"inventory": instance, "user": user, "days_remaining": days_remaining},
        to_email=user.email,
    )


def on_low_stock_alert(sender, instance, alert_level=None, **kwargs):
    """Notify admins of low / critical / depleted stock."""
    admin_emails = [email for _, email in getattr(settings, "ADMINS", [])]
    if not admin_emails:
        logger.warning("No ADMINS configured – low-stock alert not delivered.")
        return
    for email in admin_emails:
        _send_email(
            subject=f"[STOCK ALERT] {alert_level.upper()} – {instance.name}",
            template=EMAIL_LOW_STOCK_ALERT,
            context={"item": instance, "alert_level": alert_level},
            to_email=email,
        )


def on_stock_depleted(sender, instance, **kwargs):
    logger.critical(
        "STOCK DEPLETED: Item '%s' (%s) is now out of stock.",
        instance.name, instance.pk,
    )


def on_code_redeemed(sender, code_instance, user, **kwargs):
    logger.info(
        "Code %s redeemed by user %s for item '%s'",
        code_instance.pk, user.pk, code_instance.item.name,
    )
