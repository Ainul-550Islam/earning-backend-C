# api/cms/feature_flags.py
"""Feature flag management for CMS."""
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Feature Flags (Preserved) ───────────────────────────────────

# Built-in Feature Flag Names
FLAG_REFERRAL_PROGRAM     = 'referral_program'
FLAG_LEADERBOARD          = 'leaderboard'
FLAG_QUIZ_BUILDER         = 'quiz_builder'
FLAG_AI_QUIZ_GENERATOR    = 'ai_quiz_generator'
FLAG_VIDEO_CONTENT        = 'video_content'
FLAG_RTB_ADS              = 'rtb_ads'
FLAG_OFFERWALL            = 'offerwall'
FLAG_CONTENT_LOCKER       = 'content_locker'
FLAG_SMART_LINKS          = 'smart_links'
FLAG_WITHDRAWAL_USDT      = 'withdrawal_usdt'
FLAG_PUSH_NOTIFICATIONS   = 'push_notifications'
FLAG_WEBSOCKET            = 'websocket_realtime'
FLAG_CONTENT_BLOCKS       = 'content_blocks'
FLAG_FORM_BUILDER         = 'form_builder'
FLAG_APPROVAL_WORKFLOW    = 'approval_workflow'
FLAG_MAINTENANCE_MODE     = 'maintenance_mode'
FLAG_NEW_USER_BONUS       = 'new_user_welcome_bonus'
FLAG_STREAK_SYSTEM        = 'streak_system'
FLAG_EXPORT_DATA          = 'data_export'
FLAG_ANALYTICS_DASHBOARD  = 'analytics_dashboard'

# Default values for all flags
FLAG_DEFAULTS: Dict[str, bool] = {
    FLAG_REFERRAL_PROGRAM:    True,
    FLAG_LEADERBOARD:         True,
    FLAG_QUIZ_BUILDER:        True,
    FLAG_AI_QUIZ_GENERATOR:   False,
    FLAG_VIDEO_CONTENT:       False,
    FLAG_RTB_ADS:             False,
    FLAG_OFFERWALL:           True,
    FLAG_CONTENT_LOCKER:      True,
    FLAG_SMART_LINKS:         True,
    FLAG_WITHDRAWAL_USDT:     True,
    FLAG_PUSH_NOTIFICATIONS:  False,
    FLAG_WEBSOCKET:           False,
    FLAG_CONTENT_BLOCKS:      True,
    FLAG_FORM_BUILDER:        True,
    FLAG_APPROVAL_WORKFLOW:   True,
    FLAG_MAINTENANCE_MODE:    False,
    FLAG_NEW_USER_BONUS:      True,
    FLAG_STREAK_SYSTEM:       True,
    FLAG_EXPORT_DATA:         True,
    FLAG_ANALYTICS_DASHBOARD: True,
}


