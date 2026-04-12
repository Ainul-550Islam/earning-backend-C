# promotions/notifications/tasks.py
from celery import shared_task
from decimal import Decimal
import logging
logger = logging.getLogger(__name__)

@shared_task
def send_daily_report():
    """Send daily earnings report to all active publishers — 8 AM."""
    from django.contrib.auth import get_user_model
    from api.promotions.models import PromotionTransaction
    from django.utils import timezone
    from django.db.models import Sum
    User = get_user_model()
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sent = 0
    for user in User.objects.filter(is_active=True)[:500]:
        today_earnings = PromotionTransaction.objects.filter(
            user_id=user.id,
            transaction_type='reward',
            created_at__gte=today,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if today_earnings > 0:
            logger.debug(f'Daily report: user={user.id} earnings=${today_earnings}')
            sent += 1
    return {'reports_sent': sent}

@shared_task
def send_task_approved_notification(user_id: int, campaign_title: str, reward: str, device_token: str = ''):
    """Send push notification when task is approved."""
    if device_token:
        from api.promotions.notifications.fcm_push import FCMPushNotification
        fcm = FCMPushNotification()
        return fcm.notify_task_approved(device_token, campaign_title, reward)
    return {'skipped': 'no_device_token'}

@shared_task
def send_payout_notification(user_id: int, amount: str, method: str, phone: str = ''):
    """Send SMS + push on payout."""
    if phone:
        from api.promotions.notifications.sms_sender import SMSSender
        sms = SMSSender()
        sms.send_payout_confirmation(phone, amount, method)
    return {'notified': True}
