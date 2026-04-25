# api/wallet/tasks/withdrawal_reminder_tasks.py
"""
Remind admins and users about pending withdrawal states.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.reminder")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.send_withdrawal_reminders")
def send_withdrawal_reminders(self, hours: int = 24):
    """
    Send reminders for:
      - Users with withdrawals pending > 24h (user notification)
      - Admins for unapproved withdrawals > 12h (admin alert)
    Runs every 6 hours.
    """
    try:
        from ..models import WithdrawalRequest

        cutoff_24h = timezone.now() - timedelta(hours=hours)
        cutoff_12h = timezone.now() - timedelta(hours=12)

        # User reminders — pending > 24h
        pending_long = WithdrawalRequest.objects.filter(
            status="pending",
            created_at__lt=cutoff_24h,
        ).select_related("user","wallet")

        user_reminders = 0
        for wr in pending_long:
            try:
                logger.info(f"Reminder: user={wr.user.username} wr={wr.withdrawal_id} pending>{hours}h")
                # TODO: send push/email notification
                user_reminders += 1
            except Exception as e:
                logger.debug(f"User reminder skip: {e}")

        # Admin alert — unapproved > 12h
        admin_alerts = WithdrawalRequest.objects.filter(
            status="pending",
            created_at__lt=cutoff_12h,
        ).count()

        if admin_alerts:
            logger.warning(f"ADMIN ALERT: {admin_alerts} withdrawals pending >12h without approval")

        return {"user_reminders": user_reminders, "admin_alerts": admin_alerts}
    except Exception as e:
        raise self.retry(exc=e)
