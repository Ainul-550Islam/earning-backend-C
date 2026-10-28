from typing import Dict
# api/referral/caching.py
# Centralized cache layer for referral module
# All cache reads/writes go through this module — never cache.set() directly
# ============================================================

import json
import logging
from decimal import Decimal
from typing import Any, Callable, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Cache Key Constants ───────────────────────────────────────────────────────

KEY_SETTINGS           = 'referral:settings:v1'
KEY_ACTIVE_CAMPAIGN    = 'referral:campaign:active:v1'
KEY_FRAUD_RULES        = 'referral:fraud:rules:v1'
KEY_CODE_PREFIX        = 'referral:code:{code}'
KEY_USER_STATS_PREFIX  = 'referral:stats:user:{user_id}'
KEY_USER_CODE_PREFIX   = 'referral:code:user:{user_id}'
KEY_TREE_PREFIX        = 'referral:tree:{user_id}'
KEY_LEADERBOARD_PREFIX = 'referral:leaderboard:{period}:{date}'
KEY_CLICK_UNIQUE_PREFIX= 'referral:click:unique:{code_id}:{ip_hash}'
KEY_TIER_PREFIX        = 'referral:tier:{user_id}'
KEY_VIRAL_COEFF        = 'referral:viral:k_factor:{date}'
KEY_RATE_LIMIT_PREFIX  = 'referral:ratelimit:{user_id}:{action}'

# ── TTL Constants ─────────────────────────────────────────────────────────────

TTL_SETTINGS      = 300        # 5 minutes
TTL_CAMPAIGN      = 300        # 5 minutes
TTL_FRAUD_RULES   = 600        # 10 minutes
TTL_CODE          = 1800       # 30 minutes
TTL_USER_STATS    = 300        # 5 minutes
TTL_USER_CODE     = 3600       # 1 hour
TTL_TREE          = 3600       # 1 hour
TTL_LEADERBOARD   = 900        # 15 minutes
TTL_CLICK_UNIQUE  = 86400      # 24 hours
TTL_TIER          = 600        # 10 minutes
TTL_VIRAL         = 21600      # 6 hours
TTL_RATE_LIMIT    = 3600       # 1 hour


# ── Core Cache Operations ─────────────────────────────────────────────────────

class ReferralCache:
    """
    Centralized cache manager for the referral module.
    Handles serialization, key formatting, and error recovery.
    """

    @staticmethod
    def get(key: str, default=None) -> Any:
        """Get value from cache. Returns default on miss or error."""
        try:
            val = cache.get(key)
            return val if val is not None else default
        except Exception as e:
            logger.warning(f'[Cache] GET failed for {key}: {e}')
            return default

    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        """Set value in cache. Returns True on success."""
        try:
            cache.set(key, value, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f'[Cache] SET failed for {key}: {e}')
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """Delete key from cache."""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f'[Cache] DELETE failed for {key}: {e}')
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """Delete all keys matching a pattern (requires Redis backend)."""
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            keys = conn.keys(pattern)
            if keys:
                conn.delete(*keys)
                return len(keys)
        except Exception as e:
            logger.debug(f'[Cache] Pattern delete failed: {e}')
        return 0

    @staticmethod
    def get_or_set(key: str, getter: Callable, timeout: int = 300) -> Any:
        """
        Get from cache or call getter() and cache the result.
        Pattern: cache-aside.
        """
        val = ReferralCache.get(key)
        if val is None:
            try:
                val = getter()
                if val is not None:
                    ReferralCache.set(key, val, timeout)
            except Exception as e:
                logger.warning(f'[Cache] get_or_set getter failed: {e}')
        return val

    @staticmethod
    def increment(key: str, amount: int = 1, timeout: int = 3600) -> int:
        """Atomic increment. Used for click/conversion counters."""
        try:
            result = cache.incr(key, amount)
            return result
        except ValueError:
            # Key doesn't exist — set it
            cache.set(key, amount, timeout)
            return amount
        except Exception as e:
            logger.warning(f'[Cache] INCREMENT failed: {e}')
            return 0


# ── Domain-Specific Cache Operations ─────────────────────────────────────────

class ReferralSettingsCache:
    """Cache operations for ReferralSettings."""

    @staticmethod
    def get():
        """Get cached ReferralSettings object."""
        return ReferralCache.get(KEY_SETTINGS)

    @staticmethod
    def set(settings_obj) -> None:
        """Cache ReferralSettings object."""
        ReferralCache.set(KEY_SETTINGS, settings_obj, TTL_SETTINGS)

    @staticmethod
    def invalidate() -> None:
        """Clear settings cache."""
        ReferralCache.delete(KEY_SETTINGS)
        ReferralCache.delete(KEY_ACTIVE_CAMPAIGN)

    @staticmethod
    def get_or_load():
        """Get from cache or load from DB."""
        def _load():
            from api.referral.models import ReferralSettings
            s = ReferralSettings.objects.first()
            if not s:
                s = ReferralSettings.objects.create()
            return s
        return ReferralCache.get_or_set(KEY_SETTINGS, _load, TTL_SETTINGS)


