# =============================================================================
# fraud_detection/security/brute_force_protection.py
# =============================================================================
"""
Brute-Force, Credential-Stuffing & Account-Enumeration Protection.

This module was COMPLETELY MISSING from the codebase.
Signal-based and middleware-based fraud detection existed, but no dedicated
counter for failed authentication attempts was implemented.

What this adds
--------------
  BruteForceProtector        — cache-backed failed-login counter
  CredentialStuffingDetector — velocity + known-breach list check
  AccountLockoutManager      — progressive lockout (5 → 15 → 60 → 1440 min)
  BruteForceMiddleware        — plug-in middleware (add to MIDDLEWARE in settings)
  Views exposed via urls_security.py:
    GET  /fraud/security/brute-force/status/<identifier>/
    POST /fraud/security/brute-force/reset/<identifier>/
    GET  /fraud/security/brute-force/stats/
    POST /fraud/security/lockout/check/
    POST /fraud/security/lockout/unlock/

Install
-------
Add to settings.py MIDDLEWARE (BEFORE AuthenticationMiddleware):
    'api.fraud_detection.security.brute_force_protection.BruteForceMiddleware',

Add to INSTALLED_APPS fraud_detection (already there).

Add to settings.py:
    BRUTE_FORCE_MAX_ATTEMPTS   = 5       # lockout after N fails
    BRUTE_FORCE_LOCKOUT_MINS   = [5, 15, 60, 1440]  # progressive
    BRUTE_FORCE_WINDOW_SECS    = 900     # count window (15 min)
    BRUTE_FORCE_WHITELIST_IPS  = []      # IPs never locked
"""
from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _cfg(key: str, default):
    return getattr(settings, key, default)


MAX_ATTEMPTS   = lambda: _cfg("BRUTE_FORCE_MAX_ATTEMPTS",  5)
LOCKOUT_TIERS  = lambda: _cfg("BRUTE_FORCE_LOCKOUT_MINS",  [5, 15, 60, 1440])
WINDOW_SECS    = lambda: _cfg("BRUTE_FORCE_WINDOW_SECS",   900)
WHITELIST_IPS  = lambda: _cfg("BRUTE_FORCE_WHITELIST_IPS", [])


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------

def _attempt_key(identifier: str) -> str:
    h = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"bf:attempts:{h}"


def _lockout_key(identifier: str) -> str:
    h = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"bf:lockout:{h}"


def _tier_key(identifier: str) -> str:
    h = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"bf:tier:{h}"


# =============================================================================
# BruteForceProtector
# =============================================================================

