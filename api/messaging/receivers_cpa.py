"""
CPA Signal Receivers — Auto-connects CPA business events to notification system.
Connected in apps.py (MessagingConfig.ready()).

HOW TO USE:
Add this to your MessagingConfig.ready():
    from . import receivers_cpa  # noqa

Or connect manually in your app's ready():
    from messaging import receivers_cpa  # triggers @receiver decorators
"""
from __future__ import annotations
import logging
from django.dispatch import receiver
from .signals_cpa import (
    offer_status_changed, new_offer_published, offer_expiring_soon,
    conversion_received, conversion_status_changed, postback_failed,
    payout_processed, payout_threshold_reached, payout_on_hold, payout_failed,
    affiliate_status_changed, manager_assigned, fraud_detected,
    milestone_reached, epc_dropped,
)

logger = logging.getLogger(__name__)


@receiver(offer_status_changed)
def on_offer_status_changed(sender, **kwargs):
    offer_id     = kwargs.get("offer_id")
    offer_name   = kwargs.get("offer_name", "Offer")
    affiliate_id = kwargs.get("affiliate_id")
    new_status   = kwargs.get("new_status", "")
    reason       = kwargs.get("reason", "")
    payout       = kwargs.get("payout", "")
    tenant       = kwargs.get("tenant")

    if not offer_id or not affiliate_id:
        return
    try:
        from .services_cpa import (
            notify_offer_approved, notify_offer_rejected, notify_offer_paused
        )
        if new_status == "approved":
            notify_offer_approved(
                affiliate_id=affiliate_id, offer_id=offer_id,
                offer_name=offer_name, offer_payout=payout, tenant=tenant,
            )
        elif new_status == "rejected":
            notify_offer_rejected(
                affiliate_id=affiliate_id, offer_id=offer_id,
                offer_name=offer_name, reason=reason, tenant=tenant,
            )
        elif new_status in ("paused", "cap_reached"):
            notify_offer_paused(offer_id=offer_id, offer_name=offer_name,
                                reason=reason or "Cap reached", tenant=tenant)
    except Exception as exc:
        logger.error("on_offer_status_changed: %s", exc)


