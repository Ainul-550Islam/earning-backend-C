# api/support/context_processors.py
"""
Django context processors for support system.
Inject support data into template context.
Full code — no summarizing.
"""
import logging
logger = logging.getLogger(__name__)


def support_settings(request):
    """
    Inject support settings into every template context.
    Usage: {{ support.is_support_online }}, {{ support.chat_widget_enabled }}
    """
    try:
        from django.core.cache import cache
        cached = cache.get('support:ctx:settings')
        if cached:
            return {'support': cached}

        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        ctx = {
            'is_support_online':   obj.is_support_online,
            'maintenance_mode':    obj.maintenance_mode,
            'maintenance_message': obj.maintenance_message,
            'chat_widget_enabled': obj.chat_widget_enabled,
            'chat_widget_color':   obj.chat_widget_color,
            'chat_bot_enabled':    obj.chat_bot_enabled,
            'telegram_group':      obj.telegram_group,
            'whatsapp_number':     obj.whatsapp_number,
            'facebook_page':       obj.facebook_page,
            'email_support':       obj.email_support,
        }
        cache.set('support:ctx:settings', ctx, timeout=120)
        return {'support': ctx}
    except Exception as e:
        logger.debug(f'support_settings context_processor: {e}')
        return {'support': {}}


def user_ticket_count(request):
    """
    Inject authenticated user open ticket count.
    Usage: {{ user_open_tickets }}
    """
    if not request.user.is_authenticated:
        return {'user_open_tickets': 0}
    try:
        from django.core.cache import cache
        key    = f'support:ctx:tickets:{request.user.id}'
        cached = cache.get(key)
        if cached is not None:
            return {'user_open_tickets': cached}
        from api.support.models import SupportTicket
        count  = SupportTicket.objects.filter(
            user=request.user,
            status__in=['open', 'in_progress', 'waiting_user']
        ).count()
        cache.set(key, count, timeout=60)
        return {'user_open_tickets': count}
    except Exception:
        return {'user_open_tickets': 0}


def active_announcements(request):
    """
    Inject active network announcements.
    Usage: {% for ann in active_announcements %}
    """
    try:
        from django.core.cache import cache
        key    = 'support:ctx:announcements'
        cached = cache.get(key)
        if cached is not None:
            return {'active_announcements': cached}
        from django.utils import timezone
        from django.db.models import Q
        from api.support.models import NetworkAnnouncement
        now  = timezone.now()
        anns = list(NetworkAnnouncement.objects.filter(
            is_active=True, show_in_portal=True
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now)
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now)
        ).values('id', 'title', 'content', 'ann_type')[:5])
        cache.set(key, anns, timeout=300)
        return {'active_announcements': anns}
    except Exception:
        return {'active_announcements': []}