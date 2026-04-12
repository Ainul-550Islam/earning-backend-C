# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
signals.py: Django signal receivers for automatic webhook event emission.

Connects to:
  - api.wallet.WalletTransaction  -> payout.* / wallet.* events
  - api.wallet.WithdrawalRequest  -> payout.pending / success / failed
  - api.users.User                -> user.registered / user.suspended
  - Custom platform signals       -> fraud / kyc / offer events

All dispatch calls are async via Celery dispatch_event.delay()
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

logger = logging.getLogger("ainul.webhooks")

# Custom platform signals — fire these from your business logic
fraud_detected        = Signal()   # kwargs: user_id, reason, ip, tenant_id
kyc_status_changed    = Signal()   # kwargs: user_id, new_status, tenant_id
offer_credited_signal = Signal()   # kwargs: user_id, offer_id, amount, tenant_id


def _emit_async(event_type, payload, tenant_id=None):
    """Ainul Enterprise Engine — Queue a webhook dispatch safely."""
    try:
        from .tasks import dispatch_event
        dispatch_event.delay(event_type=event_type, payload=payload, tenant_id=tenant_id)
        logger.debug("Queued webhook event=%s", event_type)
    except Exception as exc:
        logger.error("Failed to queue webhook event=%s: %s", event_type, exc, exc_info=True)


@receiver(post_save, sender="wallet.WalletTransaction")
def on_wallet_transaction_saved(sender, instance, created, **kwargs):
    """Ainul Enterprise Engine — wallet.*/payout.* events from WalletTransaction."""
    from .constants import EventType
    if not created:
        return
    tx_type = getattr(instance, "transaction_type", None)
    tx_status = getattr(instance, "status", None)
    payload = {
        "transaction_id": str(getattr(instance, "walletTransaction_id", instance.pk)),
        "user_id":        str(getattr(instance, "user_id", "")),
        "amount":         str(getattr(instance, "amount", 0)),
        "type":           tx_type,
    }
    tenant_id = getattr(instance, "tenant_id", None)
    if tx_type == "withdrawal":
        event_map = {
            "completed": EventType.PAYOUT_SUCCESS,
            "rejected":  EventType.PAYOUT_FAILED,
            "reversed":  EventType.PAYOUT_REVERSED,
            "pending":   EventType.PAYOUT_PENDING,
        }
        event = event_map.get(tx_status)
        if event:
            _emit_async(event, {**payload, "status": tx_status}, tenant_id)
    elif tx_type in {"earning", "reward", "referral", "bonus", "admin_credit", "unfreeze"}:
        _emit_async(EventType.WALLET_CREDITED, payload, tenant_id)
    elif tx_type == "freeze":
        _emit_async(EventType.WALLET_FROZEN, payload, tenant_id)
    elif tx_type in {"admin_debit", "withdrawal_fee", "reversal"}:
        _emit_async(EventType.WALLET_DEBITED, payload, tenant_id)


@receiver(post_save, sender="wallet.WithdrawalRequest")
def on_withdrawal_request_saved(sender, instance, created, **kwargs):
    """Ainul Enterprise Engine — payout.pending/success/failed from WithdrawalRequest."""
    from .constants import EventType
    payload = {
        "withdrawal_id": str(instance.pk),
        "user_id":       str(getattr(instance, "user_id", "")),
        "amount":        str(getattr(instance, "amount", 0)),
    }
    tenant_id = getattr(instance, "tenant_id", None)
    if created:
        _emit_async(EventType.PAYOUT_PENDING, payload, tenant_id)
    else:
        status_map = {
            "approved":  EventType.PAYOUT_SUCCESS,
            "completed": EventType.PAYOUT_SUCCESS,
            "rejected":  EventType.PAYOUT_FAILED,
        }
        event = status_map.get(getattr(instance, "status", None))
        if event:
            _emit_async(event, payload, tenant_id)


@receiver(post_save, sender="users.User")
def on_user_saved(sender, instance, created, **kwargs):
    """Ainul Enterprise Engine — user.registered / user.suspended events."""
    from .constants import EventType
    payload = {"user_id": str(instance.pk), "email": instance.email}
    if created:
        _emit_async(EventType.USER_REGISTERED, payload)
    elif not instance.is_active:
        _emit_async(EventType.USER_SUSPENDED, payload)


@receiver(fraud_detected)
def on_fraud_detected(sender, user_id, reason, tenant_id=None, ip=None, **kwargs):
    """Ainul Enterprise Engine — fraud.alert_raised webhook.
    Usage: fraud_detected.send(sender=None, user_id=..., reason=..., ip=...)
    """
    from .constants import EventType
    _emit_async(
        EventType.FRAUD_ALERT_RAISED,
        {"user_id": str(user_id), "reason": reason, "ip": ip or ""},
        tenant_id,
    )


@receiver(kyc_status_changed)
def on_kyc_status_changed(sender, user_id, new_status, tenant_id=None, **kwargs):
    """Ainul Enterprise Engine — kyc.* webhooks.
    Usage: kyc_status_changed.send(sender=None, user_id=..., new_status="approved")
    """
    from .constants import EventType
    event_map = {
        "submitted": EventType.KYC_SUBMITTED,
        "approved":  EventType.KYC_APPROVED,
        "rejected":  EventType.KYC_REJECTED,
    }
    event = event_map.get(new_status)
    if event:
        _emit_async(event, {"user_id": str(user_id), "kyc_status": new_status}, tenant_id)


@receiver(offer_credited_signal)
def on_offer_credited(sender, user_id, offer_id, amount, tenant_id=None, **kwargs):
    """Ainul Enterprise Engine — offer.credited webhook.
    Usage: offer_credited_signal.send(sender=None, user_id=..., offer_id=..., amount=...)
    """
    from .constants import EventType
    _emit_async(
        EventType.OFFER_CREDITED,
        {"user_id": str(user_id), "offer_id": str(offer_id), "amount": str(amount)},
        tenant_id,
    )
