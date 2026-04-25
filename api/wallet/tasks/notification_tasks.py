# api/wallet/tasks/notification_tasks.py
import logging
from celery import shared_task

logger = logging.getLogger("wallet.tasks.notification")

@shared_task(bind=True, max_retries=3, name="wallet.dispatch_event_async")
def dispatch_event_async(self, event_json: str):
    """Process serialized event asynchronously (used by event_bus.publish_async)."""
    try:
        import json
        from ..event_bus import event_bus
        data = json.loads(event_json)
        event_type = data.pop("__event_type__", "")
        logger.info(f"Async event: {event_type}")
        return {"processed": True, "event": event_type}
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3, name="wallet.send_wallet_notification")
def send_wallet_notification(self, user_id: int, event_type: str, data: dict):
    """Send notification for a wallet event."""
    try:
        from ..notifications import WalletNotifier
        results = WalletNotifier.send(user_id=user_id, event_type=event_type, data=data)
        logger.info(f"Notification sent: user={user_id} event={event_type}")
        return results
    except Exception as e:
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True, max_retries=2, name="wallet.send_bulk_notifications")
def send_bulk_notifications(self, user_ids: list, event_type: str, data: dict):
    """Send notifications to multiple users."""
    try:
        from ..notifications import WalletNotifier
        sent = 0
        for uid in user_ids:
            try:
                WalletNotifier.send(uid, event_type, data)
                sent += 1
            except Exception:
                pass
        return {"sent": sent, "total": len(user_ids)}
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name="wallet.notify_bonus_expiring")
def notify_bonus_expiring(self):
    """Notify users about bonuses expiring in 48 hours."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        from ..models.balance import BalanceBonus
        from ..notifications import WalletNotifier

        soon = timezone.now() + timedelta(hours=48)
        expiring = BalanceBonus.objects.filter(
            status="active", expires_at__lte=soon, expires_at__gt=timezone.now()
        ).select_related("wallet__user")

        notified = 0
        for bonus in expiring:
            WalletNotifier.send(
                user_id=bonus.wallet.user_id,
                event_type="bonus_expiring",
                data={"amount": str(bonus.amount), "expires_at": str(bonus.expires_at)},
                channels=["in_app","push"]
            )
            notified += 1
        logger.info(f"Bonus expiry notifications sent: {notified}")
        return {"notified": notified}
    except Exception as e:
        logger.error(f"Bonus expiry notify error: {e}")
        return {"error": str(e)}
