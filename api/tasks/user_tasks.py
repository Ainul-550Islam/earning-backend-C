"""
tasks/user_tasks.py
Migrated from api/users/tasks.py — api/tasks/ is the single owner of all Celery tasks.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_otp_email(email, otp_code):
    """Send OTP email to user"""
    subject = 'Your OTP Code'
    message = f'Your OTP code is: {otp_code}. It will expire in 10 minutes.'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


@shared_task
def send_welcome_email(email, username):
    """Send welcome email to new user"""
    subject = 'Welcome to Earnify'
    message = f'Hi {username},\n\nWelcome to Earnify! Start earning today.'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


@shared_task
def cleanup_expired_otps():
    """Delete expired OTPs"""
    from django.utils import timezone
    from .models import OTP
    
    expired_otps = OTP.objects.filter(expires_at__lt=timezone.now())
    count = expired_otps.count()
    expired_otps.delete()
    return f'Deleted {count} expired OTPs'

# ── Extended user tasks (migrated + new) ──────────────────────────────────

from celery import shared_task as _st
from django.utils import timezone as _tz
from django.core.cache import cache as _cache
import logging as _log

_logger = _log.getLogger(__name__)


@_st(bind=True, max_retries=3, default_retry_delay=30,
     name='tasks.user_tasks.update_user_profile_cache')
def update_user_profile_cache(self, user_id: int) -> dict:
    """Refresh all cached user profile data after profile update."""
    try:
        from api.tasks.data_pipeline_tasks import sync_user_data_bridge
        sync_user_data_bridge.apply_async(kwargs={'user_ids': [user_id]})
        return {'status': 'success', 'user_id': user_id}
    except Exception as exc:
        raise self.retry(exc=exc)


@_st(bind=True, max_retries=2, default_retry_delay=30,
     name='tasks.user_tasks.deactivate_user')
def deactivate_user(self, user_id: int, reason: str = '') -> dict:
    """Deactivate a user account and clean up their sessions."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=user_id).update(is_active=False)
        _cache.set(f'user_suspended_{user_id}', True, timeout=None)
        _cache.delete(f'session_user_{user_id}')
        _logger.info(f"[USER] Deactivated user {user_id}: {reason}")
        return {'status': 'success', 'user_id': user_id, 'reason': reason}
    except Exception as exc:
        raise self.retry(exc=exc)


@_st(bind=True, max_retries=2, default_retry_delay=30,
     name='tasks.user_tasks.reactivate_user')
def reactivate_user(self, user_id: int) -> dict:
    """Reactivate a previously deactivated user account."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=user_id).update(is_active=True)
        _cache.delete(f'user_suspended_{user_id}')
        return {'status': 'success', 'user_id': user_id}
    except Exception as exc:
        raise self.retry(exc=exc)


@_st(bind=True, max_retries=2, default_retry_delay=30,
     name='tasks.user_tasks.send_password_reset_email')
def send_password_reset_email(self, user_id: int, reset_token: str) -> dict:
    """Send password reset email to user."""
    try:
        from django.contrib.auth import get_user_model
        from django.core.mail import send_mail
        from django.conf import settings
        User = get_user_model()
        user  = User.objects.filter(pk=user_id).first()
        if not user:
            return {'status': 'user_not_found'}
        reset_url = f"{getattr(settings, 'FRONTEND_URL', '')}/reset-password/{reset_token}/"
        send_mail(
            subject='Reset Your Password',
            message=f'Hi {user.username},\n\nClick to reset: {reset_url}\n\nExpires in 1 hour.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        return {'status': 'success', 'user_id': user_id}
    except Exception as exc:
        raise self.retry(exc=exc)


@_st(bind=True, max_retries=2, default_retry_delay=30,
     name='tasks.user_tasks.bulk_update_user_segments')
def bulk_update_user_segments(self) -> dict:
    """Bulk update all user segments from ML task results."""
    try:
        from api.tasks.ml_tasks import compute_user_segments
        return compute_user_segments.apply().get()
    except Exception as exc:
        raise self.retry(exc=exc)
