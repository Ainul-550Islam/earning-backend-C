# =============================================================================
# fraud_detection/security/security_views.py  (DRY-refactored)
# =============================================================================
"""
Security protection HTTP API — DRY-refactored.

DRY improvements
-----------------
• Extends FraudBaseView / FraudAdminView — removes 12 duplicate
  throttle_classes, 12 permission_classes, and 2 _ok/_err definitions.
• cache_append() from utils replaces inline _log_attack() helper.
• _get_protector(), _get_manager(), _get_cs() defined once as module helpers.
• _ATTACK_LOG_KEY defined once at module level.
"""
from __future__ import annotations
import logging
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudBaseView, FraudAdminView, cache_append

logger = logging.getLogger(__name__)
_ATTACK_LOG_KEY = "security:attack_log"


# ---------------------------------------------------------------------------
# Service loaders — defined once
# ---------------------------------------------------------------------------

def _get_protector():
    from api.fraud_detection.security.brute_force_protection import BruteForceProtector
    return BruteForceProtector()


def _get_manager():
    from api.fraud_detection.security.brute_force_protection import AccountLockoutManager
    return AccountLockoutManager()


def _get_cs():
    from api.fraud_detection.security.brute_force_protection import CredentialStuffingDetector
    return CredentialStuffingDetector()


def _log_attack(attack_type: str, identifier: str, ip: str, meta: dict = None) -> None:
    """Log a security attack event — uses shared cache_append (defined once)."""
    cache_append(
        _ATTACK_LOG_KEY,
        {"type": attack_type, "identifier": identifier,
         "ip": ip, "meta": meta or {},
         "timestamp": timezone.now().isoformat()},
        max_entries=2000, ttl=86_400 * 30,
    )


# =============================================================================
# Brute-Force views
# =============================================================================