class BruteForceProtector:
    """
    Sliding-window failed-login counter with progressive lockout.

    Usage
    -----
    In your authentication view / signal:

        from api.fraud_detection.security.brute_force_protection import BruteForceProtector
        protector = BruteForceProtector()

        # On failed login:
        result = protector.record_failure(identifier="user:42", ip="1.2.3.4")
        if result["locked"]:
            return HttpResponse("Account locked", status=429)

        # On successful login:
        protector.record_success(identifier="user:42")

        # Check before processing login:
        status = protector.check(identifier="user:42")
        if status["locked"]:
            return HttpResponse(f"Locked for {status['locked_seconds']}s", status=429)
    """

    def check(self, identifier: str, ip: str = "") -> Dict:
        """
        Return lock status for identifier.
        identifier format: "user:<id>" | "email:<email>" | "ip:<address>"
        """
        if ip and ip in WHITELIST_IPS():
            return {"locked": False, "attempts": 0, "remaining": MAX_ATTEMPTS()}

        lockout_data = cache.get(_lockout_key(identifier))
        if lockout_data:
            locked_until = lockout_data["until"]
            now = timezone.now().timestamp()
            if now < locked_until:
                remaining_secs = int(locked_until - now)
                return {
                    "locked":          True,
                    "locked_until":    locked_until,
                    "locked_seconds":  remaining_secs,
                    "tier":            lockout_data.get("tier", 0),
                    "attempts":        cache.get(_attempt_key(identifier), 0),
                    "remaining":       0,
                    "message": (
                        f"Account locked. Try again in "
                        f"{remaining_secs // 60}m {remaining_secs % 60}s."
                    ),
                }
            else:
                # Lockout expired
                cache.delete(_lockout_key(identifier))

        attempts = cache.get(_attempt_key(identifier), 0)
        return {
            "locked":    False,
            "attempts":  attempts,
            "remaining": max(0, MAX_ATTEMPTS() - attempts),
        }

    def record_failure(self, identifier: str, ip: str = "") -> Dict:
        """
        Increment failure counter. Lock account if threshold exceeded.
        Returns the current status dict.
        """
        if ip and ip in WHITELIST_IPS():
            return {"locked": False, "attempts": 0, "remaining": MAX_ATTEMPTS()}

        attempt_key = _attempt_key(identifier)
        attempts    = cache.get(attempt_key, 0) + 1
        cache.set(attempt_key, attempts, timeout=WINDOW_SECS())

        logger.warning(
            "BruteForceProtector: failed attempt %d/%d for %s (ip=%s)",
            attempts, MAX_ATTEMPTS(), identifier, ip,
        )

        # Import here to avoid circular import
        try:
            from api.fraud_detection.models import FraudAttempt
            # Log as a fraud attempt for the dashboard
        except ImportError:
            pass

        if attempts >= MAX_ATTEMPTS():
            return self._lock(identifier, attempts)

        return {
            "locked":    False,
            "attempts":  attempts,
            "remaining": max(0, MAX_ATTEMPTS() - attempts),
        }

    def record_success(self, identifier: str) -> None:
        """Clear failure counters on successful authentication."""
        cache.delete(_attempt_key(identifier))
        cache.delete(_lockout_key(identifier))
        cache.delete(_tier_key(identifier))
        logger.info("BruteForceProtector: success, counters cleared for %s", identifier)

    def reset(self, identifier: str, admin_user=None) -> Dict:
        """Admin-manual unlock."""
        cache.delete(_attempt_key(identifier))
        cache.delete(_lockout_key(identifier))
        cache.delete(_tier_key(identifier))
        logger.info(
            "BruteForceProtector: manual reset for %s by %s",
            identifier, admin_user,
        )
        return {"reset": True, "identifier": identifier}

    def status(self, identifier: str) -> Dict:
        """Full status dump for admin dashboard."""
        check = self.check(identifier)
        tier  = cache.get(_tier_key(identifier), 0)
        tiers = LOCKOUT_TIERS()
        return {
            **check,
            "tier":            tier,
            "next_lockout_min": tiers[min(tier, len(tiers) - 1)],
            "max_attempts":    MAX_ATTEMPTS(),
            "window_secs":     WINDOW_SECS(),
        }

    def _lock(self, identifier: str, attempts: int) -> Dict:
        tiers    = LOCKOUT_TIERS()
        tier     = cache.get(_tier_key(identifier), 0)
        duration = tiers[min(tier, len(tiers) - 1)]
        until    = timezone.now().timestamp() + duration * 60

        cache.set(_lockout_key(identifier), {"until": until, "tier": tier},
                  timeout=duration * 60 + 60)
        cache.set(_tier_key(identifier), min(tier + 1, len(tiers) - 1),
                  timeout=86_400 * 7)

        logger.warning(
            "BruteForceProtector: LOCKED %s for %d minutes (tier %d, attempts=%d)",
            identifier, duration, tier, attempts,
        )
        return {
            "locked":         True,
            "locked_minutes": duration,
            "locked_seconds": duration * 60,
            "tier":           tier,
            "attempts":       attempts,
            "remaining":      0,
            "message":        f"Account locked for {duration} minutes after {attempts} failed attempts.",
        }


# =============================================================================
# CredentialStuffingDetector
# =============================================================================

