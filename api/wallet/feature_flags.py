# api/wallet/feature_flags.py
"""
Feature flag system — enable/disable features per user/tenant/global.
Allows gradual rollout, A/B testing, killswitch for features.

Usage:
    from .feature_flags import flags
    if flags.is_enabled("instant_payout", user=request.user):
        ...
"""
import logging
from typing import Optional
from django.core.cache import cache
from functools import wraps

logger = logging.getLogger("wallet.feature_flags")
FLAG_CACHE_TTL = 300

DEFAULT_FLAGS = {
    "wallet_enabled":        True,  "wallet_transfer":      True,
    "wallet_freeze":         True,  "withdrawal_bkash":     True,
    "withdrawal_nagad":      True,  "withdrawal_rocket":    True,
    "withdrawal_usdt":       True,  "withdrawal_paypal":    False,
    "withdrawal_stripe":     False, "withdrawal_batch":     True,
    "instant_payout":        True,  "earning_cap":          True,
    "earning_streak":        True,  "earning_geo_rates":    True,
    "earning_tier_bonus":    True,  "cpalead_offers":       True,
    "cpalead_smart_link":    True,  "cpalead_postback":     True,
    "cpalead_offer_wall":    False, "cpalead_content_lock": False,
    "kyc_required":          True,  "fraud_check":          True,
    "aml_check":             True,  "sanctions_check":      True,
    "2fa_withdrawal":        False, "websocket_balance":    True,
    "openai_support":        False, "import_export":        True,
    "pdf_statements":        True,  "savings_goals":        False,
    "virtual_cards":         False, "crypto_wallet":        False,
    "loan_product":          False,
}


class FeatureFlagService:
    """Feature flag evaluation with user/tenant/global hierarchy."""

    @staticmethod
    def is_enabled(flag_name: str, user=None, tenant=None) -> bool:
        if user and getattr(user, "is_staff", False):
            return True
        if user and getattr(user, "is_authenticated", False):
            val = cache.get(f"ff_user:{user.id}:{flag_name}")
            if val is not None:
                return bool(val)
        if tenant:
            val = cache.get(f"ff_tenant:{getattr(tenant,'id',0)}:{flag_name}")
            if val is not None:
                return bool(val)
        cache_key = f"ff_global:{flag_name}"
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)
        try:
            from .config import WalletConfig
            raw = WalletConfig.get(f"FF_{flag_name}")
            if raw is not None:
                result = str(raw).lower() in ("true", "1", "yes")
                cache.set(cache_key, result, FLAG_CACHE_TTL)
                return result
        except Exception:
            pass
        return DEFAULT_FLAGS.get(flag_name, False)

    @staticmethod
    def set_global(flag_name: str, enabled: bool) -> None:
        try:
            from .config import WalletConfig
            WalletConfig.set(f"FF_{flag_name}", "true" if enabled else "false")
            cache.delete(f"ff_global:{flag_name}")
        except Exception as e:
            logger.error(f"Flag set error: {e}")

    @staticmethod
    def set_for_user(flag_name: str, user, enabled: bool) -> None:
        cache.set(f"ff_user:{user.id}:{flag_name}", enabled, FLAG_CACHE_TTL * 10)

    @staticmethod
    def get_all(user=None) -> dict:
        return {n: FeatureFlagService.is_enabled(n, user=user) for n in DEFAULT_FLAGS}


flags = FeatureFlagService()


def require_flag(flag_name: str):
    """ViewSet action decorator — returns 403 if flag disabled."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not flags.is_enabled(flag_name, user=request.user):
                from rest_framework.response import Response
                return Response({
                    "success": False, "error": f"Feature '{flag_name}' not available.",
                    "code": "feature_disabled"
                }, status=403)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
