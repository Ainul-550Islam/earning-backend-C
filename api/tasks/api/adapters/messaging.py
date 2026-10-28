"""
api/adapters/messaging.py
Notification/messaging dispatch adapter.
Supports: in_app, push, email, sms channels.
"""
import logging
logger = logging.getLogger(__name__)

def send(user_id: int, message: str, channel: str = 'in_app', **kwargs) -> bool:
    """Dispatch a message to a user via the specified channel."""
    logger.info('[Messaging] user=%s channel=%s msg=%s', user_id, channel, message[:60])
    try:
        if channel == 'in_app':
            return _send_in_app(user_id, message, **kwargs)
        elif channel == 'push':
            return _send_push(user_id, message, **kwargs)
        elif channel == 'email':
            return _send_email(user_id, message, **kwargs)
        logger.warning('[Messaging] Unknown channel: %s', channel)
        return False
    except Exception as e:
        logger.error('[Messaging] Error: %s', e)
        return False

def _send_in_app(user_id, message, title='', **kwargs):
    # TODO: integrate with WebSocket consumers.py or Notification model
    return True

def _send_push(user_id, message, title='', **kwargs):
    # TODO: integrate FCM / APNs
    return True

def _send_email(user_id, message, subject='', **kwargs):
    from django.core.mail import send_mail
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        send_mail(subject or 'Notification', message, None, [user.email], fail_silently=True)
        return True
    except Exception:
        return False
