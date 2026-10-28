"""
api/gamification/integrations/rate_limit_adapter.py

RateLimit ↔ Gamification protection adapter।

rate_limit middleware-এর earning endpoints-এ gamification guard layer।
Burst abuse → achievements temporary block।

Wire-up (api/rate_limit/middleware.py তে):
    from api.gamification.integrations.rate_limit_adapter import RateLimitGamificationAdapter
    _rl_adapter = RateLimitGamificationAdapter()

    # _check_task_completion / _check_offer_completion এর শেষে:
    if is_rate_limited:
        _rl_adapter.on_rate_limit_hit(request=request, endpoint=endpoint)
"""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)

# Endpoint → gamification event name
ENDPOINT_EVENT_MAP = {
    "/api/tasks/complete/":    "task_completion",
    "/api/offers/complete/":   "offer_completion",
    "/api/referral/click/":    "referral_click",
    "/api/withdraw/request/":  "withdrawal_request",
}

# Consecutive violations before achievements get temp-blocked (per user)
BLOCK_THRESHOLD = 5
# Block duration in minutes
BLOCK_DURATION_MINUTES = 30


class RateLimitGamificationAdapter:

    def on_rate_limit_hit(self, request: Any = None, endpoint: str = "",
                          user: Any = None) -> None:
        """
        Rate limit violation হলে — abuse pattern log করো।
        BLOCK_THRESHOLD violations → achievements temp-block।
        """
        effective_user = user or getattr(request, "user", None)
        if not effective_user or not getattr(effective_user, "is_authenticated", False):
            return
        try:
            event_name = ENDPOINT_EVENT_MAP.get(endpoint, endpoint)
            violations = self._increment_violation_count(effective_user, event_name)

            self._track(effective_user, "rate_limit_hit", {
                "endpoint":   endpoint,
                "event":      event_name,
                "violations": violations,
            })

            if violations >= BLOCK_THRESHOLD:
                self._temp_block_achievements(effective_user, endpoint, violations)
                logger.warning(
                    "[RateLimitAdapter] Temp-blocked achievements for user=%s "
                    "(violations=%d endpoint=%s)",
                    getattr(effective_user, "id", "?"), violations, endpoint
                )
        except Exception as exc:
            logger.error("[RateLimitAdapter] on_rate_limit_hit failed: %s", exc)

    def is_achievement_blocked(self, user: Any) -> bool:
        """
        award_achievement guard — rate-limited user-দের achievement দেওয়া বন্ধ।
        Returns True if user is currently blocked।
        """
        try:
            from django.core.cache import cache
            key = self._block_cache_key(user)
            return bool(cache.get(key))
        except Exception:
            return False

    def on_rate_limit_cleared(self, user: Any) -> None:
        """Rate limit period শেষ → block remove করো।"""
        try:
            from django.core.cache import cache
            cache.delete(self._block_cache_key(user))
            cache.delete(self._violation_cache_key(user))
            logger.info("[RateLimitAdapter] Rate limit block cleared for user=%s",
                        getattr(user, "id", "?"))
        except Exception as exc:
            logger.error("[RateLimitAdapter] on_rate_limit_cleared failed: %s", exc)

    def _temp_block_achievements(self, user: Any, endpoint: str,
                                 violations: int) -> None:
        try:
            from django.core.cache import cache
            key     = self._block_cache_key(user)
            timeout = BLOCK_DURATION_MINUTES * 60
            cache.set(key, {"endpoint": endpoint, "violations": violations}, timeout=timeout)
        except Exception as exc:
            logger.error("[RateLimitAdapter] _temp_block_achievements failed: %s", exc)

    def _increment_violation_count(self, user: Any, event: str) -> int:
        try:
            from django.core.cache import cache
            key     = self._violation_cache_key(user)
            current = int(cache.get(key) or 0)
            new_val = current + 1
            cache.set(key, new_val, timeout=3600)  # 1 hour window
            return new_val
        except Exception:
            return 1

    def _block_cache_key(self, user: Any) -> str:
        return f"gamification:rate_block:{getattr(user, 'pk', 'anon')}"

    def _violation_cache_key(self, user: Any) -> str:
        return f"gamification:rate_violations:{getattr(user, 'pk', 'anon')}"

    def _track(self, user, event, properties):
        try:
            from api.gamification.integrations.adapter import gamification_adapter
            gamification_adapter.track_event(event, user=user, properties=properties)
        except Exception:
            pass
