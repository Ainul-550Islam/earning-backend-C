# earning_backend/api/notifications/admin_2fa.py
"""
Admin 2FA — Two-factor authentication for high-risk notification admin actions.

Protects:
  - Bulk send to > 10,000 users
  - Campaign start (> 5,000 users)
  - Admin broadcast (all users)
  - Token/key rotation

Usage:
    from notifications.admin_2fa import require_admin_2fa

    @require_admin_2fa(threshold=10000)
    def bulk_send_view(request):
        ...
"""
import functools
import logging
import time
from typing import Optional
from django.core.cache import cache
from django.http import JsonResponse
logger = logging.getLogger(__name__)


def generate_totp_code(secret: str, window: int = 30) -> str:
    """Generate a 6-digit TOTP code."""
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.now()
    except ImportError:
        # Fallback: time-based 6-digit code without pyotp
        import hashlib, struct
        t = int(time.time()) // window
        msg = struct.pack('>Q', t)
        h = hashlib.new('sha1', (secret + str(t)).encode())
        code = int(h.hexdigest()[:6], 16) % 1000000
        return str(code).zfill(6)


def verify_totp_code(secret: str, code: str, window: int = 30) -> bool:
    """Verify a 6-digit TOTP code."""
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    except ImportError:
        expected = generate_totp_code(secret, window)
        return code == expected


def send_2fa_code_to_admin(admin_user) -> bool:
    """Send 2FA code to admin via in-app notification."""
    try:
        from django.conf import settings
        secret = getattr(settings, 'NOTIFICATION_ADMIN_2FA_SECRET', settings.SECRET_KEY[:32])
        code = generate_totp_code(secret)
        cache_key = f'admin_2fa:{admin_user.pk}'
        cache.set(cache_key, code, 300)  # Valid for 5 minutes

        from notifications.services.NotificationService import notification_service
        notification_service.create_notification(
            user=admin_user,
            title='🔐 Admin 2FA Code',
            message=f'Your admin verification code: {code}. Valid for 5 minutes.',
            notification_type='two_factor_code',
            channel='in_app',
            priority='critical',
        )
        return True
    except Exception as exc:
        logger.error(f'send_2fa_code_to_admin: {exc}')
        return False


def verify_admin_2fa(admin_user, submitted_code: str) -> bool:
    """Verify admin submitted the correct 2FA code."""
    cache_key = f'admin_2fa:{admin_user.pk}'
    stored_code = cache.get(cache_key)
    if stored_code and str(stored_code) == str(submitted_code):
        cache.delete(cache_key)  # One-time use
        return True
    # Also try TOTP
    from django.conf import settings
    secret = getattr(settings, 'NOTIFICATION_ADMIN_2FA_SECRET', settings.SECRET_KEY[:32])
    return verify_totp_code(secret, submitted_code)


def require_admin_2fa(threshold: int = 10000, action: str = 'bulk_send'):
    """
    Decorator that requires 2FA for admin actions affecting >= threshold users.

    The view must:
    1. Check user_count in request.data
    2. If >= threshold, send 2FA code and return 403 with {'2fa_required': True}
    3. On re-submit with {'2fa_code': 'XXXXXX'}, verify and proceed
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_staff:
                return JsonResponse({'error': 'Staff only'}, status=403)

            user_count = int(request.data.get('user_count', 0) if hasattr(request, 'data') else 0)
            submitted_code = request.data.get('2fa_code', '') if hasattr(request, 'data') else ''

            if user_count >= threshold:
                if not submitted_code:
                    # Send 2FA code and ask for verification
                    sent = send_2fa_code_to_admin(request.user)
                    return JsonResponse({
                        '2fa_required': True,
                        'action': action,
                        'user_count': user_count,
                        'threshold': threshold,
                        'message': f'This action affects {user_count} users and requires 2FA. Check your notifications for the code.',
                        'code_sent': sent,
                    }, status=202)

                if not verify_admin_2fa(request.user, submitted_code):
                    return JsonResponse({'error': 'Invalid 2FA code.', '2fa_required': True}, status=403)

            return func(request, *args, **kwargs)
        return wrapper
    return decorator