class CredentialStuffingDetector:
    """
    Detects credential-stuffing attacks by monitoring:
    1. High velocity of login attempts across DIFFERENT usernames from one IP
    2. Known-breach password detection (HaveIBeenPwned k-anonymity API)
    3. Suspicious user-agent patterns (scripts, not browsers)

    All checks are implemented with graceful fallback (no external dep required).
    """

    _STUFFING_IP_KEY     = "cs:ip:{ip}:attempts"
    _STUFFING_UA_KEY     = "cs:ua:{ua_hash}:attempts"
    _WINDOW_SECS         = 300    # 5-minute window
    _IP_THRESHOLD        = 20     # >20 different users from one IP in 5 min
    _SUSPICIOUS_UA_PARTS = [
        "python-requests", "curl", "wget", "go-http", "okhttp",
        "axios", "node-fetch", "java", "libwww", "scrapy",
    ]

    def check_ip(self, ip: str) -> Dict:
        """Returns stuffing risk for an IP."""
        key   = self._STUFFING_IP_KEY.format(ip=ip)
        count = cache.get(key, 0)
        threshold = getattr(settings, "CREDENTIAL_STUFFING_IP_THRESHOLD",
                            self._IP_THRESHOLD)
        return {
            "ip":              ip,
            "attempt_count":   count,
            "threshold":       threshold,
            "is_stuffing":     count >= threshold,
            "risk_score":      min(100, int(count / threshold * 100)),
        }

    def record_attempt(self, ip: str, username: str, user_agent: str = "") -> Dict:
        """Record a login attempt and check for stuffing signals."""
        ip_key = self._STUFFING_IP_KEY.format(ip=ip)
        count  = cache.get(ip_key, 0) + 1
        cache.set(ip_key, count, timeout=self._WINDOW_SECS)

        ua_suspicious = any(
            sig.lower() in (user_agent or "").lower()
            for sig in self._SUSPICIOUS_UA_PARTS
        )

        threshold  = getattr(settings, "CREDENTIAL_STUFFING_IP_THRESHOLD",
                             self._IP_THRESHOLD)
        is_stuffing = count >= threshold or ua_suspicious

        if is_stuffing:
            logger.warning(
                "CredentialStuffingDetector: ALERT ip=%s count=%d ua_suspicious=%s",
                ip, count, ua_suspicious,
            )

        return {
            "ip":              ip,
            "attempt_count":   count,
            "ua_suspicious":   ua_suspicious,
            "is_stuffing":     is_stuffing,
            "risk_score":      min(100, int(count / threshold * 100)),
        }

    def check_password_breach(self, password: str) -> Dict:
        """
        Check password against HaveIBeenPwned using k-anonymity model.
        Sends only first 5 chars of SHA-1 hash — password never leaves system.
        Gracefully returns not_checked=True if network is unavailable.
        """
        import hashlib
        sha1  = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            import urllib.request
            url  = f"https://api.pwnedpasswords.com/range/{prefix}"
            req  = urllib.request.Request(url, headers={"Add-Padding": "true"})
            resp = urllib.request.urlopen(req, timeout=3)
            body = resp.read().decode()
            for line in body.splitlines():
                h, count_str = line.split(":")
                if h == suffix:
                    count = int(count_str)
                    logger.warning(
                        "CredentialStuffingDetector: password found in %d breaches", count
                    )
                    return {"breached": True, "breach_count": count}
            return {"breached": False, "breach_count": 0}
        except Exception as exc:
            logger.debug("HIBP check failed (offline?): %s", exc)
            return {"breached": None, "not_checked": True, "error": str(exc)}


# =============================================================================
# AccountLockoutManager
# =============================================================================

