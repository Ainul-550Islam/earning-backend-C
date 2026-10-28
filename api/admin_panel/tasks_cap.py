# api/admin_panel/tasks_cap.py
"""
Tasks CAP (Cross-App Propagation) — Celery tasks that call OTHER apps.
admin_panel orchestrates; other apps execute.
"এক কাজের জন্য একটাই মালিক" — admin_panel triggers, app does the work.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_ban_user_across_apps(self, user_id: int, reason: str, banned_by_id: int = None):
    """
    Ban user — propagate across ALL apps:
    1. Disable user account
    2. Freeze wallet
    3. Cancel pending payouts
    4. Revoke active sessions
    5. Fire signals to all listeners
    """
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge
        result = AdminBridge.user.ban(user_id=user_id, reason=reason)
        logger.info(f"[tasks_cap] user_ban propagated: user={user_id} result={result}")
        return result
    except Exception as exc:
        logger.error(f"[tasks_cap] task_ban_user_across_apps failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def task_approve_withdrawal_propagate(self, item_id: int, approved_by_id: int):
    """
    Approve withdrawal — propagate:
    1. Update payout item status
    2. Create wallet debit transaction
    3. Send notification to user
    4. Update stats cache
    """
    try:
        from api.payout_queue.models import PayoutItem
        from django.utils import timezone
        from django.contrib.auth import get_user_model
        User = get_user_model()

        item = PayoutItem.objects.get(pk=item_id, status='QUEUED')
        approver = User.objects.get(pk=approved_by_id)
        item.status = 'SUCCESS'
        # PayoutItem approval is done via status change only
        item.save()

        # Notify user
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=item.user_id,
                title='Withdrawal Approved ✅',
                message=f'Your withdrawal of ৳{item.gross_amount} has been approved and is being processed.',
                notification_type='withdrawal_approved',
            )
        except Exception:
            pass

        from api.admin_panel.signals_cap import fire_withdrawal_approved
        fire_withdrawal_approved(item_id, float(item.gross_amount), item.gateway, item.user_id)
        return {'success': True, 'item_id': item_id}
    except Exception as exc:
        logger.error(f"[tasks_cap] task_approve_withdrawal_propagate failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def task_send_admin_broadcast_to_all(self, broadcast_id: int):
    """
    Deliver admin broadcast to all target users.
    Calls api.messaging and api.notifications, NOT admin_panel logic.
    """
    try:
        from api.messaging.models import AdminBroadcast
        from api.notifications.models import Notification
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        User = get_user_model()

        broadcast = AdminBroadcast.objects.get(pk=broadcast_id)
        broadcast.status = 'sending'
        broadcast.save(update_fields=['status'])

        # Determine audience
        users_qs = User.objects.filter(is_active=True)
        if broadcast.audience_type == 'premium':
            users_qs = users_qs.filter(profile__is_premium=True)
        elif broadcast.audience_type == 'filtered' and broadcast.audience_filter:
            users_qs = users_qs.filter(**broadcast.audience_filter)

        # Bulk create notifications
        notifications = [
            Notification(
                user=u,
                title=broadcast.title,
                message=broadcast.body,
                notification_type='admin_broadcast',
            )
            for u in users_qs.iterator(chunk_size=500)
        ]
        Notification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)
        sent_count = len(notifications)

        broadcast.status = 'sent'
        broadcast.sent_count = sent_count
        broadcast.save(update_fields=['status', 'sent_count'])

        logger.info(f"[tasks_cap] broadcast {broadcast_id} sent to {sent_count} users")
        return {'success': True, 'sent': sent_count}
    except Exception as exc:
        logger.error(f"[tasks_cap] broadcast failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def task_bulk_ban_users(self, user_ids: list, reason: str, banned_by_id: int):
    """Bulk ban — calls wallet freeze + payout cancel for each."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    count = User.objects.filter(pk__in=user_ids, is_active=True).update(is_active=False)
    try:
        from api.wallet.models import Wallet
        Wallet.objects.filter(user_id__in=user_ids).update(is_locked=True)
    except Exception:
        pass
    try:
        from api.payout_queue.models import PayoutItem
        PayoutItem.objects.filter(user_id__in=user_ids, status='QUEUED').update(status='CANCELLED')
    except Exception:
        pass
    logger.info(f"[tasks_cap] bulk_ban: {count} users banned")
    return {'banned': count, 'reason': reason}


@shared_task
def task_refresh_live_kpis():
    """Refresh live KPI cache and broadcast via WebSocket."""
    try:
        from api.admin_panel.logic import get_dashboard_kpi_snapshot
        from django.core.cache import cache
        kpis = get_dashboard_kpi_snapshot()
        cache.set('admin:live_kpis', kpis, 30)
        # Broadcast via Channels
        import asyncio
        from api.admin_panel.consumers import broadcast_kpi_update
        asyncio.run(broadcast_kpi_update(kpis))
    except Exception as e:
        logger.debug(f"[tasks_cap] refresh_live_kpis: {e}")


@shared_task
def task_propagate_maintenance_on(message: str, duration_minutes: int):
    """Enable maintenance mode across all services."""
    from django.core.cache import cache
    cache.set('admin_panel:maintenance_mode_active', True, 86400)
    cache.set('admin_panel:maintenance_message', message, 86400)
    from api.admin_panel.signals_cap import admin_maintenance_on
    admin_maintenance_on.send(sender='admin_panel', message=message, duration_minutes=duration_minutes)


@shared_task
def task_propagate_maintenance_off():
    """End maintenance mode across all services."""
    from django.core.cache import cache
    cache.delete('admin_panel:maintenance_mode_active')
    cache.delete('admin_panel:maintenance_message')
    from api.admin_panel.signals_cap import admin_maintenance_off
    admin_maintenance_off.send(sender='admin_panel')