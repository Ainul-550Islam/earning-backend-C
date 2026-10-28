# api/admin_panel/rate_limiting.py
"""
Admin Panel Rate Limiting Engine.
Extends api.rate_limit with admin-specific controls:
  - Per-endpoint admin rate limits
  - Admin bulk action throttling
  - Emergency rate limit override
  - Rate limit analytics
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdminRateLimiter:
    """Admin-specific rate limiter with bypass and override support."""

    # Default limits (requests / window_seconds)
    DEFAULTS = {
        'bulk_ban':         (10, 60),        # 10 bulk bans per minute
        'bulk_approve':     (50, 60),         # 50 approvals per minute
        'data_export':      (5, 3600),        # 5 exports per hour
        'report_generate':  (10, 3600),       # 10 reports per hour
        'broadcast':        (5, 3600),        # 5 broadcasts per hour
        'kyc_approve':      (100, 60),        # 100 KYC approvals per minute
        'fraud_block_ip':   (50, 60),         # 50 IP blocks per minute
        'wallet_adjust':    (20, 60),         # 20 wallet adjustments per minute
        'user_ban':         (20, 60),         # 20 user bans per minute
        'config_update':    (30, 60),         # 30 config updates per minute
        'api_call':         (1000, 3600),     # 1000 API calls per hour (general)
    }

    @classmethod
    def check(cls, action: str, actor_id: Any, scope: str = 'user') -> Tuple[bool, int, int]:
        """
        Check if action is rate limited.
        Returns (allowed, current_count, limit).
        """
        limit, window = cls.DEFAULTS.get(action, (100, 60))

        # Check for override (emergency bypass)
        override_key = f'admin_panel:rl_override:{actor_id}:{action}'
        if cache.get(override_key):
            return True, 0, limit

        # Check if superadmin (higher limits)
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=actor_id)
            if user.is_superuser:
                limit = limit * 5  # 5x limit for superadmin
        except Exception:
            pass

        cache_key = f'admin_panel:rl:{scope}:{actor_id}:{action}'
        current = cache.get(cache_key, 0)

        if current >= limit:
            logger.warning(f"[RateLimit] {action} BLOCKED: actor={actor_id} count={current}/{limit}")
            return False, current, limit

        cache.set(cache_key, current + 1, window)
        return True, current + 1, limit

    @classmethod
    def override(cls, actor_id: Any, action: str, ttl: int = 300) -> None:
        """Emergency bypass — allow actor to exceed rate limit."""
        cache.set(f'admin_panel:rl_override:{actor_id}:{action}', True, ttl)
        logger.warning(f"[RateLimit] Override set for actor={actor_id} action={action} ttl={ttl}s")

    @classmethod
    def reset(cls, actor_id: Any, action: str) -> None:
        """Reset rate limit counter for an actor/action."""
        cache.delete(f'admin_panel:rl:user:{actor_id}:{action}')

    @classmethod
    def get_stats(cls, actor_id: Any) -> Dict[str, Dict]:
        """Get current rate limit usage for all actions."""
        stats = {}
        for action, (limit, window) in cls.DEFAULTS.items():
            key = f'admin_panel:rl:user:{actor_id}:{action}'
            current = cache.get(key, 0)
            stats[action] = {'current': current, 'limit': limit, 'window': window,
                             'pct': round(current / limit * 100, 1)}
        return stats

    @classmethod
    def set_custom_limit(cls, action: str, limit: int, window: int) -> None:
        """Set custom rate limit for an action (persisted in cache)."""
        cls.DEFAULTS[action] = (limit, window)
        cache.set(f'admin_panel:rl_custom:{action}', (limit, window), 86400 * 7)

    @classmethod
    def load_custom_limits(cls) -> None:
        """Load custom limits from DB/cache on startup."""
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='admin_rate_limits')
            limits = json.loads(obj.value)
            for action, (limit, window) in limits.items():
                cls.DEFAULTS[action] = (limit, window)
        except Exception:
            pass


admin_rate_limiter = AdminRateLimiter()