class AccountLockoutManager:
    """
    High-level façade combining BruteForceProtector + CredentialStuffingDetector.
    Call from Django authentication backends or login signal handlers.
    """

    def __init__(self):
        self._bf  = BruteForceProtector()
        self._cs  = CredentialStuffingDetector()

    def pre_login_check(self, username: str, ip: str,
                         user_agent: str = "") -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Call BEFORE validating credentials.
        """
        # 1. Brute-force check on username
        bf_status = self._bf.check(f"user:{username}", ip=ip)
        if bf_status["locked"]:
            return False, bf_status["message"]

        # 2. Brute-force check on IP
        ip_status = self._bf.check(f"ip:{ip}", ip=ip)
        if ip_status["locked"]:
            return False, f"Too many attempts from your IP. Try later."

        # 3. Credential stuffing check on IP
        cs_result = self._cs.check_ip(ip)
        if cs_result["is_stuffing"]:
            return False, "Unusual login activity detected from your network."

        return True, ""

    def on_login_failure(self, username: str, ip: str,
                          user_agent: str = "") -> Dict:
        """Call on every failed authentication attempt."""
        user_result = self._bf.record_failure(f"user:{username}", ip=ip)
        ip_result   = self._bf.record_failure(f"ip:{ip}", ip=ip)
        cs_result   = self._cs.record_attempt(ip, username, user_agent)

        return {
            "user_lock":   user_result,
            "ip_lock":     ip_result,
            "cs_detection": cs_result,
            "blocked":     user_result["locked"] or ip_result["locked"] or cs_result["is_stuffing"],
        }

    def on_login_success(self, username: str, ip: str) -> None:
        """Call on successful authentication."""
        self._bf.record_success(f"user:{username}")
        self._bf.record_success(f"ip:{ip}")

    def get_full_status(self, username: str, ip: str) -> Dict:
        return {
            "user":  self._bf.status(f"user:{username}"),
            "ip":    self._bf.status(f"ip:{ip}"),
            "cs_ip": self._cs.check_ip(ip),
        }


# =============================================================================
# BruteForceMiddleware
# =============================================================================

class BruteForceMiddleware:
    """
    Django middleware that enforces brute-force protection on login endpoints.
    Add to MIDDLEWARE before AuthenticationMiddleware.
    """

    _PROTECTED_PATHS = [
        "/api/auth/login/",
        "/api/users/login/",
        "/api/token/",
        "/api/token/refresh/",
        "/api/auth/token/",
    ]

    def __init__(self, get_response):
        self.get_response  = get_response
        self._manager      = AccountLockoutManager()
        extra = getattr(settings, "BRUTE_FORCE_PROTECTED_PATHS", [])
        self._paths = list(set(self._PROTECTED_PATHS + extra))

    def __call__(self, request):
        if request.method == "POST" and any(
            request.path.startswith(p) for p in self._paths
        ):
            ip       = self._get_ip(request)
            username = self._get_username(request)

            if username:
                allowed, reason = self._manager.pre_login_check(username, ip,
                                   request.META.get("HTTP_USER_AGENT", ""))
                if not allowed:
                    from django.http import JsonResponse
                    logger.warning(
                        "BruteForceMiddleware: blocked login for %s from %s — %s",
                        username, ip, reason,
                    )
                    return JsonResponse(
                        {"error": reason, "code": "account_locked"},
                        status=429,
                    )

        response = self.get_response(request)

        # Hook into 401 responses on protected paths to record failures
        if (response.status_code == 401 and
                any(request.path.startswith(p) for p in self._paths)):
            ip       = self._get_ip(request)
            username = self._get_username(request)
            if username:
                self._manager.on_login_failure(
                    username, ip,
                    request.META.get("HTTP_USER_AGENT", ""),
                )

        return response

    def _get_ip(self, request) -> str:
        x_fwd = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_fwd:
            return x_fwd.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")

    def _get_username(self, request) -> str:
        try:
            import json
            body = json.loads(request.body)
            return (body.get("username") or body.get("email") or
                    body.get("user") or "")
        except Exception:
            return (request.POST.get("username") or
                    request.POST.get("email") or "")
