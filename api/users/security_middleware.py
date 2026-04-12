# api/users/security_middleware.py
# ============================================================
# Security Middleware — CAPTCHA, IP Block, Suspicious Activity
# settings.py তে MIDDLEWARE list এ add করো:
# 'api.users.security_middleware.SecurityMiddleware'
# ============================================================

import json
import logging
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Config — settings.py তে override করতে পারবে
BLOCKED_IPS_CACHE_KEY = "blocked_ips_set"
SENSITIVE_ENDPOINTS = getattr(settings, 'SENSITIVE_ENDPOINTS', [
    '/api/auth/register/',
    '/api/auth/login/',
    '/api/wallet/withdraw/',
    '/api/users/kyc/',
    '/api/users/2fa/',
])

RATE_LIMITS = getattr(settings, 'ENDPOINT_RATE_LIMITS', {
    '/api/auth/register/': {'limit': 5, 'window': 3600},    # 1 ঘণ্টায় 5 বার
    '/api/auth/login/': {'limit': 10, 'window': 900},       # 15 মিনিটে 10 বার
    '/api/wallet/withdraw/': {'limit': 3, 'window': 86400}, # দিনে 3 বার
    '/api/users/2fa/': {'limit': 5, 'window': 300},         # 5 মিনিটে 5 বার
})


class SecurityMiddleware:
    """
    সব request এ security check করো।
    Order: IP Block → Rate Limit → Suspicious Activity
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # API request এ শুধু apply করো
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        ip = self._get_client_ip(request)

        # 1. IP Blocked কিনা check করো
        if self._is_ip_blocked(ip):
            logger.warning(f"Blocked IP attempted access: {ip} → {request.path}")
            return JsonResponse({
                'error': 'Access denied.',
                'code': 'IP_BLOCKED'
            }, status=403)

        # 2. Endpoint rate limit check করো
        rate_check = self._check_rate_limit(request, ip)
        if not rate_check['allowed']:
            return JsonResponse({
                'error': f"অনেক বার request করেছেন। {rate_check['retry_after']} সেকেন্ড পরে চেষ্টা করুন।",
                'code': 'RATE_LIMITED',
                'retry_after': rate_check['retry_after']
            }, status=429)

        response = self.get_response(request)

        # 3. Failed responses track করো (fraud detection)
        if hasattr(response, 'status_code'):
            if response.status_code in [401, 403] and request.path in SENSITIVE_ENDPOINTS:
                self._track_failed_attempt(ip, request.path)

        return response

    def _get_client_ip(self, request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _is_ip_blocked(self, ip: str) -> bool:
        """Redis cache তে blocked IP আছে কিনা check করো"""
        # DB থেকে check — IPReputation model
        cache_key = f"ip_blocked:{ip}"
        blocked = cache.get(cache_key)
        if blocked is not None:
            return blocked

        try:
            from api.users.models import IPReputation
            rep = IPReputation.objects.filter(ip_address=ip).first()
            is_blocked = rep and rep.is_blacklisted
            # 5 মিনিট cache করো
            cache.set(cache_key, is_blocked, timeout=300)
            return is_blocked
        except Exception:
            return False

    def _check_rate_limit(self, request, ip: str) -> dict:
        """Per-endpoint, per-IP rate limiting"""
        path = request.path

        # Exact match খোঁজো
        limit_config = None
        for endpoint, config in RATE_LIMITS.items():
            if path.startswith(endpoint):
                limit_config = config
                break

        if not limit_config:
            return {'allowed': True}

        limit = limit_config['limit']
        window = limit_config['window']

        cache_key = f"rate_limit:{ip}:{path}"
        current = cache.get(cache_key, 0)

        if current >= limit:
            return {'allowed': False, 'retry_after': window}

        # Increment করো
        pipe = cache
        new_val = current + 1
        cache.set(cache_key, new_val, timeout=window)

        return {'allowed': True}

    def _track_failed_attempt(self, ip: str, path: str):
        """বারবার fail করলে auto-block করো"""
        key = f"failed_attempts:{ip}:{path}"
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, timeout=3600)

        # 20+ বার fail → auto block (1 ঘণ্টা)
        if attempts >= 20:
            try:
                from api.users.models import IPReputation
                rep, _ = IPReputation.objects.get_or_create(ip_address=ip)
                rep.failed_login_attempts += 1
                rep.last_failed_login = timezone.now()
                if attempts >= 20:
                    rep.is_blacklisted = True
                    rep.blacklist_reason = f"Auto-blocked: {attempts} failed attempts on {path}"
                    rep.reputation = 'blocked'
                rep.save()
                # Cache update করো
                cache.set(f"ip_blocked:{ip}", True, timeout=300)
                logger.warning(f"IP {ip} auto-blocked after {attempts} failed attempts")
            except Exception as e:
                logger.error(f"Auto-block failed for IP {ip}: {e}")


# ============================================================
# CAPTCHA VALIDATOR UTILITY
# ============================================================

class CaptchaValidator:
    """
    Google reCAPTCHA v3 validate করো।
    Frontend থেকে token আসবে, backend এ verify করো।

    settings.py তে add করো:
    RECAPTCHA_SECRET_KEY = 'your_secret_key'
    RECAPTCHA_SCORE_THRESHOLD = 0.5
    """

    VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
    THRESHOLD = getattr(settings, 'RECAPTCHA_SCORE_THRESHOLD', 0.5)

    @classmethod
    def verify(cls, token: str, action: str = None) -> dict:
        """
        reCAPTCHA token verify করো।
        Return: {'valid': bool, 'score': float, 'action': str}
        """
        import urllib.request
        import urllib.parse

        secret_key = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
        if not secret_key:
            # Development mode — skip
            logger.warning("RECAPTCHA_SECRET_KEY not set, skipping CAPTCHA validation")
            return {'valid': True, 'score': 1.0, 'action': action}

        try:
            data = urllib.parse.urlencode({
                'secret': secret_key,
                'response': token
            }).encode()

            req = urllib.request.Request(cls.VERIFY_URL, data=data)
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode())

            is_valid = (
                result.get('success', False)
                and result.get('score', 0) >= cls.THRESHOLD
                and (action is None or result.get('action') == action)
            )

            return {
                'valid': is_valid,
                'score': result.get('score', 0),
                'action': result.get('action'),
                'error': result.get('error-codes', []) if not is_valid else []
            }

        except Exception as e:
            logger.error(f"CAPTCHA verification failed: {e}")
            # Network error তে allow করো (fail open) — production এ fail closed করতে পারো
            return {'valid': True, 'score': 0.5, 'action': action}