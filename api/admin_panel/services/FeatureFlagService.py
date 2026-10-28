# api/admin_panel/services/FeatureFlagService.py
"""Service for evaluating feature flags with rollout and A/B support."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class FeatureFlagService:

    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def is_enabled(cls, flag_key: str, user=None) -> bool:
        """
        Check if a feature flag is active.
        If user is provided, applies rollout percentage logic.
        If user is None, returns global is_enabled state.
        """
        try:
            from ..models.config import FeatureFlag
            # Use per-user check if user provided
            if user is not None:
                cache_key = f'admin_panel:feature_flag_user:{flag_key}:{user.pk}'
                cached = cache.get(cache_key)
                if cached is not None:
                    return cached
                try:
                    flag = FeatureFlag.objects.get(flag_key=flag_key)
                    result = flag.is_active_for_user(user)
                    cache.set(cache_key, result, cls.CACHE_TTL)
                    return result
                except FeatureFlag.DoesNotExist:
                    return False
            else:
                return FeatureFlag.is_enabled_globally(flag_key)
        except Exception as e:
            logger.debug(f"FeatureFlagService.is_enabled error for '{flag_key}': {e}")
            return False

    @classmethod
    def get_all_flags(cls) -> dict:
        """Return dict of {flag_key: is_enabled} for all flags."""
        cached = cache.get('admin_panel:feature_flags')
        if cached:
            return cached
        try:
            from ..models.config import FeatureFlag
            flags = {f.flag_key: f.is_enabled for f in FeatureFlag.objects.all()}
            cache.set('admin_panel:feature_flags', flags, cls.CACHE_TTL)
            return flags
        except Exception:
            return {}

    @classmethod
    def enable(cls, flag_key: str, user=None) -> bool:
        """Enable a feature flag."""
        try:
            from ..models.config import FeatureFlag
            flag, created = FeatureFlag.objects.get_or_create(
                flag_key=flag_key,
                defaults={'is_enabled': True, 'updated_by': user}
            )
            if not created:
                flag.is_enabled = True
                flag.updated_by = user
                flag.save(update_fields=['is_enabled', 'updated_by', 'updated_at'])
            return True
        except Exception as e:
            logger.error(f"FeatureFlagService.enable error: {e}")
            return False

    @classmethod
    def disable(cls, flag_key: str, user=None) -> bool:
        """Disable a feature flag."""
        try:
            from ..models.config import FeatureFlag
            FeatureFlag.objects.filter(flag_key=flag_key).update(
                is_enabled=False, updated_by=user
            )
            cache.delete(f'admin_panel:feature_flag:{flag_key}')
            cache.delete('admin_panel:feature_flags')
            return True
        except Exception as e:
            logger.error(f"FeatureFlagService.disable error: {e}")
            return False

    @classmethod
    def set_rollout(cls, flag_key: str, percentage: int, user=None) -> bool:
        """Set rollout percentage for a flag (0-100)."""
        if not (0 <= percentage <= 100):
            raise ValueError(f"rollout_pct must be 0-100, got {percentage}")
        try:
            from ..models.config import FeatureFlag
            FeatureFlag.objects.filter(flag_key=flag_key).update(
                rollout_pct=percentage, updated_by=user
            )
            cache.delete(f'admin_panel:feature_flag:{flag_key}')
            return True
        except Exception as e:
            logger.error(f"FeatureFlagService.set_rollout error: {e}")
            return False