# api/cms/tasks/notification_tasks.py
"""Notification and email sending tasks."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.send_notification', bind=True, max_retries=3)
def send_notification(self, user_id: int, notification_type: str, title: str, message: str,
                      reward_amount=None, reward_currency='USD', source_type='', source_id=None,
                      action_url='', metadata=None):
    """Send in-app notification to a user."""
    try:
        from django.contrib.auth import get_user_model
        from api.cms.services_new.NotificationService import NotificationService
        User = get_user_model()
        user = User.objects.get(id=user_id)
        notif = NotificationService.notify_user(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            reward_amount=reward_amount,
            reward_currency=reward_currency,
            source_type=source_type,
            source_id=source_id,
            action_url=action_url,
            metadata=metadata or {},
        )
        logger.info(f"[Task] Notification sent to user {user_id}: {notification_type}")
        return {'status': 'success', 'notification_id': notif.id if notif else None}
    except Exception as exc:
        logger.error(f"[Task] Notification failed for user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.broadcast_announcement', bind=True)
def broadcast_announcement_task(self, announcement_id: int):
    """Broadcast announcement to all active users."""
    try:
        from api.cms.models_new.extras import Announcement
        from api.cms.services_new.NotificationService import NotificationService
        announcement = Announcement.objects.get(id=announcement_id)
        count = NotificationService.broadcast_announcement(announcement)
        logger.info(f"[Task] Broadcast announcement {announcement_id} to {count} users")
        return {'status': 'success', 'notified': count}
    except Exception as exc:
        logger.error(f"[Task] Broadcast failed for announcement {announcement_id}: {exc}")
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='cms.tasks.cleanup_old_notifications', bind=True)
def cleanup_old_notifications(self, days: int = 90):
    """Delete old read notifications."""
    try:
        from api.cms.services_new.NotificationService import NotificationService
        deleted = NotificationService.delete_old_notifications(days=days)
        logger.info(f"[Task] Deleted {deleted} old notifications")
        return {'status': 'success', 'deleted': deleted}
    except Exception as exc:
        logger.error(f"[Task] Notification cleanup failed: {exc}")
        raise


@shared_task(name='cms.tasks.send_email_template', bind=True, max_retries=3)
def send_email_template(self, template_name: str, recipient_email: str,
                        recipient_name: str = '', context: dict = None):
    """Send an email using a stored EmailTemplate."""
    try:
        from api.cms.models_new.extras import EmailTemplate
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        template = EmailTemplate.objects.get(name=template_name, is_active=True)
        ctx = context or {}
        ctx.setdefault('recipient_name', recipient_name)

        subject, html_body, text_body = template.render(ctx)
        from_email = template.from_email or settings.DEFAULT_FROM_EMAIL
        from_name = template.from_name or settings.DEFAULT_FROM_EMAIL

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body or '',
            from_email=f"{from_name} <{from_email}>",
            to=[recipient_email],
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        if template.reply_to:
            msg.reply_to = [template.reply_to]

        msg.send()
        template.increment_send_count()
        logger.info(f"[Task] Email '{template_name}' sent to {recipient_email}")
        return {'status': 'success', 'template': template_name, 'to': recipient_email}
    except Exception as exc:
        logger.error(f"[Task] Email send failed '{template_name}' to {recipient_email}: {exc}")
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='cms.tasks.process_daily_earning_rewards', bind=True)
def process_daily_earning_rewards(self):
    """
    Process pending earning rewards daily.
    CPAlead pattern: batch process rewards that need settlement.
    """
    try:
        from django.utils import timezone
        logger.info(f"[Task] Processing daily earning rewards at {timezone.now()}")
        # Placeholder — implement based on wallet model
        return {'status': 'success', 'processed': 0}
    except Exception as exc:
        logger.error(f"[Task] Daily reward processing failed: {exc}")
        raise


@shared_task(name='cms.tasks.daily_earning_cap_reset', bind=True)
def daily_earning_cap_reset(self):
    """Reset daily earning caps at midnight (caches auto-expire but log it)."""
    try:
        from api.cms.services_new.CPALeadService import EarningCapService
        EarningCapService.reset_daily_caps()
        logger.info("[Task] Daily earning caps reset")
        return {'status': 'success'}
    except Exception as exc:
        logger.error(f"[Task] Daily cap reset failed: {exc}")
        raise


@shared_task(name='cms.tasks.cpalead_sync', bind=True)
def cpalead_sync(self):
    """
    Sync CPAlead campaign data.
    Placeholder — implement when CPAlead API access is configured.
    """
    try:
        logger.info("[Task] CPAlead sync started")
        # Sync CPAlead campaigns: fetches latest offer feed and updates OfferCache
        from api.cms.services_new.CPALeadService import CPALeadService
        offers = CPALeadService.fetch_offers()
        return {'status': 'success', 'synced': len(offers)}
    except Exception as exc:
        logger.error(f"[Task] CPAlead sync failed: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.cleanup_expired_popup_dismissals', bind=True)
def cleanup_expired_popup_dismissals(self):
    """Remove expired popup dismissal records."""
    try:
        from api.cms.models_new.extras import PopupDismissal
        from django.utils import timezone
        deleted, _ = PopupDismissal.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        logger.info(f"[Task] Deleted {deleted} expired popup dismissals")
        return {'status': 'success', 'deleted': deleted}
    except Exception as exc:
        logger.error(f"[Task] Popup dismissal cleanup failed: {exc}")
        raise


@shared_task(name='cms.tasks.send_welcome_email', bind=True, max_retries=2)
def send_welcome_email_task(self, user_id: int, referral_bonus: float = 0):
    """Send welcome email to new user."""
    try:
        from django.contrib.auth import get_user_model
        from api.cms.email_service import CMSEmailService
        user = get_user_model().objects.get(id=user_id)
        CMSEmailService.send_welcome(user, referral_bonus=referral_bonus)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='cms.tasks.send_withdrawal_email', bind=True, max_retries=3)
def send_withdrawal_email_task(self, user_id: int, amount: float,
                                method: str, status: str, reference: str = ''):
    """Send withdrawal status email."""
    try:
        from django.contrib.auth import get_user_model
        from api.cms.email_service import CMSEmailService
        user = get_user_model().objects.get(id=user_id)
        CMSEmailService.send_withdrawal_update(user, amount, method, status, reference)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.send_reward_email', bind=True, max_retries=2)
def send_reward_email_task(self, user_id: int, coins: float,
                            usd_value: float, source: str = 'Offer'):
    """Send reward earned email."""
    try:
        from django.contrib.auth import get_user_model
        from api.cms.email_service import CMSEmailService
        user = get_user_model().objects.get(id=user_id)
        CMSEmailService.send_reward_earned(user, coins, usd_value, source)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
