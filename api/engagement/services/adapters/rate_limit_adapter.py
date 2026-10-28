# engagement/services/adapters/rate_limit_adapter.py
"""
RateLimitAdapter
================
Wraps api.rate_limit for ALL engagement actions.

Engagement never imports RateLimitService directly — all calls go here.
If api.rate_limit is unavailable, falls back to Redis cache counting.

Actions checked:
    checkin        — 1/day
    spin           — N/day (from SPIN_MAX_PER_DAY)
    task           — N/day per task_type
    shop_purchase  — N/hour
    scratch        — N/day
    auction_bid    — N/hour
    referral       — N/day (abuse prevention)
    offer_access   — N/hour per offerwall
    quest_claim    — N/day
    achievement_claim — N/day
"""

import logging
from typing import Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("engagement.adapters.rate_limit")

# ── Engagement-specific default limits (used when api.rate_limit unavailable) ──
ENGAGEMENT_LIMITS = {
    "checkin":           {"max": 1,   "window": 86400},   # 1/day
    "spin":              {"max": 10,  "window": 86400},   # 10/day
    "scratch":           {"max": 3,   "window": 86400},   # 3/day
    "task":              {"max": 50,  "window": 86400},   # 50/day
    "shop_purchase":     {"max": 20,  "window": 3600},    # 20/hour
    "auction_bid":       {"max": 50,  "window": 3600},    # 50/hour
    "referral":          {"max": 5,   "window": 86400},   # 5/day
    "quest_claim":       {"max": 100, "window": 86400},   # 100/day
    "offer_access":      {"max": 100, "window": 3600},    # 100/hour
    "achievement_claim": {"max": 50,  "window": 86400},   # 50/day
    "calendar_claim":    {"max": 1,   "window": 86400},   # 1/day
    "chest_open":        {"max": 20,  "window": 86400},   # 20/day
    "prestige":          {"max": 1,   "window": 86400},   # 1/day
}