class BruteForceStatusAPIView(FraudAdminView):
    """GET /fraud/security/brute-force/status/<identifier>/"""
    def get(self, request, identifier: str):
        try:
            return self.ok({"identifier": identifier,
                             **_get_protector().status(identifier)})
        except Exception as exc:
            logger.exception("BruteForceStatusAPIView identifier=%s: %s", identifier, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BruteForceResetAPIView(FraudAdminView):
    """POST /fraud/security/brute-force/reset/<identifier>/"""
    def post(self, request, identifier: str):
        try:
            return self.ok(_get_protector().reset(identifier,
                                                   admin_user=request.user))
        except Exception as exc:
            logger.exception("BruteForceResetAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BruteForceCheckAPIView(FraudBaseView):
    """POST /fraud/security/brute-force/check/"""
    def post(self, request):
        username   = request.data.get("username") or request.data.get("email","")
        ip         = request.data.get("ip","")
        user_agent = request.data.get("user_agent","")
        if not username: return self.err("username or email is required.")
        if not ip:       return self.err("ip is required.")
        try:
            allowed, reason = _get_manager().pre_login_check(username, ip, user_agent)
            return self.ok({"allowed": allowed, "reason": reason,
                             "username": username, "ip": ip})
        except Exception as exc:
            logger.exception("BruteForceCheckAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BruteForceStatsAPIView(FraudAdminView):
    """GET /fraud/security/brute-force/stats/"""
    def get(self, request):
        log     = cache.get(_ATTACK_LOG_KEY, [])
        by_type: dict = {}
        for e in log:
            t = e.get("type","unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return self.ok({"total_attack_log_entries": len(log),
                         "by_type": by_type, "recent_attacks": log[:10]})


# =============================================================================
# Lockout views
# =============================================================================

class LockoutCheckAPIView(FraudAdminView):
    """POST /fraud/security/lockout/check/"""
    def post(self, request):
        username = request.data.get("username","")
        ip       = request.data.get("ip","")
        if not username and not ip:
            return self.err("username or ip is required.")
        try:
            return self.ok(_get_manager().get_full_status(
                username or "unknown", ip or "0.0.0.0"))
        except Exception as exc:
            logger.exception("LockoutCheckAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class LockoutUnlockAPIView(FraudAdminView):
    """POST /fraud/security/lockout/unlock/"""
    def post(self, request):
        username = request.data.get("username","")
        ip       = request.data.get("ip","")
        if not username and not ip:
            return self.err("username or ip is required.")
        try:
            protector = _get_protector()
            results   = {}
            if username: results["user"] = protector.reset(f"user:{username}",
                                                            admin_user=request.user)
            if ip:       results["ip"]   = protector.reset(f"ip:{ip}",
                                                            admin_user=request.user)
            logger.info("LockoutUnlockAPIView: %s unlocked user=%s ip=%s",
                         request.user, username, ip)
            return self.ok({"unlocked": True, "results": results})
        except Exception as exc:
            logger.exception("LockoutUnlockAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Credential Stuffing views
# =============================================================================

class CredentialStuffingCheckIPAPIView(FraudBaseView):
    """POST /fraud/security/credential-stuffing/check-ip/"""
    def post(self, request):
        ip = request.data.get("ip")
        if not ip: return self.err("ip is required.")
        try:
            result = _get_cs().check_ip(ip)
            if result["is_stuffing"]:
                _log_attack("credential_stuffing", ip, ip,
                             {"attempt_count": result["attempt_count"]})
            return self.ok(result)
        except Exception as exc:
            logger.exception("CredentialStuffingCheckIPAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CredentialStuffingCheckPasswordAPIView(FraudAdminView):
    """POST /fraud/security/credential-stuffing/check-password/"""
    def post(self, request):
        password = request.data.get("password")
        if not password:     return self.err("password is required.")
        if len(password) < 4: return self.err("password too short to check.")
        try:
            return self.ok(_get_cs().check_password_breach(password))
        except Exception as exc:
            logger.exception("CredentialStuffingCheckPasswordAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CredentialStuffingReportAPIView(FraudAdminView):
    """POST /fraud/security/credential-stuffing/report/"""
    def post(self, request):
        ip         = request.data.get("ip","")
        username   = request.data.get("username","")
        user_agent = request.data.get("user_agent","")
        if not ip: return self.err("ip is required.")
        try:
            result = _get_cs().record_attempt(ip, username, user_agent)
            _log_attack("credential_stuffing_manual", username, ip,
                         {"user_agent": user_agent,
                          "risk_score": result["risk_score"]})
            return self.ok(result)
        except Exception as exc:
            logger.exception("CredentialStuffingReportAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Attack Log views
# =============================================================================

class AttackLogAPIView(FraudAdminView):
    """GET /fraud/security/attack-log/"""
    def get(self, request):
        try:
            limit = min(500, int(request.query_params.get("limit", 100)))
        except (TypeError, ValueError):
            limit = 100
        type_filter = request.query_params.get("type")
        log = cache.get(_ATTACK_LOG_KEY, [])
        if type_filter:
            log = [e for e in log if e.get("type") == type_filter]
        return self.ok({"total": len(log), "limit": limit, "events": log[:limit]})


class AttackLogStatsAPIView(FraudAdminView):
    """GET /fraud/security/attack-log/stats/"""
    def get(self, request):
        log     = cache.get(_ATTACK_LOG_KEY, [])
        by_type: dict = {}
        for e in log:
            t = e.get("type","unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return self.ok({"total_events": len(log), "by_type": by_type,
                         "most_recent": log[0] if log else None})


class AttackLogClearAPIView(FraudAdminView):
    """POST /fraud/security/attack-log/clear/"""
    def post(self, request):
        count = len(cache.get(_ATTACK_LOG_KEY, []))
        cache.delete(_ATTACK_LOG_KEY)
        logger.info("AttackLogClearAPIView: cleared %d events by %s", count, request.user)
        return self.ok({"cleared": count})
