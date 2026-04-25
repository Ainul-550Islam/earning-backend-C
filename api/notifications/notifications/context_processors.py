# earning_backend/api/notifications/context_processors.py
"""
Context Processors — Django template context processors for notifications.
Injects notification data into every template context automatically.

Add to settings.py TEMPLATES[0]['OPTIONS']['context_processors']:
    'api.notifications.context_processors.notification_context',
"""
import logging
logger = logging.getLogger(__name__)


def notification_context(request):
    """
    Inject notification data into all Django template contexts.

    Provides:
        UNREAD_COUNT          — number of unread notifications
        NOTIFICATION_ENABLED  — True if notifications are enabled for user
        NOTIFICATION_CHANNELS — list of opted-in channels
        HAS_PUSH_DEVICE       — True if user has a registered push device
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'UNREAD_COUNT': 0,
            'NOTIFICATION_ENABLED': False,
            'NOTIFICATION_CHANNELS': [],
            'HAS_PUSH_DEVICE': False,
        }

    try:
        from django.core.cache import cache
        user_id = request.user.pk
        cache_key = f'notif:ctx:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from notifications.models import Notification, DeviceToken, NotificationPreference
        from notifications.models.analytics import OptOutTracking

        unread = Notification.objects.filter(
            user=request.user, is_read=False, is_deleted=False
        ).count()

        has_device = DeviceToken.objects.filter(user=request.user, is_active=True).exists()

        opted_out = list(
            OptOutTracking.objects.filter(user=request.user, is_active=True)
            .values_list('channel', flat=True)
        )
        all_channels = ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
        active_channels = [c for c in all_channels if c not in opted_out]

        ctx = {
            'UNREAD_COUNT': unread,
            'NOTIFICATION_ENABLED': True,
            'NOTIFICATION_CHANNELS': active_channels,
            'HAS_PUSH_DEVICE': has_device,
        }
        cache.set(cache_key, ctx, 60)  # Cache for 1 minute
        return ctx

    except Exception as exc:
        logger.debug(f'notification_context: {exc}')
        return {
            'UNREAD_COUNT': 0,
            'NOTIFICATION_ENABLED': True,
            'NOTIFICATION_CHANNELS': ['in_app'],
            'HAS_PUSH_DEVICE': False,
        }
