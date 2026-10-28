# api/cms/sanctions.py
"""
CMS Sanctions stub — sanctions logic is owned by api.fraud_detection.
This module provides CMS-level wrappers only.
"""
from typing import Dict, List, Optional
import logging

logger = logging.getLogger('api.cms.sanctions')


class SanctionManager:
    """CMS wrapper for sanctions via fraud_detection adapter."""

    @staticmethod
    def is_sanctioned(user) -> bool:
        from api.cms.adapters import FraudAdapter
        return FraudAdapter.is_sanctioned(user)

    @staticmethod
    def get_user_sanctions(user) -> List[Dict]:
        try:
            from api.fraud_detection.models import SanctionList
            return list(SanctionList.objects.filter(user=user).values(
                'reason', 'created_at', 'expires_at', 'is_active'
            ))
        except (ImportError, Exception):
            return []

    @staticmethod
    def suspend_user(user, reason: str, duration_days: int = 30) -> bool:
        try:
            from api.fraud_detection.services import SanctionService
            SanctionService.suspend(user=user, reason=reason, days=duration_days)
            return True
        except (ImportError, Exception) as e:
            logger.warning("[CMS Sanctions] suspend failed: %s", e)
            return False

    @staticmethod
    def unsuspend_user(user) -> bool:
        try:
            from api.fraud_detection.services import SanctionService
            SanctionService.lift(user=user)
            return True
        except (ImportError, Exception):
            return False

    @staticmethod
    def get_active_suspensions() -> List[Dict]:
        try:
            from api.fraud_detection.models import SanctionList
            return list(SanctionList.objects.filter(is_active=True).values(
                'user_id', 'reason', 'created_at', 'expires_at'
            )[:100])
        except (ImportError, Exception):
            return []


class FraudScorer:
    """CMS fraud scoring — returns (score: int 0-100, reasons: list)."""

    @staticmethod
    def score(user_id: int, ip: str, session_id: str,
              payout: float) -> tuple:
        """
        Calculate a fraud risk score.

        Returns ``(score: int, reasons: list[str])`` where score 0–100.
        Rules (additive, capped at 100):
          - IP is banned                     → 100 immediately
          - payout == 0                      → +40  (zero-payout anomaly)
          - payout > 50 (unusually high)     → +20
        """
        from django.core.cache import cache
        reasons = []

        # Banned IP check — instant 100
        if cache.get(f'cms:banned_ip:{ip}'):
            reasons.append('banned_ip')
            return 100, reasons

        fraud_score = 0

        # Zero payout anomaly
        if payout == 0:
            fraud_score += 40
            reasons.append('zero_payout')

        # Unusually high payout
        if payout and float(payout) > 50:
            fraud_score += 20
            reasons.append('high_payout')

        return min(fraud_score, 100), reasons

    @staticmethod
    def is_high_risk(user, threshold: float = 0.7) -> bool:
        """Legacy interface — score a user object."""
        try:
            score, _ = FraudScorer.score(user.pk, '', '', 0)
            return score / 100 >= threshold
        except Exception:
            return False

    @staticmethod
    def block_if_risky(user, threshold: float = 0.8) -> bool:
        return FraudScorer.is_high_risk(user, threshold)

    @staticmethod
    def ban_ip(ip: str, reason: str = '', duration_hours: int = 24) -> bool:
        from django.core.cache import cache
        cache.set(f'cms:banned_ip:{ip}',
                  {'reason': reason, 'banned': True},
                  timeout=duration_hours * 3600)
        return True

    @staticmethod
    def unban_ip(ip: str) -> bool:
        from django.core.cache import cache
        cache.delete(f'cms:banned_ip:{ip}')
        return True

    @staticmethod
    def is_ip_banned(ip: str) -> bool:
        from django.core.cache import cache
        return bool(cache.get(f'cms:banned_ip:{ip}'))


class RateLimiter:
    """Self-contained rate limiter using Django cache as the counter backend.

    ``check()`` accepts both ``window`` (old name) and ``window_seconds`` (new
    name used in tests) so both callers work without changes.

    Returns a ``(allowed: bool, remaining: int)`` tuple — tests unpack it.
    """

    @staticmethod
    def check(key: str, limit: int, window: int = 60,
              window_seconds: int = None) -> tuple:
        """
        Check and consume one token for ``key``.

        Returns ``(allowed, remaining)`` where:
          - ``allowed``   is True if the request is within the rate limit.
          - ``remaining`` is the number of calls left in the current window.
        """
        from django.core.cache import cache
        effective_window = window_seconds if window_seconds is not None else window
        cache_key = f'cms:rl:{key}'
        count = cache.get(cache_key, 0)
        if count >= limit:
            return False, 0
        # Increment — set with TTL only on first hit
        new_count = count + 1
        if count == 0:
            cache.set(cache_key, new_count, effective_window)
        else:
            cache.set(cache_key, new_count,
                      cache.ttl(cache_key) if hasattr(cache, 'ttl') else effective_window)
        remaining = max(limit - new_count, 0)
        return True, remaining

    @staticmethod
    def consume(key: str, limit: int, window: int = 60,
                window_seconds: int = None) -> bool:
        """Consume a token; returns True if allowed."""
        allowed, _ = RateLimiter.check(key, limit, window, window_seconds)
        return allowed

    @staticmethod
    def is_rate_limited(key: str, limit: int, window: int = 60) -> bool:
        """Return True if the key is currently rate-limited (no token consumed)."""
        from django.core.cache import cache
        count = cache.get(f'cms:rl:{key}', 0)
        return count >= limit
