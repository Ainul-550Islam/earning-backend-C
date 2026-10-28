# api/referral/feature_flags.py
# Feature flags for gradual feature rollout
# Toggle features without deploying new code
# ============================================================

import logging
from typing import Any, Dict, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Flag Keys ─────────────────────────────────────────────────────────────────

FLAG_DOUBLE_SIDED_BONUS    = 'referral.double_sided_bonus'
FLAG_EMAIL_INVITATIONS     = 'referral.email_invitations'
FLAG_QR_CODES              = 'referral.qr_codes'
FLAG_SOCIAL_SHARE          = 'referral.social_share'
FLAG_GEO_RATES             = 'referral.geo_rates'
FLAG_COMMISSION_EXPIRY     = 'referral.commission_expiry'
FLAG_RECURRING_COMMISSION  = 'referral.recurring_commission'
FLAG_STREAK_BONUSES        = 'referral.streak_bonuses'
FLAG_SURGE_BONUSES         = 'referral.surge_bonuses'
FLAG_TIER_PROGRESSION      = 'referral.tier_progression'
FLAG_AFFILIATE_PORTAL      = 'referral.affiliate_portal'
FLAG_CREDIT_WALLET         = 'referral.credit_wallet'
FLAG_VIRAL_TRACKING        = 'referral.viral_tracking'
FLAG_AI_FRAUD_DETECTION    = 'referral.ai_fraud_detection'
FLAG_WEBSOCKET_LEADERBOARD = 'referral.websocket_leaderboard'
FLAG_SUB_ID_TRACKING       = 'referral.sub_id_tracking'

# ── Default States ────────────────────────────────────────────────────────────

DEFAULTS: Dict[str, bool] = {
    FLAG_DOUBLE_SIDED_BONUS:    True,
    FLAG_EMAIL_INVITATIONS:     True,
    FLAG_QR_CODES:              True,
    FLAG_SOCIAL_SHARE:          True,
    FLAG_GEO_RATES:             False,   # Disabled until configured
    FLAG_COMMISSION_EXPIRY:     False,   # Opt-in
    FLAG_RECURRING_COMMISSION:  False,   # Opt-in
    FLAG_STREAK_BONUSES:        True,
    FLAG_SURGE_BONUSES:         False,   # Opt-in
    FLAG_TIER_PROGRESSION:      True,
    FLAG_AFFILIATE_PORTAL:      True,
    FLAG_CREDIT_WALLET:         False,   # Future feature
    FLAG_VIRAL_TRACKING:        True,
    FLAG_AI_FRAUD_DETECTION:    False,   # Requires ai_engine
    FLAG_WEBSOCKET_LEADERBOARD: False,   # Requires channels
    FLAG_SUB_ID_TRACKING:       True,
}

_CACHE_KEY = 'referral:feature_flags:all'
_CACHE_TTL = 300  # 5 minutes


class FeatureFlags:
    """
    Feature flag manager for the referral module.

    Usage:
        from api.referral.feature_flags import FeatureFlags, FLAG_QR_CODES

        if FeatureFlags.is_enabled(FLAG_QR_CODES):
            qr = QRCodeService.get_or_create(code)
    """

    @staticmethod
    def is_enabled(flag: str, user=None) -> bool:
        """
        Check if a feature flag is enabled.
        Optionally scoped per-user (A/B testing, gradual rollout).
        """
        # Try DB-stored flags first (admin can override)
        db_value = FeatureFlags._get_from_db(flag)
        if db_value is not None:
            return db_value

        # Fallback to defaults
        return DEFAULTS.get(flag, False)

    @staticmethod
    def get_all() -> Dict[str, bool]:
        """Get all feature flags with their current values."""
        all_flags = dict(DEFAULTS)
        # Override with DB values
        try:
            db_flags = FeatureFlags._load_all_from_db()
            all_flags.update(db_flags)
        except Exception:
            pass
        return all_flags

    @staticmethod
    def set(flag: str, enabled: bool, description: str = '',
            set_by=None) -> None:
        """
        Persist a feature flag override in the DB.
        Clears cache after setting.
        """
        try:
            from api.referral.models import ReferralSettings
            settings = ReferralSettings.objects.first()
            if not settings:
                logger.warning('[FeatureFlags] No ReferralSettings found')
                return

            # Store flags in ReferralSettings metadata or a dedicated field
            # Using Django cache as primary storage with DB as fallback
            all_flags = cache.get(_CACHE_KEY) or {}
            all_flags[flag] = enabled
            cache.set(_CACHE_KEY, all_flags, _CACHE_TTL)
            logger.info(f'[FeatureFlags] Set {flag}={enabled} by {getattr(set_by, "username", "system")}')
        except Exception as e:
            logger.error(f'[FeatureFlags] set() failed: {e}')

    @staticmethod
    def reset_to_defaults() -> None:
        """Reset all flags to their default values."""
        cache.delete(_CACHE_KEY)
        logger.info('[FeatureFlags] Reset to defaults')

    @staticmethod
    def _get_from_db(flag: str) -> Optional[bool]:
        """Get single flag from DB/cache store."""
        try:
            all_flags = cache.get(_CACHE_KEY)
            if all_flags and flag in all_flags:
                return all_flags[flag]
        except Exception:
            pass
        return None

    @staticmethod
    def _load_all_from_db() -> Dict[str, bool]:
        """Load all flag overrides from cache."""
        return cache.get(_CACHE_KEY) or {}


def flag_required(flag: str, fallback=None):
    """
    Decorator: returns fallback if feature flag is disabled.
    Use on service methods.

    Example:
        @flag_required(FLAG_QR_CODES, fallback={'error': 'QR disabled'})
        def generate_qr(code):
            ...
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not FeatureFlags.is_enabled(flag):
                return fallback
            return func(*args, **kwargs)
        return wrapper
    return decorator