# api/payment_gateways/feature_flags.py
# Feature flag system — enable/disable features without deploying code
# Used for gradual rollouts, A/B testing, gateway kills, beta features
# "Do not summarize or skip any logic. Provide the full code."

import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Default feature flags ──────────────────────────────────────────────────────
DEFAULT_FLAGS: Dict[str, Any] = {
    # Gateway features
    'bkash_deposits':           True,
    'bkash_withdrawals':        True,
    'nagad_deposits':           True,
    'nagad_withdrawals':        True,
    'sslcommerz_deposits':      True,
    'amarpay_deposits':         True,
    'upay_deposits':            True,
    'shurjopay_deposits':       True,
    'stripe_deposits':          True,
    'paypal_deposits':          True,
    'payoneer_withdrawals':     True,
    'wire_withdrawals':         True,
    'ach_withdrawals':          True,
    'crypto_deposits':          True,
    'crypto_withdrawals':       True,
    'usdt_fastpay':             True,

    # Publisher features
    'publisher_registration':   True,
    'publisher_smartlinks':     True,
    'publisher_content_locker': True,
    'publisher_offerwall':      True,
    'publisher_referral':       True,
    'publisher_ab_testing':     True,
    'publisher_leaderboard':    True,
    'publisher_fast_pay':       True,
    'publisher_instant_pay':    False,  # Beta
    'publisher_api_access':     True,

    # Advertiser features
    'advertiser_registration':  True,
    'advertiser_self_serve':    True,
    'advertiser_rtb':           True,
    'advertiser_campaign_budget': True,
    'advertiser_conversion_goals': True,

    # Tracking features
    'pixel_tracking':           True,
    's2s_postback':             True,
    'fingerprint_tracking':     True,
    'click_fraud_ml':           True,
    'geo_pricing':              True,
    'traffic_quality_scoring':  True,

    # AI features
    'ai_fraud_scoring':         True,
    'ai_offer_recommendations': True,
    'ai_support_assistant':     True,
    'ai_campaign_analysis':     False,  # Beta
    'openai_integration':       True,

    # System features
    'websocket_realtime':       True,
    'push_notifications':       True,
    'email_notifications':      True,
    'sms_notifications':        False,  # Requires Twilio setup
    'sanctions_screening':      True,
    'aml_checks':               True,
    'kyc_required':             False,  # Disabled by default
    'multi_tenancy':            False,  # Enterprise only
    'invoice_pdf':              True,
    'data_export':              True,
    'maintenance_mode':         False,
}

CACHE_TTL = 300  # 5 minutes


