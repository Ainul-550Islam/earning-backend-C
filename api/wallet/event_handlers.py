# api/wallet/event_handlers.py
"""
Event handler registrations.
All handlers are registered here — imported once in apps.py ready().

This is the central hub: event_bus.subscribe() for every domain event.
"""
import logging
from decimal import Decimal
from .event_bus import event_bus
from .events import (
    WalletCreated, WalletCredited, WalletDebited,
    WalletLocked, WithdrawalRequested, WithdrawalCompleted,
    WithdrawalFailed, EarningAdded, BonusGranted, BonusExpired,
    StreakMilestone, ReferralCommissionPaid, KYCApproved,
    FraudDetected, AMLFlagged, PublisherLevelUpgraded,
    OfferConverted, DailyPayoutProcessed, DisputeOpened,
    TransferCompleted,
)

logger = logging.getLogger("wallet.event_handlers")


# ── Notification handlers ─────────────────────────────────

@event_bus.subscribe(WalletCredited)
def notify_on_credit(event: WalletCredited):
    """Send push notification when wallet is credited."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="wallet_credited",
            data={
                "amount": str(event.amount),
                "balance_after": str(event.balance_after),
                "type": event.txn_type,
                "description": event.description,
            }
        )
    except Exception as e:
        logger.debug(f"notify_on_credit skip: {e}")


@event_bus.subscribe(WithdrawalRequested)
def notify_on_withdrawal_request(event: WithdrawalRequested):
    """Notify user withdrawal is pending."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="withdrawal_requested",
            data={"amount": str(event.amount), "net_amount": str(event.net_amount), "gateway": event.gateway}
        )
    except Exception as e:
        logger.debug(f"notify_on_withdrawal_request skip: {e}")


@event_bus.subscribe(WithdrawalCompleted)
def notify_on_withdrawal_complete(event: WithdrawalCompleted):
    """Notify user withdrawal is complete."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="withdrawal_completed",
            data={"amount": str(event.amount), "gateway_ref": event.gateway_ref}
        )
    except Exception as e:
        logger.debug(f"notify_on_withdrawal_complete skip: {e}")


@event_bus.subscribe(WithdrawalFailed)
def notify_on_withdrawal_failed(event: WithdrawalFailed):
    """Notify user withdrawal failed."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="withdrawal_failed",
            data={"amount": str(event.amount), "error": event.error}
        )
    except Exception as e:
        logger.debug(f"notify_on_withdrawal_failed skip: {e}")


@event_bus.subscribe(StreakMilestone)
def notify_on_streak(event: StreakMilestone):
    """Celebrate streak milestone."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="streak_milestone",
            data={"days": event.streak_days, "bonus": str(event.bonus_amount)}
        )
    except Exception as e:
        logger.debug(f"notify_on_streak skip: {e}")


@event_bus.subscribe(KYCApproved)
def notify_on_kyc_approved(event: KYCApproved):
    """Notify KYC approval + new withdrawal limit."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="kyc_approved",
            data={"level": event.level, "new_daily_limit": str(event.new_daily_limit)}
        )
    except Exception as e:
        logger.debug(f"notify_on_kyc_approved skip: {e}")


@event_bus.subscribe(PublisherLevelUpgraded)
def notify_on_level_upgrade(event: PublisherLevelUpgraded):
    """Notify CPAlead publisher level upgrade."""
    try:
        from .notifications import WalletNotifier
        WalletNotifier.send(
            user_id=event.user_id,
            event_type="publisher_level_upgraded",
            data={"old_level": event.old_level, "new_level": event.new_level,
                  "new_payout_freq": event.new_payout_freq}
        )
    except Exception as e:
        logger.debug(f"notify_on_level_upgrade skip: {e}")


# ── Cache invalidation handlers ───────────────────────────

@event_bus.subscribe(WalletCredited)
def invalidate_cache_on_credit(event: WalletCredited):
    try:
        from .cache_manager import WalletCacheManager
        WalletCacheManager.invalidate_wallet(event.wallet_id)
    except Exception as e:
        logger.debug(f"cache invalidate skip: {e}")


@event_bus.subscribe(WalletDebited)
def invalidate_cache_on_debit(event: WalletDebited):
    try:
        from .cache_manager import WalletCacheManager
        WalletCacheManager.invalidate_wallet(event.wallet_id)
    except Exception as e:
        logger.debug(f"cache invalidate skip: {e}")


# ── Audit log handlers ────────────────────────────────────

@event_bus.subscribe(WalletLocked)
def audit_wallet_locked(event: WalletLocked):
    try:
        from .audit_log import AuditLogger
        AuditLogger.log(
            action="wallet_locked", user_id=event.user_id,
            target_id=event.wallet_id, detail=f"Reason: {event.reason}"
        )
    except Exception as e:
        logger.debug(f"audit_wallet_locked skip: {e}")


@event_bus.subscribe(FraudDetected)
def audit_fraud_detected(event: FraudDetected):
    try:
        from .audit_log import AuditLogger
        AuditLogger.log(
            action="fraud_detected", user_id=event.user_id,
            target_id=event.wallet_id,
            detail=f"Score={event.score} signals={event.signals}"
        )
    except Exception as e:
        logger.debug(f"audit_fraud skip: {e}")


# ── Webhook delivery handlers ─────────────────────────────

@event_bus.subscribe(WalletCredited)
def deliver_webhook_on_credit(event: WalletCredited):
    try:
        from .services_extra import WebhookDeliveryService
        WebhookDeliveryService.fire_event(
            "wallet.credited",
            {"wallet_id": event.wallet_id, "amount": str(event.amount), "txn_id": event.txn_id}
        )
    except Exception as e:
        logger.debug(f"webhook delivery skip: {e}")


@event_bus.subscribe(WithdrawalCompleted)
def deliver_webhook_on_withdrawal(event: WithdrawalCompleted):
    try:
        from .services_extra import WebhookDeliveryService
        WebhookDeliveryService.fire_event(
            "withdrawal.completed",
            {"withdrawal_id": event.withdrawal_id, "amount": str(event.amount)}
        )
    except Exception as e:
        logger.debug(f"webhook delivery skip: {e}")