class FeatureFlags:
    """
    Feature flag system.
    Priority: User override > Site config DB > Default.
    """
    CACHE_TTL = 60  # 1 minute
    CACHE_PREFIX = 'cms:feature_flag'

    @classmethod
    def is_enabled(cls, flag_name: str, user=None) -> bool:
        """
        Check if a feature flag is enabled.
        Checks user-level override first, then site config, then default.
        """
        # 1. User-level override
        if user and user.is_authenticated:
            user_val = cls._get_user_flag(flag_name, user)
            if user_val is not None:
                return user_val

        # 2. Site config (cached)
        site_val = cls._get_site_flag(flag_name)
        if site_val is not None:
            return site_val

        # 3. Default
        return FLAG_DEFAULTS.get(flag_name, False)

    @classmethod
    def _get_site_flag(cls, flag_name: str) -> Optional[bool]:
        cache_key = f"{cls.CACHE_PREFIX}:site:{flag_name}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from api.cms.models_new.site_config import SiteConfig
            config = SiteConfig.get_active()
            if not config:
                return None
            # Map flag names to SiteConfig fields
            field_map = {
                FLAG_REFERRAL_PROGRAM: 'referral_enabled',
                FLAG_LEADERBOARD:      'leaderboard_enabled',
                FLAG_QUIZ_BUILDER:     'quiz_enabled',
                FLAG_OFFERWALL:        'offerwall_enabled',
                FLAG_MAINTENANCE_MODE: 'maintenance_mode',
            }
            field_name = field_map.get(flag_name)
            if field_name and hasattr(config, field_name):
                val = getattr(config, field_name)
                cache.set(cache_key, val, cls.CACHE_TTL)
                return val
        except Exception:
            pass
        return None

    @classmethod
    def _get_user_flag(cls, flag_name: str, user) -> Optional[bool]:
        """Check user-specific flag override (e.g. beta testers)."""
        try:
            # Check if user is in a group that overrides this flag
            if user.is_staff or user.is_superuser:
                return True  # Staff always has all features
            # Could extend to check UserFeatureFlag model
            return None
        except Exception:
            return None

    @classmethod
    def enable(cls, flag_name: str, scope: str = 'site') -> bool:
        """Enable a feature flag for the site."""
        return cls.set(flag_name, True, scope)

    @classmethod
    def disable(cls, flag_name: str, scope: str = 'site') -> bool:
        """Disable a feature flag for the site."""
        return cls.set(flag_name, False, scope)

    @classmethod
    def set(cls, flag_name: str, value: bool, scope: str = 'site') -> bool:
        """Set a feature flag value."""
        try:
            cache_key = f"{cls.CACHE_PREFIX}:site:{flag_name}"
            cache.set(cache_key, value, cls.CACHE_TTL)
            logger.info(f"[FeatureFlag] {flag_name} = {value} ({scope})")
            return True
        except Exception as e:
            logger.error(f"[FeatureFlag] set failed: {e}")
            return False

    @classmethod
    def get_all(cls, user=None) -> Dict[str, bool]:
        """Get all feature flags with their current values."""
        return {
            flag: cls.is_enabled(flag, user)
            for flag in FLAG_DEFAULTS.keys()
        }

    @classmethod
    def invalidate_cache(cls, flag_name: str = None):
        """Invalidate feature flag cache."""
        if flag_name:
            cache.delete(f"{cls.CACHE_PREFIX}:site:{flag_name}")
        else:
            for flag in FLAG_DEFAULTS:
                cache.delete(f"{cls.CACHE_PREFIX}:site:{flag}")

    @classmethod
    def require(cls, flag_name: str, user=None):
        """
        Decorator / context guard: raise FeatureDisabledError if flag is off.
        Usage: FeatureFlags.require('offerwall') in view or service.
        """
        if not cls.is_enabled(flag_name, user):
            from api.cms.exceptions import ServiceUnavailableError
            raise ServiceUnavailableError(
                detail=f"Feature '{flag_name}' is currently disabled.",
                code='feature_disabled',
            )


def feature_required(flag_name: str):
    """Decorator that checks feature flag before executing function."""
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get user from args (for view methods)
            user = None
            if args and hasattr(args[0], 'user'):
                user = args[0].user
            elif len(args) > 1 and hasattr(args[1], 'user'):
                user = args[1].user
            FeatureFlags.require(flag_name, user)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ── Enhanced Feature Flag Classes ─────────────────────────────────────

