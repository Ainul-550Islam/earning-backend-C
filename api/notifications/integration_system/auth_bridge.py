# integration_system/auth_bridge.py
"""Auth Bridge — Cross-module permission and authentication system."""
import logging
from functools import wraps
from typing import Dict, List, Optional, Set
from django.core.cache import cache
from .integ_constants import CacheTTL
from .integ_exceptions import CrossModulePermissionDenied, InvalidAPIKey
logger = logging.getLogger(__name__)

# Permission matrix: which module can access which other module
MODULE_PERMISSIONS: Dict[str, Set[str]] = {
    "notifications":  {"users", "wallet", "tasks", "referrals", "kyc", "fraud", "analytics"},
    "wallet":         {"users", "notifications", "withdrawals", "payments"},
    "tasks":          {"users", "notifications", "wallet", "fraud"},
    "withdrawals":    {"users", "wallet", "notifications", "kyc"},
    "referrals":      {"users", "wallet", "notifications"},
    "fraud":          {"users", "notifications", "wallet", "tasks"},
    "analytics":      {"users", "notifications", "wallet", "tasks", "referrals"},
    "admin":          {"*"},  # Admin can access all
    "postbacks":      {"wallet", "notifications", "offers"},
    "offers":         {"users", "wallet", "notifications"},
}


class AuthBridge:
    """Cross-module permission enforcement."""

    def check_permission(self, source_module: str, target_module: str, action: str = "read") -> bool:
        allowed = MODULE_PERMISSIONS.get(source_module, set())
        if "*" in allowed:
            return True
        return target_module in allowed

    def require_permission(self, source_module: str, target_module: str, action: str = "read"):
        if not self.check_permission(source_module, target_module, action):
            raise CrossModulePermissionDenied(source_module, target_module, action)

    def validate_api_key(self, api_key: str, service: str) -> Dict:
        """Validate an API key for an external service."""
        if not api_key:
            raise InvalidAPIKey(service)
        cache_key = f"apikey:valid:{service}:{api_key[:8]}"
        cached = cache.get(cache_key)
        if cached is not None:
            return {"valid": cached, "service": service, "from_cache": True}
        is_valid = self._check_api_key(api_key, service)
        cache.set(cache_key, is_valid, CacheTTL.MEDIUM)
        return {"valid": is_valid, "service": service, "from_cache": False}

    def _check_api_key(self, api_key: str, service: str) -> bool:
        from django.conf import settings
        key_map = {
            "sendgrid":  getattr(settings, "SENDGRID_API_KEY", ""),
            "twilio":    getattr(settings, "TWILIO_AUTH_TOKEN", ""),
            "shoho_sms": getattr(settings, "SHOHO_SMS_API_KEY", ""),
            "bkash":     getattr(settings, "BKASH_API_KEY", ""),
        }
        expected = key_map.get(service, "")
        if not expected:
            return True  # Unknown service — skip validation
        import hmac
        return hmac.compare_digest(api_key, expected)

    def get_module_permissions(self, module: str) -> Set[str]:
        return MODULE_PERMISSIONS.get(module, set())

    def grant_permission(self, source_module: str, target_module: str):
        MODULE_PERMISSIONS.setdefault(source_module, set()).add(target_module)

    def revoke_permission(self, source_module: str, target_module: str):
        if source_module in MODULE_PERMISSIONS:
            MODULE_PERMISSIONS[source_module].discard(target_module)


def require_module_permission(source_module: str, target_module: str):
    """Decorator to enforce cross-module permissions."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_bridge.require_permission(source_module, target_module)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


auth_bridge = AuthBridge()