class ReferralCodeCache:
    """Cache operations for ReferralCode lookups."""

    @staticmethod
    def get_by_code(code: str):
        """Get ReferralCode object by code string."""
        key = KEY_CODE_PREFIX.format(code=code.upper())
        return ReferralCache.get(key)

    @staticmethod
    def set_code(code: str, code_obj) -> None:
        key = KEY_CODE_PREFIX.format(code=code.upper())
        ReferralCache.set(key, code_obj, TTL_CODE)

    @staticmethod
    def get_primary_for_user(user_id: int):
        """Get primary ReferralCode for a user."""
        key = KEY_USER_CODE_PREFIX.format(user_id=user_id)
        return ReferralCache.get(key)

    @staticmethod
    def set_primary_for_user(user_id: int, code_obj) -> None:
        key = KEY_USER_CODE_PREFIX.format(user_id=user_id)
        ReferralCache.set(key, code_obj, TTL_USER_CODE)

    @staticmethod
    def invalidate_user(user_id: int) -> None:
        key = KEY_USER_CODE_PREFIX.format(user_id=user_id)
        ReferralCache.delete(key)

    @staticmethod
    def record_unique_click(code_id: int, ip_hash: str) -> bool:
        """
        Record unique click for a code+IP combination.
        Returns True if this is a NEW unique click (not seen before).
        """
        key = KEY_CLICK_UNIQUE_PREFIX.format(code_id=code_id, ip_hash=ip_hash)
        if cache.get(key):
            return False
        cache.set(key, 1, TTL_CLICK_UNIQUE)
        return True


class ReferralUserStatsCache:
    """Cache operations for per-user referral stats."""

    @staticmethod
    def get(user_id: int) -> Optional[dict]:
        key = KEY_USER_STATS_PREFIX.format(user_id=user_id)
        return ReferralCache.get(key)

    @staticmethod
    def set(user_id: int, stats: dict) -> None:
        key = KEY_USER_STATS_PREFIX.format(user_id=user_id)
        ReferralCache.set(key, stats, TTL_USER_STATS)

    @staticmethod
    def invalidate(user_id: int) -> None:
        key = KEY_USER_STATS_PREFIX.format(user_id=user_id)
        ReferralCache.delete(key)
        # Also invalidate tier cache
        tier_key = KEY_TIER_PREFIX.format(user_id=user_id)
        ReferralCache.delete(tier_key)


class ReferralLeaderboardCache:
    """Cache operations for leaderboard data."""

    @staticmethod
    def get(period: str) -> Optional[list]:
        today = timezone.now().date().isoformat()
        key = KEY_LEADERBOARD_PREFIX.format(period=period, date=today)
        return ReferralCache.get(key)

    @staticmethod
    def set(period: str, data: list) -> None:
        today = timezone.now().date().isoformat()
        key = KEY_LEADERBOARD_PREFIX.format(period=period, date=today)
        ReferralCache.set(key, data, TTL_LEADERBOARD)

    @staticmethod
    def invalidate_all() -> None:
        for period in ['daily', 'weekly', 'monthly']:
            today = timezone.now().date().isoformat()
            key = KEY_LEADERBOARD_PREFIX.format(period=period, date=today)
            ReferralCache.delete(key)


class FraudRulesCache:
    """Cache operations for fraud rules list."""

    @staticmethod
    def get() -> Optional[list]:
        return ReferralCache.get(KEY_FRAUD_RULES)

    @staticmethod
    def set(rules: list) -> None:
        ReferralCache.set(KEY_FRAUD_RULES, rules, TTL_FRAUD_RULES)

    @staticmethod
    def get_or_load() -> list:
        def _load():
            from api.referral.models import ReferralFraudRule
            return list(ReferralFraudRule.objects.filter(
                is_active=True
            ).values(
                'rule_type', 'action', 'threshold',
                'fraud_score_points', 'time_window_minutes',
            ))
        result = ReferralCache.get_or_set(KEY_FRAUD_RULES, _load, TTL_FRAUD_RULES)
        return result or []

    @staticmethod
    def invalidate() -> None:
        ReferralCache.delete(KEY_FRAUD_RULES)


class ReferralRateLimitCache:
    """Cache-based rate limiting for referral actions."""

    @staticmethod
    def check_and_increment(user_id: int, action: str, max_count: int, window_seconds: int) -> bool:
        """
        Check rate limit and increment counter.
        Returns True if request is allowed.
        Returns False if rate limit exceeded.
        """
        key = KEY_RATE_LIMIT_PREFIX.format(user_id=user_id, action=action)
        current = ReferralCache.get(key, default=0)
        if current >= max_count:
            return False
        ReferralCache.set(key, current + 1, window_seconds)
        return True

    @staticmethod
    def get_remaining(user_id: int, action: str, max_count: int) -> int:
        """Get remaining allowed requests."""
        key = KEY_RATE_LIMIT_PREFIX.format(user_id=user_id, action=action)
        current = ReferralCache.get(key, default=0)
        return max(0, max_count - current)

    @staticmethod
    def reset(user_id: int, action: str) -> None:
        key = KEY_RATE_LIMIT_PREFIX.format(user_id=user_id, action=action)
        ReferralCache.delete(key)


# ── Cache Warming ─────────────────────────────────────────────────────────────

def warm_referral_caches() -> Dict:
    """
    Pre-warm critical caches on server startup.
    Call from apps.py ready() or management command.
    """
    results = {}

    try:
        ReferralSettingsCache.get_or_load()
        results['settings'] = 'warmed'
    except Exception as e:
        results['settings'] = f'error: {e}'

    try:
        FraudRulesCache.get_or_load()
        results['fraud_rules'] = 'warmed'
    except Exception as e:
        results['fraud_rules'] = f'error: {e}'

    logger.info(f'[Cache] Warmed: {results}')
    return results


# ── Type alias for Dict usage at top ─────────────────────────────────────────
from typing import Dict  # noqa: E402