# api/support/cache.py
"""
Cache management utilities for support system.
Centralized cache keys, TTLs, and invalidation helpers.
"""
import logging
from functools import wraps
from typing import Any, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Cache key prefixes ────────────────────────────────────────
PREFIX            = 'support'
PREFIX_TICKET     = f'{PREFIX}:ticket'
PREFIX_FAQ        = f'{PREFIX}:faq'
PREFIX_SETTINGS   = f'{PREFIX}:settings'
PREFIX_AGENT      = f'{PREFIX}:agent'
PREFIX_STATS      = f'{PREFIX}:stats'
PREFIX_KB         = f'{PREFIX}:kb'
PREFIX_CHAT       = f'{PREFIX}:chat'
PREFIX_USER       = f'{PREFIX}:user'

# ── TTLs (seconds) ────────────────────────────────────────────
TTL_SETTINGS      = 300    # 5 min
TTL_STATS         = 60     # 1 min
TTL_FAQ           = 600    # 10 min
TTL_KB_ARTICLE    = 300    # 5 min
TTL_KB_CATEGORY   = 600    # 10 min
TTL_AGENT_STATUS  = 30     # 30 sec
TTL_USER_TICKETS  = 60     # 1 min
TTL_ANNOUNCEMENTS = 300    # 5 min
TTL_TICKET_DETAIL = 120    # 2 min

# ── Key builders ──────────────────────────────────────────────
def key_settings() -> str:
    return f'{PREFIX_SETTINGS}:singleton'

def key_ticket(ticket_id: str) -> str:
    return f'{PREFIX_TICKET}:{ticket_id}'

def key_ticket_stats(tenant_id=None) -> str:
    suffix = f':{tenant_id}' if tenant_id else ':global'
    return f'{PREFIX_STATS}:tickets{suffix}'

def key_faq_list(category: str = 'all') -> str:
    return f'{PREFIX_FAQ}:list:{category}'

def key_kb_article(slug: str) -> str:
    return f'{PREFIX_KB}:article:{slug}'

def key_kb_categories(tenant_id=None) -> str:
    suffix = f':{tenant_id}' if tenant_id else ':global'
    return f'{PREFIX_KB}:categories{suffix}'

def key_agent_status(agent_id: int) -> str:
    return f'{PREFIX_AGENT}:status:{agent_id}'

def key_user_tickets(user_id: int) -> str:
    return f'{PREFIX_USER}:tickets:{user_id}'

def key_announcements(tenant_id=None) -> str:
    suffix = f':{tenant_id}' if tenant_id else ':global'
    return f'{PREFIX}:announcements{suffix}'

def key_chat_queue(tenant_id=None) -> str:
    suffix = f':{tenant_id}' if tenant_id else ':global'
    return f'{PREFIX_CHAT}:queue{suffix}'


# ── Get/set helpers ───────────────────────────────────────────
def get_settings():
    """Get cached support settings."""
    obj = cache.get(key_settings())
    if obj:
        return obj
    try:
        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        cache.set(key_settings(), obj, timeout=TTL_SETTINGS)
        return obj
    except Exception as e:
        logger.debug(f'cache.get_settings: {e}')
        return None


def get_ticket_stats(tenant=None) -> dict:
    """Get cached ticket stats."""
    key = key_ticket_stats(getattr(tenant, 'id', None) if tenant else None)
    stats = cache.get(key)
    if stats:
        return stats
    try:
        from api.support.models import SupportTicket
        qs = SupportTicket.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        from django.utils import timezone
        from datetime import timedelta
        stats = {
            'total':       qs.count(),
            'open':        qs.filter(status='open').count(),
            'in_progress': qs.filter(status='in_progress').count(),
            'waiting_user':qs.filter(status='waiting_user').count(),
            'resolved':    qs.filter(status='resolved').count(),
            'closed':      qs.filter(status='closed').count(),
            'urgent':      qs.filter(priority='urgent', status__in=['open','in_progress','waiting_user']).count(),
            'escalated':   qs.filter(escalated=True, status__in=['open','in_progress']).count(),
            'today':       qs.filter(created_at__date=timezone.now().date()).count(),
            'unanswered':  qs.filter(admin_response='', status='open').count(),
            'sla_breached':qs.filter(sla__first_response_breached=True).count(),
        }
        cache.set(key, stats, timeout=TTL_STATS)
        return stats
    except Exception as e:
        logger.debug(f'cache.get_ticket_stats: {e}')
        return {}


# ── Invalidation helpers ──────────────────────────────────────
def invalidate_ticket(ticket_id: str) -> None:
    cache.delete(key_ticket(ticket_id))


def invalidate_stats(tenant=None) -> None:
    cache.delete(key_ticket_stats(getattr(tenant, 'id', None) if tenant else None))


def invalidate_settings() -> None:
    cache.delete(key_settings())
    cache.delete('support:maintenance_mode')


def invalidate_faq() -> None:
    cache.delete(key_faq_list())
    cache.delete(key_faq_list('all'))


def invalidate_kb_article(slug: str) -> None:
    cache.delete(key_kb_article(slug))


def invalidate_user_tickets(user_id: int) -> None:
    cache.delete(key_user_tickets(user_id))


def invalidate_announcements(tenant=None) -> None:
    cache.delete(key_announcements(getattr(tenant,'id',None) if tenant else None))


def warm_cache() -> dict:
    """Pre-warm critical caches. Call on deploy or scheduled task."""
    results = {}
    try:
        settings = get_settings()
        results['settings'] = bool(settings)
    except Exception:
        results['settings'] = False
    try:
        stats = get_ticket_stats()
        results['stats'] = bool(stats)
    except Exception:
        results['stats'] = False
    return results


# ── Cache decorator ───────────────────────────────────────────
def cached(key_fn, ttl: int = 300):
    """Decorator to cache function return value."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_fn(*args, **kwargs) if callable(key_fn) else key_fn
            result    = cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, timeout=ttl)
            return result
        return wrapper
    return decorator