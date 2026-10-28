# api/djoyalty/feature_flags.py
"""
Djoyalty Feature Flags -- DB-backed live feature toggles।
Enable/disable features without deployment।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from functools import wraps
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Default flags -- all enabled by default
_DEFAULTS = {
    'spin_wheel':           True,
    'scratch_card':         True,
    'lottery':              True,
    'receipt_scan':         True,
    'eco_points':           True,
    'family_accounts':      True,
    'ai_personalization':   True,
    'offerwall':            True,
    'cpalead_integration':  True,
    'digital_wallet':       True,
    'cashout_bkash':        True,
    'cashout_nagad':        True,
    'cashout_bank':         True,
    'referral_program':     True,
    'leaderboard':          True,
    'quiz':                  True,   # Quiz reward feature (AUDIT FIX v4)
    'charity_redemption':   True,
    'coalition_earn':       True,
    'reward_catalog':       True,
    'smart_links':          True,
    'websocket_realtime':   False,  # Requires channels install
    'graphql_api':          False,  # Optional
    'web3_rewards':         False,  # Future feature
}


class FeatureFlags:
    """
    Feature flag manager -- DB-backed with memory cache।

    Usage:
        if FeatureFlags.is_enabled('spin_wheel', tenant=request.tenant):
            # show spin wheel
        FeatureFlags.enable('receipt_scan', tenant=my_tenant)
        FeatureFlags.disable('lottery')
    """

    _cache: dict = {}

    @classmethod
    def is_enabled(cls, flag: str, tenant=None) -> bool:
        """Check if a feature flag is enabled।"""
        cache_key = f'{tenant.id if tenant else "global"}:{flag}'

        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls._load_from_db(flag, tenant)

        return cls._cache[cache_key]

    @classmethod
    def _load_from_db(cls, flag: str, tenant=None) -> bool:
        """Load flag value from SystemConfig model।"""
        try:
            from .models.audit import SystemConfig
            cfg = SystemConfig.objects.filter(
                key=f'feature.{flag}',
                tenant=tenant,
            ).first()
            if cfg:
                return cfg.get_typed_value()
        except Exception:
            pass
        return _DEFAULTS.get(flag, True)

    @classmethod
    def enable(cls, flag: str, tenant=None):
        """Enable a feature flag।"""
        cls._set(flag, True, tenant)
        cache_key = f'{tenant.id if tenant else "global"}:{flag}'
        cls._cache[cache_key] = True
        logger.info('FeatureFlags: ENABLED %s (tenant=%s)', flag,
                    tenant.id if tenant else 'global')

    @classmethod
    def disable(cls, flag: str, tenant=None):
        """Disable a feature flag।"""
        cls._set(flag, False, tenant)
        cache_key = f'{tenant.id if tenant else "global"}:{flag}'
        cls._cache[cache_key] = False
        logger.info('FeatureFlags: DISABLED %s (tenant=%s)', flag,
                    tenant.id if tenant else 'global')

    @classmethod
    def _set(cls, flag: str, value: bool, tenant=None):
        """Save flag to DB।"""
        try:
            from .models.audit import SystemConfig
            SystemConfig.objects.update_or_create(
                key=f'feature.{flag}',
                tenant=tenant,
                defaults={
                    'value': 'true' if value else 'false',
                    'value_type': 'boolean',
                    'description': f'Feature flag: {flag}',
                },
            )
        except Exception as e:
            logger.error('FeatureFlags._set error: %s', e)

    @classmethod
    def all_flags(cls, tenant=None) -> dict:
        """Get all feature flags with current values।"""
        flags = dict(_DEFAULTS)
        try:
            from .models.audit import SystemConfig
            db_flags = SystemConfig.objects.filter(
                key__startswith='feature.',
                tenant=tenant,
            )
            for cfg in db_flags:
                key = cfg.key.replace('feature.', '')
                flags[key] = cfg.get_typed_value()
        except Exception:
            pass
        return flags

    @classmethod
    def clear_cache(cls):
        """Clear in-memory cache -- force reload from DB।"""
        cls._cache.clear()

    @classmethod
    def require_flag(cls, flag: str, error_msg: str = ''):
        """Decorator: require feature flag to be enabled for ViewSet action।"""
        def decorator(func):
            @wraps(func)
            def wrapper(self, request, *args, **kwargs):
                tenant = getattr(request, 'tenant', None)
                if not cls.is_enabled(flag, tenant=tenant):
                    return Response(
                        {'error': error_msg or f'Feature "{flag}" is not enabled.'},
                        status=403,
                    )
                return func(self, request, *args, **kwargs)
            return wrapper
        return decorator


# Module-level singleton
flags = FeatureFlags()
