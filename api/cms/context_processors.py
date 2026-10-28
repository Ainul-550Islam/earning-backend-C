# api/cms/context_processors.py
"""Django context processors for CMS templates."""
from django.core.cache import cache


def cms_site_config(request):
    """Inject site config into all templates."""
    config = getattr(request, 'cms_site_config', None)
    if config is None:
        try:
            from api.cms.services_new.WithdrawalService import SiteConfigService
            domain = request.get_host().split(':')[0]
            cache_key = f"cms_ctx_{domain}"
            config = cache.get(cache_key)
            if config is None:
                config = SiteConfigService.get_config(domain)
                cache.set(cache_key, config, 300)
        except Exception:
            config = {}
    return {'cms_config': config, 'cms_version': '2.0.0'}


def cms_user_context(request):
    """Inject user earning info into templates."""
    if not request.user.is_authenticated:
        return {'user_coins': 0, 'user_streak': 0, 'user_level': 0}
    try:
        bal = request.user.virtual_balance
        coins = float(bal.balance)
    except Exception:
        coins = 0
    try:
        streak = request.user.earning_streak.current_streak
    except Exception:
        streak = 0
    try:
        level = request.user.profile.level
    except Exception:
        level = 1
    return {
        'user_coins': coins,
        'user_streak': streak,
        'user_level': level,
    }


def cms_notifications_context(request):
    """Inject unread notification count."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    try:
        from api.cms.models_new.extras import Notification
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
    except Exception:
        count = 0
    return {'unread_notifications': count}
