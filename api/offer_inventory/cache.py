# api/offer_inventory/cache.py
"""
Cache helpers — Redis-backed।
সব cache key এখানে centralize করা।
"""
from django.core.cache import cache
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)

# ── TTL Constants ─────────────────────────────────────────────────
TTL_OFFER_LIST    = 300      # 5 min
TTL_OFFER_DETAIL  = 600      # 10 min
TTL_DASHBOARD     = 300      # 5 min
TTL_USER_PROFILE  = 900      # 15 min
TTL_FRAUD_RULES   = 600      # 10 min
TTL_GEO_IP        = 3600     # 1 hour
TTL_FEATURE_FLAG  = 120      # 2 min
TTL_NOTIF_COUNT   = 60       # 1 min


# ── Key Builders ─────────────────────────────────────────────────

def offer_list_key(tenant=None, country='', device='', page=1):
    return f'offers:list:{tenant}:{country}:{device}:p{page}'


def offer_detail_key(offer_id: str):
    return f'offers:detail:{offer_id}'


def dashboard_key(tenant=None):
    return f'dashboard:stats:{tenant}'


def user_profile_key(user_id):
    return f'user:profile:{user_id}'


def fraud_rules_key():
    return 'fraud:rules:active'


def feature_flag_key(feature: str, tenant=None):
    return f'feature:{tenant}:{feature}'


def notif_count_key(user_id):
    return f'notif:unread:{user_id}'


def click_token_key(token: str):
    return f'click:token:{token}'


def ip_blocked_key(ip: str):
    return f'ip:blocked:{ip}'


# ── Cache Operations ──────────────────────────────────────────────

def get_cached(key: str):
    try:
        return cache.get(key)
    except Exception as e:
        logger.error(f'Cache GET error ({key}): {e}')
        return None


def set_cached(key: str, value, ttl: int = 300):
    try:
        cache.set(key, value, ttl)
    except Exception as e:
        logger.error(f'Cache SET error ({key}): {e}')


def delete_cached(*keys):
    try:
        cache.delete_many(keys)
    except Exception as e:
        logger.error(f'Cache DELETE error: {e}')


def invalidate_offer_caches(offer_id: str = None, tenant=None):
    """Offer-related cache মুছে দাও।"""
    keys = [dashboard_key(tenant)]
    if offer_id:
        keys.append(offer_detail_key(offer_id))
    delete_cached(*keys)
    # Pattern delete for offer lists
    try:
        cache.delete_pattern(f'offers:list:{tenant}:*')
    except AttributeError:
        pass  # Some cache backends don't support pattern delete


def cache_result(key_fn, ttl=300):
    """Decorator: function result cache করো।"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            cached = get_cached(key)
            if cached is not None:
                return cached
            result = fn(*args, **kwargs)
            set_cached(key, result, ttl)
            return result
        return wrapper
    return decorator
