# api/support/templatetags/support_tags.py
"""
Django template tags and filters for support system.
Usage: {% load support_tags %}
"""
from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def ticket_status_badge(status: str) -> str:
    """Render status as HTML badge."""
    badges = {
        'open':         '<span class="badge badge-warning">Open</span>',
        'in_progress':  '<span class="badge badge-info">In Progress</span>',
        'waiting_user': '<span class="badge badge-secondary">Waiting</span>',
        'resolved':     '<span class="badge badge-success">Resolved</span>',
        'closed':       '<span class="badge badge-dark">Closed</span>',
        'spam':         '<span class="badge badge-danger">Spam</span>',
    }
    from django.utils.safestring import mark_safe
    return mark_safe(badges.get(status, f'<span class="badge">{status}</span>'))


@register.filter
def ticket_priority_color(priority: str) -> str:
    """Return CSS color for priority."""
    colors = {
        'urgent': '#dc2626',
        'high':   '#ea580c',
        'medium': '#ca8a04',
        'low':    '#16a34a',
    }
    return colors.get(priority, '#6b7280')


@register.filter
def hours_ago(dt) -> str:
    """Return how long ago a datetime was: '2h ago', '3d ago'."""
    if not dt:
        return ''
    diff = timezone.now() - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return f'{secs}s ago'
    if secs < 3600:
        return f'{secs//60}m ago'
    if secs < 86400:
        return f'{secs//3600}h ago'
    return f'{secs//86400}d ago'


@register.filter
def mask_email(email: str) -> str:
    """Mask email: ab***@gmail.com"""
    from api.support.helpers import mask_email as _mask
    return _mask(email)


@register.filter
def ticket_icon(category: str) -> str:
    """Return emoji icon for ticket category."""
    icons = {
        'payment':    '💰',
        'coins':      '🪙',
        'account':    '👤',
        'technical':  '🔧',
        'withdrawal': '💸',
        'fraud':      '🚨',
        'kyc':        '🪪',
        'referral':   '👥',
        'offer':      '🎯',
        'other':      '❓',
    }
    return icons.get(category, '📝')


@register.filter
def format_sla_time(hours: float) -> str:
    """Format SLA hours to human readable: 1h, 4h, 2d."""
    from api.support.helpers import hours_to_human
    return hours_to_human(hours)


@register.simple_tag
def support_is_online() -> bool:
    """Check if support is currently online."""
    try:
        from api.support.cache import get_settings
        settings = get_settings()
        return settings.is_support_online if settings else True
    except Exception:
        return True


@register.simple_tag(takes_context=True)
def user_open_ticket_count(context) -> int:
    """Get open ticket count for current user."""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return 0
    try:
        from api.support.models import SupportTicket
        return SupportTicket.objects.filter(
            user=request.user,
            status__in=['open', 'in_progress', 'waiting_user']
        ).count()
    except Exception:
        return 0


@register.inclusion_tag('support/ticket_badge.html', takes_context=True)
def ticket_count_badge(context):
    """Render ticket count badge for nav."""
    request = context.get('request')
    count = 0
    if request and request.user.is_authenticated:
        try:
            from api.support.models import SupportTicket
            count = SupportTicket.objects.filter(
                user=request.user,
                status__in=['open', 'in_progress']
            ).count()
        except Exception:
            pass
    return {'count': count}