@receiver(new_offer_published)
def on_new_offer_published(sender, **kwargs):
    try:
        from .services_cpa import notify_new_offer_available
        notify_new_offer_available(
            offer_id=kwargs.get("offer_id"),
            offer_name=kwargs.get("offer_name", "New Offer"),
            vertical=kwargs.get("vertical", ""),
            payout=kwargs.get("payout", ""),
            countries=kwargs.get("countries", []),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_new_offer_published: %s", exc)


@receiver(conversion_received)
def on_conversion_received(sender, **kwargs):
    try:
        from .services_cpa import notify_conversion_received
        notify_conversion_received(
            affiliate_id=kwargs.get("affiliate_id"),
            conversion_id=kwargs.get("conversion_id"),
            offer_name=kwargs.get("offer_name", "Offer"),
            payout_amount=kwargs.get("payout_amount", "$0.00"),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_conversion_received: %s", exc)


@receiver(conversion_status_changed)
def on_conversion_status_changed(sender, **kwargs):
    new_status = kwargs.get("new_status", "")
    try:
        from .services_cpa import notify_conversion_rejected
        if new_status in ("rejected", "reversed", "chargeback"):
            notify_conversion_rejected(
                affiliate_id=kwargs.get("affiliate_id"),
                conversion_id=kwargs.get("conversion_id"),
                offer_name=kwargs.get("offer_name", "Offer"),
                payout_amount=kwargs.get("payout_amount", "$0.00"),
                reason=kwargs.get("reason", ""),
                tenant=kwargs.get("tenant"),
            )
    except Exception as exc:
        logger.error("on_conversion_status_changed: %s", exc)


@receiver(postback_failed)
def on_postback_failed(sender, **kwargs):
    try:
        from .services_cpa import notify_postback_failed
        notify_postback_failed(
            affiliate_id=kwargs.get("affiliate_id"),
            offer_id=kwargs.get("offer_id"),
            offer_name=kwargs.get("offer_name", "Offer"),
            error_detail=kwargs.get("error_detail", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_postback_failed: %s", exc)


@receiver(payout_processed)
def on_payout_processed(sender, **kwargs):
    try:
        from .services_cpa import notify_payout_processed
        notify_payout_processed(
            affiliate_id=kwargs.get("affiliate_id"),
            payout_id=kwargs.get("payout_id"),
            amount=kwargs.get("amount", "$0.00"),
            payment_method=kwargs.get("payment_method", ""),
            transaction_id=kwargs.get("transaction_id", ""),
            expected_date=kwargs.get("expected_date", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_payout_processed: %s", exc)


@receiver(payout_threshold_reached)
def on_payout_threshold_reached(sender, **kwargs):
    try:
        from .services_cpa import notify_payout_threshold_met
        notify_payout_threshold_met(
            affiliate_id=kwargs.get("affiliate_id"),
            current_balance=kwargs.get("current_balance", "$0.00"),
            threshold=kwargs.get("threshold", "$0.00"),
            next_payout_date=kwargs.get("next_payout_date", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_payout_threshold_reached: %s", exc)


@receiver(payout_on_hold)
def on_payout_on_hold(sender, **kwargs):
    try:
        from .services_cpa import notify_payout_on_hold
        notify_payout_on_hold(
            affiliate_id=kwargs.get("affiliate_id"),
            payout_id=kwargs.get("payout_id"),
            amount=kwargs.get("amount", "$0.00"),
            reason=kwargs.get("reason", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_payout_on_hold: %s", exc)


@receiver(affiliate_status_changed)
def on_affiliate_status_changed(sender, **kwargs):
    affiliate_id   = kwargs.get("affiliate_id")
    affiliate_name = kwargs.get("affiliate_name", "Affiliate")
    new_status     = kwargs.get("new_status", "")
    reason         = kwargs.get("reason", "")
    tenant         = kwargs.get("tenant")
    if not affiliate_id or not new_status:
        return
    try:
        from .services_cpa import notify_affiliate_approved, notify_affiliate_suspended
        if new_status == "approved":
            notify_affiliate_approved(
                affiliate_id=affiliate_id,
                affiliate_name=affiliate_name,
                manager_name=kwargs.get("manager_name", ""),
                welcome_bonus=kwargs.get("welcome_bonus", ""),
                tenant=tenant,
            )
        elif new_status in ("suspended", "banned"):
            notify_affiliate_suspended(
                affiliate_id=affiliate_id,
                reason=reason,
                duration=kwargs.get("duration", ""),
                tenant=tenant,
            )
    except Exception as exc:
        logger.error("on_affiliate_status_changed: %s", exc)


@receiver(manager_assigned)
def on_manager_assigned(sender, **kwargs):
    try:
        from .services_cpa import notify_manager_assigned
        notify_manager_assigned(
            affiliate_id=kwargs.get("affiliate_id"),
            manager_id=kwargs.get("manager_id"),
            manager_name=kwargs.get("manager_name", "Your Manager"),
            manager_email=kwargs.get("manager_email", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_manager_assigned: %s", exc)


@receiver(fraud_detected)
def on_fraud_detected(sender, **kwargs):
    try:
        from .services_cpa import notify_fraud_alert
        notify_fraud_alert(
            affiliate_id=kwargs.get("affiliate_id"),
            offer_id=kwargs.get("offer_id"),
            offer_name=kwargs.get("offer_name", "Offer"),
            details=kwargs.get("details", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_fraud_detected: %s", exc)


@receiver(milestone_reached)
def on_milestone_reached(sender, **kwargs):
    try:
        from .services_cpa import notify_milestone_reached
        notify_milestone_reached(
            affiliate_id=kwargs.get("affiliate_id"),
            milestone_type=kwargs.get("milestone_type", "custom"),
            milestone_value=kwargs.get("milestone_value", ""),
            reward=kwargs.get("reward", ""),
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_milestone_reached: %s", exc)


@receiver(epc_dropped)
def on_epc_dropped(sender, **kwargs):
    """Alert affiliate when their EPC drops more than 30%."""
    try:
        drop_percent = kwargs.get("drop_percent", 0)
        if drop_percent < 30:
            return
        from .services_cpa import _create_notification
        _create_notification(
            recipient_id=kwargs.get("affiliate_id"),
            notification_type="epc.drop",
            title=f"EPC Drop Alert: {kwargs.get('offer_name', 'Your Offer')}",
            body=(
                f"Your EPC dropped by {drop_percent:.0f}% on "
                f"\"{kwargs.get('offer_name', 'your offer')}\". "
                f"Old EPC: {kwargs.get('old_epc', 'N/A')} → "
                f"New EPC: {kwargs.get('new_epc', 'N/A')}. "
                f"Check your traffic quality."
            ),
            priority="HIGH",
            object_type="offer",
            object_id=str(kwargs.get("offer_id", "")),
            action_url="/stats/",
            action_label="View Stats",
            payload=kwargs,
            tenant=kwargs.get("tenant"),
        )
    except Exception as exc:
        logger.error("on_epc_dropped: %s", exc)
