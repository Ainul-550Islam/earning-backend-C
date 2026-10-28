# api/admin_panel/feature_flags.py
"""
Admin Panel Feature Flag Management System.
Extends FeatureFlagService with: targeting rules, rollout control,
A/B test integration, environment-specific flags, kill switches.

This module is the complete feature flag brain for admin_panel.
Other modules import is_enabled() — this module implements it all.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # seconds


# ===========================================================================
# FLAG TYPES & ROLLOUT STRATEGIES
# ===========================================================================

class FlagType(str, Enum):
    BOOLEAN      = 'boolean'        # Simple on/off
    PERCENTAGE   = 'percentage'     # % rollout
    USER_LIST    = 'user_list'      # Specific user IDs
    GEO          = 'geo'            # Country-based
    PLAN         = 'plan'           # User plan/tier
    AB_TEST      = 'ab_test'        # A/B experiment
    KILL_SWITCH  = 'kill_switch'    # Emergency off
    ENVIRONMENT  = 'environment'    # dev/staging/prod


class RolloutStrategy(str, Enum):
    ALL             = 'all'             # 100% of users
    PERCENTAGE      = 'percentage'      # X% of users (hash-based)
    USER_WHITELIST  = 'user_whitelist'  # Explicit user list
    STAFF_ONLY      = 'staff_only'      # Staff users only
    BETA_USERS      = 'beta_users'      # Users in beta group
    GEO_TARGETED    = 'geo_targeted'    # Specific countries
    GRADUAL         = 'gradual'         # Increasing % over time


# ===========================================================================
# FLAG DEFINITION
# ===========================================================================

@dataclass
class FlagDefinition:
    """Complete feature flag definition."""
    key:            str
    label:          str
    description:    str = ''
    flag_type:      FlagType = FlagType.BOOLEAN
    is_enabled:     bool = False
    rollout_pct:    int = 100             # 0-100%
    strategy:       RolloutStrategy = RolloutStrategy.ALL
    allowed_users:  List[int] = field(default_factory=list)
    blocked_users:  List[int] = field(default_factory=list)
    allowed_countries: List[str] = field(default_factory=list)
    allowed_plans:  List[str] = field(default_factory=list)
    environments:   List[str] = field(default_factory=list)  # dev, staging, prod
    metadata:       Dict = field(default_factory=dict)
    kill_switch:    bool = False
    expires_at:     Optional[str] = None

    def is_active_in_env(self, env: str) -> bool:
        if not self.environments:
            return True
        return env in self.environments

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        from django.utils.dateparse import parse_datetime
        exp = parse_datetime(self.expires_at)
        return exp and timezone.now() > exp


# ===========================================================================
# FEATURE FLAG ENGINE
# ===========================================================================

class FeatureFlagEngine:
    """
    Core evaluation engine for feature flags.
    Determines if a flag is enabled for a given user/context.
    """

    def is_enabled(
        self,
        flag_key: str,
        user=None,
        user_id: Any = None,
        country: str = '',
        plan: str = '',
        default: bool = False,
    ) -> bool:
        """
        Main evaluation method.
        Returns True if flag is enabled for the given context.
        """
        # Fast path: check cache
        flag = self._get_flag(flag_key)
        if flag is None:
            return default

        # Kill switch = always off regardless
        if flag.kill_switch or not flag.is_enabled:
            return False

        # Expired?
        if flag.is_expired():
            return False

        # No user context = check global rollout only
        if user is None and user_id is None:
            return flag.rollout_pct == 100

        uid = user_id or (user.pk if user else None)

        # Blocked user
        if uid and uid in (flag.blocked_users or []):
            return False

        # Whitelisted user
        if uid and uid in (flag.allowed_users or []):
            return True

        # Staff-only
        if flag.strategy == RolloutStrategy.STAFF_ONLY:
            return bool(user and user.is_staff)

        # Geo targeting
        if flag.strategy == RolloutStrategy.GEO_TARGETED and flag.allowed_countries:
            return country.upper() in flag.allowed_countries

        # Plan-based
        if flag.allowed_plans and plan:
            return plan in flag.allowed_plans

        # Percentage rollout (deterministic hash)
        if flag.rollout_pct < 100 and uid:
            return self._in_rollout(uid, flag_key, flag.rollout_pct)

        return flag.is_enabled and flag.rollout_pct == 100

    def _in_rollout(self, user_id: Any, flag_key: str, pct: int) -> bool:
        """Deterministic percentage check using user_id hash."""
        h = hashlib.md5(f"{flag_key}:{user_id}".encode()).hexdigest()
        bucket = int(h[:8], 16) % 100
        return bucket < pct

    def _get_flag(self, flag_key: str) -> Optional[FlagDefinition]:
        """Get flag definition from cache or DB."""
        cache_key = f'admin_panel:flag_def:{flag_key}'
        cached = cache.get(cache_key)
        if cached is not None:
            if isinstance(cached, dict):
                return FlagDefinition(**cached)
            return cached

        try:
            from api.admin_panel.models.config import FeatureFlag
            db_flag = FeatureFlag.objects.get(flag_key=flag_key)
            flag = FlagDefinition(
                key=db_flag.flag_key,
                label=getattr(db_flag, 'label', flag_key),
                is_enabled=db_flag.is_enabled,
                rollout_pct=db_flag.rollout_pct,
                allowed_users=getattr(db_flag, 'allowed_user_ids', []) or [],
                environments=getattr(db_flag, 'environments', []) or [],
                kill_switch=getattr(db_flag, 'kill_switch', False),
            )
            cache.set(cache_key, flag.__dict__, CACHE_TTL)
            return flag
        except Exception:
            cache.set(cache_key, False, CACHE_TTL)
            return None

    def enable(self, flag_key: str, rollout_pct: int = 100, actor=None) -> bool:
        """Enable a flag."""
        return self._update_flag(flag_key, is_enabled=True, rollout_pct=rollout_pct, actor=actor)

    def disable(self, flag_key: str, actor=None) -> bool:
        """Disable a flag."""
        return self._update_flag(flag_key, is_enabled=False, actor=actor)

    def kill(self, flag_key: str, actor=None) -> bool:
        """Emergency kill switch — sets kill_switch=True, bypasses all rules."""
        try:
            from api.admin_panel.models.config import FeatureFlag
            FeatureFlag.objects.filter(flag_key=flag_key).update(
                is_enabled=False, kill_switch=True,
            )
            self._clear_cache(flag_key)
            logger.critical(f"[FeatureFlag] KILL SWITCH ACTIVATED: {flag_key}")
            return True
        except Exception as e:
            logger.error(f"[FeatureFlag.kill] {e}")
            return False

    def set_rollout(self, flag_key: str, pct: int, actor=None) -> bool:
        """Set rollout percentage (0-100)."""
        return self._update_flag(flag_key, rollout_pct=max(0, min(100, pct)), actor=actor)

    def add_to_whitelist(self, flag_key: str, user_id: Any) -> bool:
        """Add user to flag whitelist."""
        try:
            from api.admin_panel.models.config import FeatureFlag
            flag = FeatureFlag.objects.get(flag_key=flag_key)
            current = flag.allowed_user_ids or []
            if user_id not in current:
                current.append(user_id)
                flag.allowed_user_ids = current
                flag.save()
                self._clear_cache(flag_key)
            return True
        except Exception:
            return False

    def remove_from_whitelist(self, flag_key: str, user_id: Any) -> bool:
        """Remove user from flag whitelist."""
        try:
            from api.admin_panel.models.config import FeatureFlag
            flag = FeatureFlag.objects.get(flag_key=flag_key)
            current = flag.allowed_user_ids or []
            if user_id in current:
                current.remove(user_id)
                flag.allowed_user_ids = current
                flag.save()
                self._clear_cache(flag_key)
            return True
        except Exception:
            return False

    def _update_flag(self, flag_key: str, actor=None, **kwargs) -> bool:
        try:
            from api.admin_panel.models.config import FeatureFlag
            FeatureFlag.objects.filter(flag_key=flag_key).update(**kwargs)
            self._clear_cache(flag_key)
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='update_feature_flag',
                                  model_name='FeatureFlag', changes={'flag': flag_key, **kwargs})
            return True
        except Exception as e:
            logger.error(f"[FeatureFlag._update] {e}")
            return False

    def _clear_cache(self, flag_key: str) -> None:
        cache.delete(f'admin_panel:flag_def:{flag_key}')
        cache.delete(f'admin_panel:feature_flag:{flag_key}')
        cache.delete('admin_panel:feature_flags_all')

    def get_all_flags(self) -> List[Dict]:
        """Get all flags with evaluation status."""
        cache_key = 'admin_panel:all_flags_detailed'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.admin_panel.models.config import FeatureFlag
            flags = list(FeatureFlag.objects.values(
                'flag_key', 'label', 'is_enabled', 'rollout_pct',
                'kill_switch', 'created_at', 'updated_at'
            ).order_by('flag_key'))
            cache.set(cache_key, flags, CACHE_TTL)
            return flags
        except Exception:
            return []

    def get_flag_usage_stats(self, flag_key: str, days: int = 7) -> Dict:
        """Track how many times a flag was evaluated (from cache counters)."""
        key = f'admin_panel:flag_eval:{flag_key}'
        total = cache.get(key, 0)
        enabled = cache.get(f'{key}:enabled', 0)
        return {
            'flag_key': flag_key,
            'total_evaluations': total,
            'enabled_count': enabled,
            'disabled_count': total - enabled,
            'enable_rate': round(enabled / max(total, 1) * 100, 2),
        }

    def evaluate_and_track(self, flag_key: str, user=None, **kwargs) -> bool:
        """Evaluate flag and track usage in cache counter."""
        result = self.is_enabled(flag_key, user=user, **kwargs)
        try:
            eval_key = f'admin_panel:flag_eval:{flag_key}'
            cache_increment = lambda k: cache.get_or_set(k, 0) or 0
            current = cache.get(eval_key, 0)
            cache.set(eval_key, current + 1, 86400)
            if result:
                en_key = f'{eval_key}:enabled'
                cache.set(en_key, cache.get(en_key, 0) + 1, 86400)
        except Exception:
            pass
        return result


# ===========================================================================
# PREDEFINED FLAG KEYS
# ===========================================================================

class Flags:
    """All feature flag keys used in admin_panel. Centralised registry."""

    # Core features
    DAILY_PAYOUT           = 'daily_payout'
    WELCOME_BONUS          = 'welcome_bonus'
    REFERRAL_SYSTEM        = 'referral_system'
    SPIN_WHEEL             = 'spin_wheel'
    DAILY_CHECKIN          = 'daily_checkin'

    # Content & offers
    CONTENT_LOCKER         = 'content_locker'
    OFFERWALL              = 'offerwall'
    RTB_MARKETPLACE        = 'rtb_marketplace'
    SMARTLINK_ENABLED      = 'smartlink_enabled'
    AI_OFFER_ROUTING       = 'ai_offer_routing'

    # AI features
    AI_FRAUD_DETECTION     = 'ai_fraud_detection'
    AI_CHURN_PREDICTION    = 'ai_churn_prediction'
    AI_RECOMMENDATIONS     = 'ai_recommendations'
    OPENAI_ADMIN           = 'openai_admin'

    # KYC & compliance
    KYC_REQUIRED           = 'kyc_required'
    KYC_AUTO_APPROVE       = 'kyc_auto_approve'
    SANCTIONS_SCREENING    = 'sanctions_screening'
    AML_MONITORING         = 'aml_monitoring'
    GDPR_ERASURE           = 'gdpr_erasure'

    # Payments
    BKASH_ENABLED          = 'bkash_enabled'
    NAGAD_ENABLED          = 'nagad_enabled'
    ROCKET_ENABLED         = 'rocket_enabled'
    CRYPTO_PAYOUT          = 'crypto_payout'
    INSTANT_PAYOUT         = 'instant_payout'
    AUTO_APPROVE_PAYOUT    = 'auto_approve_payout'

    # Admin features
    WEBSOCKET_DASHBOARD    = 'websocket_dashboard'
    REALTIME_FRAUD_ALERTS  = 'realtime_fraud_alerts'
    ADMIN_2FA              = 'admin_2fa'
    ADMIN_AI_ASSISTANT     = 'admin_ai_assistant'
    MAINTENANCE_BANNER     = 'maintenance_banner'

    # Beta features
    RTB_V2                 = 'rtb_v2_beta'
    NEW_DASHBOARD_UI       = 'new_dashboard_ui'
    PUSH_NOTIFICATIONS     = 'push_notifications'


# Global engine instance
flag_engine = FeatureFlagEngine()


# ===========================================================================
# CONVENIENCE FUNCTIONS
# ===========================================================================

def is_enabled(flag_key: str, user=None, user_id=None, **kwargs) -> bool:
    """Quick check if a flag is enabled."""
    return flag_engine.is_enabled(flag_key, user=user, user_id=user_id, **kwargs)


def enable_flag(flag_key: str, rollout_pct: int = 100, actor=None) -> bool:
    return flag_engine.enable(flag_key, rollout_pct=rollout_pct, actor=actor)


def disable_flag(flag_key: str, actor=None) -> bool:
    return flag_engine.disable(flag_key, actor=actor)


def kill_flag(flag_key: str, actor=None) -> bool:
    """Emergency kill switch."""
    return flag_engine.kill(flag_key, actor=actor)


def get_all_flags() -> List[Dict]:
    return flag_engine.get_all_flags()