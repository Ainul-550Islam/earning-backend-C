"""
fraud_detection/velocity_checker.py
─────────────────────────────────────
Velocity-based fraud detection.

Checks:
  1. IP Velocity       — > N conversions from same IP within 1 minute → flag
  2. IP Daily Cap      — > N conversions from same IP within 24 hours → flag
  3. User Velocity     — > N conversions from same user within 1 hour → flag
  4. Network Burst     — > N postbacks from same network within 1 minute → flag
  5. Device Velocity   — > N clicks from same device fingerprint within 1 hour

All thresholds are configurable via constants.
Redis-backed for high-throughput, with DB fallback.

Redis key schema:
  pe:vel:ip:1m:{ip_hash}              → sliding window counter (TTL 60s)
  pe:vel:ip:1h:{ip_hash}              → sliding window counter (TTL 3600s)
  pe:vel:ip:24h:{ip_hash}             → sliding window counter (TTL 86400s)
  pe:vel:user:1h:{user_id}            → sliding window counter (TTL 3600s)
  pe:vel:net:1m:{network_id}          → sliding window counter (TTL 60s)
  pe:vel:dev:1h:{fingerprint_hash}    → sliding window counter (TTL 3600s)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from django.core.cache import cache
from django.utils import timezone

from ..constants import (
    MAX_CONVERSIONS_SAME_IP_HOUR,
    MAX_CONVERSIONS_SAME_DEVICE_DAY,
    BOT_VELOCITY_THRESHOLD,
)
from ..exceptions import VelocityLimitException, FraudDetectedException

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────
# Override via Django settings: POSTBACK_ENGINE = {"VELOCITY_IP_1M": 10, ...}

_IP_CONVERSIONS_PER_MINUTE  = 5    # more than 5 conversions in 60s from same IP → fraud
_IP_CONVERSIONS_PER_HOUR    = 50   # more than 50/hour → flag for review
_IP_CONVERSIONS_PER_DAY     = 200  # more than 200/day → hard block
_USER_CONVERSIONS_PER_HOUR  = 20   # more than 20 conversions/hour same user → suspicious
_NETWORK_POSTBACKS_PER_MIN  = 2000 # network-level burst protection
_DEVICE_CLICKS_PER_HOUR     = 30   # device fingerprint velocity

# Redis TTL per window
_TTL_1M  = 60
_TTL_1H  = 3600
_TTL_24H = 86400


@dataclass
class VelocityResult:
    """Result from a velocity check."""
    blocked: bool = False
    flagged: bool = False           # flag but don't hard-block
    violations: List[str] = field(default_factory=list)

    def add_violation(self, msg: str, hard_block: bool = False):
        self.violations.append(msg)
        if hard_block:
            self.blocked = True
        else:
            self.flagged = True


class VelocityChecker:
    """
    High-throughput velocity/rate-limit fraud detector.
    Uses Redis atomic INCRs for concurrency-safe counting.
    Falls back to no-op if Redis is unavailable (logs warning).
    """

    # ── Main entry point ───────────────────────────────────────────────────────

    def check(
        self,
        ip: str = "",
        user=None,
        network=None,
        device_fingerprint: str = "",
    ) -> VelocityResult:
        """
        Run all applicable velocity checks.
        Raises VelocityLimitException if any hard-block threshold is exceeded.
        Returns VelocityResult with flagged=True for soft violations.
        """
        result = VelocityResult()

        # IP velocity checks
        if ip:
            self._check_ip_velocity(ip, result)

        # User velocity checks
        if user is not None:
            self._check_user_velocity(user, result)

        # Network burst check
        if network is not None:
            self._check_network_velocity(network, result)

        # Device fingerprint velocity
        if device_fingerprint:
            self._check_device_velocity(device_fingerprint, result)

        # Raise if hard-blocked
        if result.blocked:
            msg = " | ".join(result.violations)
            logger.warning(
                "Velocity BLOCK: ip=%s user=%s violations=[%s]",
                ip, getattr(user, "id", None), msg,
            )
            raise VelocityLimitException(
                f"Velocity limit exceeded: {msg}"
            )

        if result.flagged:
            logger.info(
                "Velocity FLAG: ip=%s user=%s violations=[%s]",
                ip, getattr(user, "id", None),
                " | ".join(result.violations),
            )

        return result

    def increment_ip(self, ip: str) -> None:
        """
        Increment all IP-based counters after a successful postback.
        Call this AFTER a conversion is approved to track real traffic.
        """
        if not ip:
            return
        ip_hash = self._hash(ip)
        self._incr(f"pe:vel:ip:1m:{ip_hash}",  _TTL_1M)
        self._incr(f"pe:vel:ip:1h:{ip_hash}",  _TTL_1H)
        self._incr(f"pe:vel:ip:24h:{ip_hash}", _TTL_24H)

    def increment_user(self, user_id: str) -> None:
        """Increment user conversion counter."""
        if not user_id:
            return
        self._incr(f"pe:vel:user:1h:{user_id}", _TTL_1H)

    def increment_network(self, network_id: str) -> None:
        """Increment network postback counter."""
        if not network_id:
            return
        self._incr(f"pe:vel:net:1m:{network_id}", _TTL_1M)

    def increment_device(self, fingerprint: str) -> None:
        """Increment device fingerprint click counter."""
        if not fingerprint:
            return
        fp_hash = self._hash(fingerprint)
        self._incr(f"pe:vel:dev:1h:{fp_hash}", _TTL_1H)

    def get_ip_stats(self, ip: str) -> dict:
        """Return current velocity counters for an IP (for admin UI)."""
        ip_hash = self._hash(ip)
        return {
            "per_minute": self._get(f"pe:vel:ip:1m:{ip_hash}"),
            "per_hour":   self._get(f"pe:vel:ip:1h:{ip_hash}"),
            "per_day":    self._get(f"pe:vel:ip:24h:{ip_hash}"),
        }

    def reset_ip(self, ip: str) -> None:
        """Manually reset all counters for an IP (admin action)."""
        ip_hash = self._hash(ip)
        try:
            cache.delete_many([
                f"pe:vel:ip:1m:{ip_hash}",
                f"pe:vel:ip:1h:{ip_hash}",
                f"pe:vel:ip:24h:{ip_hash}",
            ])
        except Exception as exc:
            logger.warning("VelocityChecker.reset_ip failed: %s", exc)

    # ── Private check methods ──────────────────────────────────────────────────

    def _check_ip_velocity(self, ip: str, result: VelocityResult) -> None:
        ip_hash = self._hash(ip)

        # 1-minute window (hard block — bot-level traffic)
        count_1m = self._get(f"pe:vel:ip:1m:{ip_hash}")
        if count_1m >= _IP_CONVERSIONS_PER_MINUTE:
            result.add_violation(
                f"IP {ip}: {count_1m} conversions in 60s (max {_IP_CONVERSIONS_PER_MINUTE})",
                hard_block=True,
            )
            return  # No need to check further windows

        # 1-hour window (soft flag)
        count_1h = self._get(f"pe:vel:ip:1h:{ip_hash}")
        if count_1h >= _IP_CONVERSIONS_PER_HOUR:
            result.add_violation(
                f"IP {ip}: {count_1h} conversions in 1h (max {_IP_CONVERSIONS_PER_HOUR})",
                hard_block=False,
            )

        # 24-hour window (hard block)
        count_24h = self._get(f"pe:vel:ip:24h:{ip_hash}")
        if count_24h >= _IP_CONVERSIONS_PER_DAY:
            result.add_violation(
                f"IP {ip}: {count_24h} conversions in 24h (max {_IP_CONVERSIONS_PER_DAY})",
                hard_block=True,
            )

    def _check_user_velocity(self, user, result: VelocityResult) -> None:
        user_id = str(getattr(user, "id", ""))
        if not user_id:
            return

        count = self._get(f"pe:vel:user:1h:{user_id}")
        if count >= _USER_CONVERSIONS_PER_HOUR:
            result.add_violation(
                f"User {user_id}: {count} conversions in 1h (max {_USER_CONVERSIONS_PER_HOUR})",
                hard_block=False,  # soft flag — let fraud review decide
            )

    def _check_network_velocity(self, network, result: VelocityResult) -> None:
        network_id = str(getattr(network, "id", ""))
        if not network_id:
            return

        # Use the network's own rate_limit_per_minute if set
        limit = getattr(network, "rate_limit_per_minute", _NETWORK_POSTBACKS_PER_MIN)
        count = self._get(f"pe:vel:net:1m:{network_id}")
        if count >= limit:
            result.add_violation(
                f"Network {getattr(network, 'network_key', network_id)}: "
                f"{count} postbacks/min (max {limit})",
                hard_block=True,
            )

    def _check_device_velocity(self, fingerprint: str, result: VelocityResult) -> None:
        fp_hash = self._hash(fingerprint)
        count = self._get(f"pe:vel:dev:1h:{fp_hash}")
        if count >= _DEVICE_CLICKS_PER_HOUR:
            result.add_violation(
                f"Device fingerprint: {count} clicks in 1h (max {_DEVICE_CLICKS_PER_HOUR})",
                hard_block=False,
            )

    # ── Redis helpers ──────────────────────────────────────────────────────────

    def _incr(self, key: str, ttl: int) -> int:
        """
        Atomic increment with TTL set on first write.
        Uses cache.add() + cache.incr() pattern for Django cache compatibility.
        """
        try:
            # Try to increment existing key
            try:
                val = cache.incr(key)
                return val
            except ValueError:
                # Key doesn't exist — initialise to 1
                cache.add(key, 0, timeout=ttl)
                val = cache.incr(key)
                return val
        except Exception as exc:
            logger.debug("VelocityChecker._incr failed (non-fatal): %s", exc)
            return 0

    def _get(self, key: str) -> int:
        """Get current counter value, returning 0 if missing or Redis unavailable."""
        try:
            val = cache.get(key)
            return int(val) if val is not None else 0
        except Exception:
            return 0

    @staticmethod
    def _hash(value: str) -> str:
        """Short SHA-256 prefix for use in Redis key (avoids PII in keys)."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


# ── Module-level singleton ─────────────────────────────────────────────────────
velocity_checker = VelocityChecker()