class RateLimitAdapter:
    """
    Engagement → api.rate_limit adapter.
    All methods return a standard result dict.
    """

    # ── Result builder ────────────────────────────────────────────────────────
    @staticmethod
    def _ok(remaining: int = 999, limit: int = 999, current: int = 0,
             reset_after: int = 0) -> dict:
        return {
            "allowed": True,
            "remaining": remaining,
            "limit": limit,
            "current": current,
            "reset_after": reset_after,
            "source": "pass",
        }

    @staticmethod
    def _blocked(limit: int, current: int, reset_after: int,
                 reason: str = "rate_limited") -> dict:
        return {
            "allowed": False,
            "remaining": 0,
            "limit": limit,
            "current": current,
            "reset_after": reset_after,
            "retry_after": reset_after,
            "reason": reason,
            "source": "blocked",
        }

    # ── Fallback: Redis cache counting ────────────────────────────────────────
    @staticmethod
    def _cache_check(user, action: str, ip: str = None) -> dict:
        """Simple Redis/cache counter — used when api.rate_limit unavailable."""
        cfg = ENGAGEMENT_LIMITS.get(action, {"max": 100, "window": 3600})
        max_count = cfg["max"]
        window = cfg["window"]

        # Per-user key
        key = f"rl:eng:{action}:{user.pk}"
        current = cache.get(key, 0)

        if current >= max_count:
            ttl = cache.ttl(key) if hasattr(cache, "ttl") else window
            return RateLimitAdapter._blocked(max_count, current, ttl or window)

        # Increment
        try:
            new_val = cache.incr(key)
            if new_val == 1:
                cache.expire(key, window)
        except Exception:
            cache.set(key, current + 1, window)
            new_val = current + 1

        return RateLimitAdapter._ok(
            remaining=max(0, max_count - new_val),
            limit=max_count,
            current=new_val,
            reset_after=window,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def check_action(user, action: str, ip: str = None,
                     task_type: str = None, offer_wall: str = None) -> dict:
        """
        Master check for ANY engagement action.

        Args:
            user:       User performing the action
            action:     'checkin' | 'spin' | 'task' | 'shop_purchase' | etc.
            ip:         Client IP address
            task_type:  Required when action='task'
            offer_wall: Required when action='offer_access'

        Returns:
            {
                "allowed": bool,
                "remaining": int,
                "limit": int,
                "current": int,
                "reset_after": int,   # seconds until window resets
                "retry_after": int,   # seconds until allowed again (if blocked)
                "source": str,        # "rate_limit_app" | "cache_fallback"
            }
        """
        try:
            from api.rate_limit.services.RateLimitService import RateLimitService
            svc = RateLimitService()

            if action == "task" and task_type:
                result = svc.check_task_completion_limit(user, task_type)
                return {
                    "allowed":     result["is_allowed"],
                    "remaining":   result["remaining"],
                    "limit":       result["limit"],
                    "current":     result["current"],
                    "reset_after": result.get("reset_time", 0),
                    "retry_after": result.get("reset_time", 0) if not result["is_allowed"] else 0,
                    "source":      "rate_limit_app",
                }

            if action == "offer_access" and offer_wall:
                result = svc.check_offer_access_limit(user, offer_wall)
                return {
                    "allowed":     result["is_allowed"],
                    "remaining":   result["remaining"],
                    "limit":       result["limit"],
                    "current":     result["current"],
                    "reset_after": result.get("reset_time", 0),
                    "retry_after": result.get("reset_time", 0) if not result["is_allowed"] else 0,
                    "source":      "rate_limit_app",
                }

            if action == "referral" and ip:
                result = svc.check_referral_activity(ip)
                return {
                    "allowed":     result["is_allowed"],
                    "remaining":   result.get("remaining", 0),
                    "limit":       result.get("limit", 5),
                    "current":     result.get("current", 0),
                    "reset_after": result.get("reset_time", 86400),
                    "retry_after": result.get("reset_time", 86400) if not result["is_allowed"] else 0,
                    "source":      "rate_limit_app",
                }

            # Generic action → use cache fallback with engagement limits
            result = RateLimitAdapter._cache_check(user, action, ip)
            result["source"] = "cache_fallback"
            return result

        except ImportError:
            # api.rate_limit not installed
            result = RateLimitAdapter._cache_check(user, action, ip)
            result["source"] = "cache_fallback"
            return result
        except Exception as e:
            logger.error(f"RateLimitAdapter.check_action error user={user.pk} action={action}: {e}")
            # Fail open — allow the action
            return RateLimitAdapter._ok()

    @staticmethod
    def check_spin(user, ip: str = None) -> dict:
        """Convenience: check spin rate limit."""
        return RateLimitAdapter.check_action(user, "spin", ip=ip)

    @staticmethod
    def check_checkin(user, ip: str = None) -> dict:
        """Convenience: check daily check-in."""
        return RateLimitAdapter.check_action(user, "checkin", ip=ip)

    @staticmethod
    def check_task(user, task_type: str, ip: str = None) -> dict:
        """Convenience: check task completion rate."""
        return RateLimitAdapter.check_action(user, "task", ip=ip, task_type=task_type)

    @staticmethod
    def check_shop(user, ip: str = None) -> dict:
        """Convenience: check shop purchase rate."""
        return RateLimitAdapter.check_action(user, "shop_purchase", ip=ip)

    @staticmethod
    def check_referral_ip(ip: str) -> dict:
        """Check referral activity from IP (abuse prevention)."""
        try:
            from api.rate_limit.services.RateLimitService import RateLimitService
            result = RateLimitService().check_referral_activity(ip)
            return {
                "allowed":     result.get("is_allowed", True),
                "reason":      result.get("reason", ""),
                "source":      "rate_limit_app",
            }
        except Exception:
            # Cache-based IP check
            key = f"rl:eng:referral_ip:{ip}"
            current = cache.get(key, 0)
            if current >= 5:
                return {"allowed": False, "reason": "ip_rate_limited", "source": "cache_fallback"}
            cache.set(key, current + 1, 86400)
            return {"allowed": True, "reason": "", "source": "cache_fallback"}

    @staticmethod
    def reset_action(user, action: str) -> bool:
        """
        Reset rate limit counter for a user+action.
        Called by admin when manually resetting limits.
        """
        key = f"rl:eng:{action}:{user.pk}"
        cache.delete(key)
        try:
            from api.rate_limit.services.RateLimitService import RateLimitService
            from api.rate_limit.services.RedisRateLimiter import RedisRateLimiter
            RedisRateLimiter().reset_user_limits(user.id, action)
        except Exception:
            pass
        return True

    @staticmethod
    def get_user_limits(user) -> dict:
        """
        Get current rate limit status for all engagement actions for a user.
        Used in admin panel / debug endpoint.
        """
        result = {}
        for action in ENGAGEMENT_LIMITS:
            key = f"rl:eng:{action}:{user.pk}"
            cfg = ENGAGEMENT_LIMITS[action]
            current = cache.get(key, 0)
            result[action] = {
                "current": current,
                "limit": cfg["max"],
                "remaining": max(0, cfg["max"] - current),
                "window_seconds": cfg["window"],
            }
        return result