class BaseFeatureFlag(BaseService):
    """Base feature flag class with common functionality."""
    
    def __init__(self):
        """Initialize feature flag."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute feature flag."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def is_enabled(self, user_id: int = None, context: Dict[str, Any] = None) -> bool:
        """Check if feature is enabled."""
        return False


class BooleanFeatureFlag(BaseFeatureFlag):
    """Simple boolean feature flag."""
    
    def __init__(self, name: str, default_value: bool = False):
        super().__init__()
        self.name = name
        self.default_value = default_value
    
    def is_enabled(self, user_id: int = None, context: Dict[str, Any] = None) -> bool:
        """Check if boolean feature is enabled."""
        try:
            # Check cache first
            cache_key = f"feature_flag:{self.name}"
            cached_value = self.cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Get from original FeatureFlags class
            return FeatureFlags.is_enabled(self.name)
            
        except Exception as e:
            logger.error(f"Error checking feature flag {self.name}: {e}")
            return self.default_value


class PercentageFeatureFlag(BaseFeatureFlag):
    """Percentage-based feature flag."""
    
    def __init__(self, name: str, percentage: int = 0):
        super().__init__()
        self.name = name
        self.percentage = percentage
    
    def is_enabled(self, user_id: int = None, context: Dict[str, Any] = None) -> bool:
        """Check if percentage feature is enabled for user."""
        try:
            if not user_id:
                return False
            
            # Check cache first
            cache_key = f"feature_flag:{self.name}:user:{user_id}"
            cached_value = self.cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Get base flag status
            base_enabled = FeatureFlags.is_enabled(self.name)
            if not base_enabled:
                return False
            
            # Use consistent hashing for user
            import hashlib
            hash_input = f"{self.name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            enabled = (hash_value % 100) < self.percentage
            
            # Cache for 1 hour
            self.cache.set(cache_key, enabled, timeout=3600)
            
            return enabled
            
        except Exception as e:
            logger.error(f"Error checking percentage feature flag {self.name}: {e}")
            return False


# ── Enhanced Feature Flag Manager ─────────────────────────────────────

class EnhancedFeatureFlagManager:
    """Manager for enhanced feature flags."""
    
    def __init__(self):
        """Initialize feature flag manager."""
        self.flags = {}
        self.logger = logging.getLogger(f"{__name__}.manager")
        
        # Register enhanced flags
        self._register_enhanced_flags()
    
    def _register_enhanced_flags(self):
        """Register enhanced feature flags."""
        self.flags['new_dashboard_v2'] = BooleanFeatureFlag('new_dashboard_v2', False)
        self.flags['advanced_analytics'] = PercentageFeatureFlag('advanced_analytics', 20)
        self.flags['beta_features'] = PercentageFeatureFlag('beta_features', 10)
    
    def register_flag(self, name: str, flag: BaseFeatureFlag):
        """Register a new feature flag."""
        self.flags[name] = flag
        logger.info(f"Enhanced feature flag registered: {name}")
    
    def get_flag(self, name: str) -> Optional[BaseFeatureFlag]:
        """Get feature flag by name."""
        return self.flags.get(name)
    
    def is_enabled(self, name: str, user_id: int = None, context: Dict[str, Any] = None) -> bool:
        """Check if feature flag is enabled."""
        # Check enhanced flags first
        flag = self.get_flag(name)
        if flag:
            return flag.is_enabled(user_id, context)
        
        # Fall back to original FeatureFlags
        return FeatureFlags.is_enabled(name)
    
    def get_all_flags(self, user_id: int = None) -> Dict[str, Dict[str, Any]]:
        """Get all feature flags and their status."""
        result = {}
        
        # Get original flags
        original_flags = FeatureFlags.get_all()
        for name, value in original_flags.items():
            result[name] = {
                'name': name,
                'enabled': value,
                'type': 'original'
            }
        
        # Get enhanced flags
        for name, flag in self.flags.items():
            try:
                result[name] = {
                    'name': name,
                    'enabled': flag.is_enabled(user_id),
                    'type': flag.__class__.__name__
                }
            except Exception as e:
                logger.error(f"Error checking enhanced flag {name}: {e}")
                result[name] = {
                    'name': name,
                    'enabled': False,
                    'error': str(e),
                    'type': flag.__class__.__name__
                }
        
        return result


# Global enhanced feature flag manager
enhanced_feature_flag_manager = EnhancedFeatureFlagManager()
