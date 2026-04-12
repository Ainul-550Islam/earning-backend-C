"""
api/monetization_tools/cache.py
=================================
Cache key builders and invalidation helpers.
Uses Django's cache framework (Redis recommended).
"""

import logging
from functools import wraps
from django.core.cache import cache

from .constants import (
    CACHE_TTL_AD_UNIT, CACHE_TTL_OFFERWALL, CACHE_TTL_LEADERBOARD,
    CACHE_TTL_REVENUE_SUMMARY, CACHE_TTL_SUBSCRIPTION_PLAN,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache key builders
# ---------------------------------------------------------------------------

def ad_unit_key(ad_unit_id) -> str:
    return f"mt:ad_unit:{ad_unit_id}"

def campaign_key(campaign_id) -> str:
    return f"mt:campaign:{campaign_id}"

def offerwall_list_key(tenant_id=None) -> str:
    return f"mt:offerwalls:{tenant_id or 'all'}"

def offer_list_key(offerwall_id, country: str = 'all') -> str:
    return f"mt:offers:{offerwall_id}:{country}"

def offer_detail_key(offer_id) -> str:
    return f"mt:offer:{offer_id}"

def leaderboard_key(scope: str, board_type: str, period_label: str = '') -> str:
    return f"mt:leaderboard:{scope}:{board_type}:{period_label}"

def revenue_summary_key(tenant_id, date_str: str) -> str:
    return f"mt:revenue_summary:{tenant_id}:{date_str}"

def subscription_plans_key(tenant_id=None) -> str:
    return f"mt:subscription_plans:{tenant_id or 'all'}"

def user_subscription_key(user_id) -> str:
    return f"mt:user_sub:{user_id}"

def user_level_key(user_id) -> str:
    return f"mt:user_level:{user_id}"

def spin_wheel_count_key(user_id, date_str: str) -> str:
    return f"mt:spin_count:{user_id}:{date_str}"

def waterfall_key(ad_unit_id) -> str:
    return f"mt:waterfall:{ad_unit_id}"

def floor_price_key(network_id, country: str = 'all') -> str:
    return f"mt:floor:{network_id}:{country}"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def get_cached(key: str):
    try:
        return cache.get(key)
    except Exception as exc:
        logger.warning("Cache GET error for key '%s': %s", key, exc)
        return None


def set_cached(key: str, value, ttl: int) -> bool:
    try:
        cache.set(key, value, timeout=ttl)
        return True
    except Exception as exc:
        logger.warning("Cache SET error for key '%s': %s", key, exc)
        return False


def delete_cached(*keys: str) -> None:
    for key in keys:
        try:
            cache.delete(key)
        except Exception as exc:
            logger.warning("Cache DELETE error for key '%s': %s", key, exc)


# ---------------------------------------------------------------------------
# Invalidation helpers
# ---------------------------------------------------------------------------

def invalidate_offer_caches(offerwall_id=None, offer_id=None) -> None:
    keys = []
    if offer_id:
        keys.append(offer_detail_key(offer_id))
    if offerwall_id:
        keys.extend([
            offer_list_key(offerwall_id),
            offer_list_key(offerwall_id, 'all'),
        ])
    delete_cached(*keys)


def invalidate_leaderboard_cache(scope: str, board_type: str, period_label: str = '') -> None:
    delete_cached(leaderboard_key(scope, board_type, period_label))


def invalidate_user_caches(user_id) -> None:
    delete_cached(
        user_subscription_key(user_id),
        user_level_key(user_id),
    )


def invalidate_waterfall_cache(ad_unit_id) -> None:
    delete_cached(waterfall_key(ad_unit_id))


# ---------------------------------------------------------------------------
# Decorator: cache view result
# ---------------------------------------------------------------------------

def cached_result(key_fn, ttl: int = 300):
    """
    Decorator for service methods that return JSON-serialisable data.
    Usage:
        @cached_result(key_fn=lambda *a, **kw: f"my_key:{a[0]}", ttl=60)
        def expensive_query(user_id): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key   = key_fn(*args, **kwargs)
            value = get_cached(key)
            if value is not None:
                return value
            result = func(*args, **kwargs)
            set_cached(key, result, ttl)
            return result
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Commonly cached queries
# ---------------------------------------------------------------------------

def get_active_offerwalls(tenant_id=None):
    """Return cached list of active offerwalls."""
    from .models import Offerwall
    key   = offerwall_list_key(tenant_id)
    value = get_cached(key)
    if value is not None:
        return value
    qs = Offerwall.objects.filter(is_active=True).select_related('network')
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    data = list(qs.values('id', 'name', 'slug', 'logo_url', 'sort_order'))
    set_cached(key, data, CACHE_TTL_OFFERWALL)
    return data


def get_subscription_plans(tenant_id=None):
    """Return cached list of active subscription plans."""
    from .models import SubscriptionPlan
    key   = subscription_plans_key(tenant_id)
    value = get_cached(key)
    if value is not None:
        return value
    qs = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    data = list(qs.values())
    set_cached(key, data, CACHE_TTL_SUBSCRIPTION_PLAN)
    return data


def get_waterfall_config(ad_unit_id):
    """Return cached waterfall config for an ad unit."""
    from .models import WaterfallConfig
    key   = waterfall_key(ad_unit_id)
    value = get_cached(key)
    if value is not None:
        return value
    entries = list(
        WaterfallConfig.objects.filter(ad_unit_id=ad_unit_id, is_active=True)
        .select_related('ad_network')
        .order_by('priority')
        .values('priority', 'floor_ecpm', 'timeout_ms', 'ad_network__display_name', 'ad_network__network_type')
    )
    set_cached(key, entries, CACHE_TTL_AD_UNIT)
    return entries


# ---------------------------------------------------------------------------
# Phase-2 cache key builders
# ---------------------------------------------------------------------------

def flash_sale_key(tenant_id=None) -> str:
    return f"mt:flash_sales:{tenant_id or 'all'}"

def active_multiplier_key(tenant_id=None) -> str:
    return f"mt:active_multiplier:{tenant_id or 'all'}"

def referral_link_key(user_id, program_id) -> str:
    return f"mt:ref_link:{user_id}:{program_id}"

def referral_summary_key(user_id) -> str:
    return f"mt:ref_summary:{user_id}"

def payout_pending_key(user_id) -> str:
    return f"mt:payout_pending:{user_id}"

def fraud_score_key(user_id) -> str:
    return f"mt:fraud_score:{user_id}"

def publisher_key(account_id) -> str:
    return f"mt:publisher:{account_id}"

def segment_members_key(segment_id) -> str:
    return f"mt:seg_members:{segment_id}"

def coupon_key(code: str) -> str:
    return f"mt:coupon:{code.upper()}"

def daily_streak_key(user_id) -> str:
    return f"mt:streak:{user_id}"

def spin_config_key(tenant_id=None) -> str:
    return f"mt:spin_config:{tenant_id or 'all'}"

def revenue_goal_key(tenant_id, period: str) -> str:
    return f"mt:rev_goal:{tenant_id}:{period}"

def postback_dedup_key(network_name: str, txn_id: str) -> str:
    """Short-lived key (5 min) for postback deduplication."""
    return f"mt:pb_dedup:{network_name}:{txn_id}"


# ---------------------------------------------------------------------------
# Phase-2 invalidation helpers
# ---------------------------------------------------------------------------

def invalidate_referral_caches(user_id, program_id=None) -> None:
    keys = [referral_summary_key(user_id)]
    if program_id:
        keys.append(referral_link_key(user_id, program_id))
    delete_cached(*keys)


def invalidate_publisher_cache(account_id) -> None:
    delete_cached(publisher_key(account_id))


def invalidate_segment_cache(segment_id) -> None:
    delete_cached(segment_members_key(segment_id))


def invalidate_coupon_cache(code: str) -> None:
    delete_cached(coupon_key(code))


def invalidate_streak_cache(user_id) -> None:
    delete_cached(daily_streak_key(user_id))


# ---------------------------------------------------------------------------
# Phase-2 commonly cached queries
# ---------------------------------------------------------------------------

def get_live_flash_sales(tenant_id=None):
    """Return cached live flash sales."""
    from .models import FlashSale
    from django.utils import timezone
    key   = flash_sale_key(tenant_id)
    value = get_cached(key)
    if value is not None:
        return value
    now = timezone.now()
    qs  = FlashSale.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    data = list(qs.values('id', 'name', 'sale_type', 'multiplier', 'bonus_coins',
                           'discount_pct', 'starts_at', 'ends_at'))
    set_cached(key, data, ttl=60)  # 1-min TTL — sales are time-sensitive
    return data


def get_coupon(code: str):
    """Return cached coupon by code."""
    from .models import Coupon
    key   = coupon_key(code)
    value = get_cached(key)
    if value is not None:
        return value
    try:
        coupon = Coupon.objects.get(code__iexact=code, is_active=True)
        set_cached(key, coupon, ttl=300)
        return coupon
    except Coupon.DoesNotExist:
        return None


def get_daily_streak(user_id):
    """Return cached DailyStreak for user."""
    from .models import DailyStreak
    key   = daily_streak_key(user_id)
    value = get_cached(key)
    if value is not None:
        return value
    try:
        streak = DailyStreak.objects.get(user_id=user_id)
        set_cached(key, streak, ttl=120)
        return streak
    except DailyStreak.DoesNotExist:
        return None


def check_postback_duplicate(network_name: str, txn_id: str) -> bool:
    """Return True if postback was already seen in the last 5 minutes."""
    key   = postback_dedup_key(network_name, txn_id)
    value = get_cached(key)
    if value:
        return True
    set_cached(key, 1, ttl=300)
    return False