class FeatureFlag:
    """
    Feature flag manager for payment_gateways.

    Features can be controlled:
        1. From settings.PAYMENT_GATEWAY_FEATURES dict
        2. From database FeatureFlagConfig model
        3. Per-user/per-tenant override
        4. Admin toggle at runtime

    Priority: per-user > DB > settings > default

    Usage:
        ff = FeatureFlag()
        if ff.is_enabled('usdt_fastpay'):
            process_fastpay()
        if ff.is_enabled('ai_fraud_scoring', user=request.user):
            run_ai_check()
    """

    def is_enabled(self, flag_name: str, user=None,
                    tenant=None, default: bool = None) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Flag identifier (e.g. 'usdt_fastpay')
            user:      Optional user for per-user override
            tenant:    Optional tenant for multi-tenant override
            default:   Default if flag not found (falls back to DEFAULT_FLAGS)

        Returns:
            bool: True if feature is enabled
        """
        # 1. Check maintenance mode — blocks most features
        if flag_name != 'maintenance_mode' and self._get_flag('maintenance_mode'):
            MAINTENANCE_ALLOWED = {'gateway_status', 'health_check', 'maintenance_mode'}
            if flag_name not in MAINTENANCE_ALLOWED:
                return False

        # 2. Per-user override
        if user:
            user_override = self._get_user_override(user, flag_name)
            if user_override is not None:
                return user_override

        # 3. Per-tenant override
        if tenant:
            tenant_override = self._get_tenant_override(tenant, flag_name)
            if tenant_override is not None:
                return tenant_override

        # 4. DB flag
        db_value = self._get_db_flag(flag_name)
        if db_value is not None:
            return db_value

        # 5. Settings override
        settings_flags = getattr(settings, 'PAYMENT_GATEWAY_FEATURES', {})
        if flag_name in settings_flags:
            return bool(settings_flags[flag_name])

        # 6. Default
        if default is not None:
            return default
        return DEFAULT_FLAGS.get(flag_name, True)

    def enable(self, flag_name: str, actor=None):
        """Enable a feature flag (saves to DB)."""
        self._set_db_flag(flag_name, True, actor)
        cache.delete(f'ff:{flag_name}')
        logger.info(f'Feature flag ENABLED: {flag_name} by {getattr(actor, "email", "system")}')

    def disable(self, flag_name: str, actor=None):
        """Disable a feature flag (saves to DB)."""
        self._set_db_flag(flag_name, False, actor)
        cache.delete(f'ff:{flag_name}')
        logger.info(f'Feature flag DISABLED: {flag_name} by {getattr(actor, "email", "system")}')

    def toggle(self, flag_name: str, actor=None) -> bool:
        """Toggle a flag. Returns new state."""
        current = self.is_enabled(flag_name)
        if current:
            self.disable(flag_name, actor)
        else:
            self.enable(flag_name, actor)
        return not current

    def get_all_flags(self) -> Dict[str, bool]:
        """Get current state of all flags."""
        flags = dict(DEFAULT_FLAGS)
        settings_flags = getattr(settings, 'PAYMENT_GATEWAY_FEATURES', {})
        flags.update({k: bool(v) for k, v in settings_flags.items()})
        try:
            from api.payment_gateways.models.gateway_config import FeatureFlagConfig
            for flag in FeatureFlagConfig.objects.filter(is_active=True):
                flags[flag.name] = flag.is_enabled
        except Exception:
            pass
        return flags

    def get_gateway_flags(self, gateway: str) -> dict:
        """Get all flags for a specific gateway."""
        return {
            'deposits':    self.is_enabled(f'{gateway}_deposits'),
            'withdrawals': self.is_enabled(f'{gateway}_withdrawals'),
            'enabled':     self.is_enabled(f'{gateway}_deposits') or self.is_enabled(f'{gateway}_withdrawals'),
        }

    def require(self, flag_name: str, user=None):
        """Raise exception if flag is disabled."""
        if not self.is_enabled(flag_name, user=user):
            from api.payment_gateways.exceptions import FeatureDisabledException
            raise FeatureDisabledException(
                f'Feature "{flag_name}" is currently disabled. '
                f'Please contact support if you need access.'
            )

    def is_gateway_enabled(self, gateway: str, operation: str = 'deposit') -> bool:
        """Check if a specific gateway operation is enabled."""
        flag = f'{gateway}_{operation}s'  # e.g. 'bkash_deposits'
        return self.is_enabled(flag)

    def get_enabled_gateways(self, operation: str = 'deposit') -> List[str]:
        """Get list of enabled gateways for an operation."""
        from api.payment_gateways.choices import ALL_GATEWAYS
        return [
            gw for gw in ALL_GATEWAYS
            if self.is_enabled(f'{gw}_{operation}s')
        ]

    # ── Private helpers ────────────────────────────────────────────────────────
    def _get_flag(self, flag_name: str) -> bool:
        """Get flag with caching."""
        cached = cache.get(f'ff:{flag_name}')
        if cached is not None:
            return cached
        value = self._get_db_flag(flag_name)
        if value is None:
            value = getattr(settings, 'PAYMENT_GATEWAY_FEATURES', {}).get(
                flag_name, DEFAULT_FLAGS.get(flag_name, True)
            )
        cache.set(f'ff:{flag_name}', value, CACHE_TTL)
        return value

    def _get_db_flag(self, flag_name: str) -> Optional[bool]:
        """Get flag value from database."""
        try:
            from api.payment_gateways.models.gateway_config import FeatureFlagConfig
            flag = FeatureFlagConfig.objects.get(name=flag_name)
            return flag.is_enabled
        except Exception:
            return None

    def _set_db_flag(self, flag_name: str, value: bool, actor=None):
        """Set flag value in database."""
        try:
            from api.payment_gateways.models.gateway_config import FeatureFlagConfig
            FeatureFlagConfig.objects.update_or_create(
                name=flag_name,
                defaults={
                    'is_enabled': value,
                    'changed_by': getattr(actor, 'email', 'system'),
                }
            )
        except Exception as e:
            logger.debug(f'Could not save feature flag to DB: {e}')
            # Fall back to cache-only
            cache.set(f'ff:{flag_name}', value, 86400)

    def _get_user_override(self, user, flag_name: str) -> Optional[bool]:
        """Check user-specific flag override."""
        cache_key = f'ff_user:{user.id}:{flag_name}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from api.payment_gateways.models.gateway_config import UserFeatureOverride
            override = UserFeatureOverride.objects.get(user=user, flag_name=flag_name)
            value = override.is_enabled
            cache.set(cache_key, value, CACHE_TTL)
            return value
        except Exception:
            return None

    def _get_tenant_override(self, tenant, flag_name: str) -> Optional[bool]:
        """Check tenant-specific flag override."""
        try:
            from api.payment_gateways.models.gateway_config import TenantFeatureOverride
            override = TenantFeatureOverride.objects.get(tenant=tenant, flag_name=flag_name)
            return override.is_enabled
        except Exception:
            return None


# ── Decorator ──────────────────────────────────────────────────────────────────
def require_feature(flag_name: str):
    """
    View decorator: return 503 if feature flag is disabled.

    Usage:
        @require_feature('usdt_fastpay')
        def my_view(request):
            ...
    """
    import functools
    from rest_framework.response import Response

    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            ff = FeatureFlag()
            user = getattr(request, 'user', None)
            if not ff.is_enabled(flag_name, user=user):
                return Response({
                    'success': False,
                    'error':   f'Feature "{flag_name}" is currently unavailable.',
                    'code':    'FEATURE_DISABLED',
                }, status=503)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# Global singleton
feature_flags = FeatureFlag()
