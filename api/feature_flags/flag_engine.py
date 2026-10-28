"""
Flag Engine for Feature Flags & A/B Testing.

FIX: now delegates all cache key naming + invalidation to
`FlagCacheManager` (utils/cache_manager.py) instead of hand-building
`f"flag_enabled:{flag_name}"` strings inline, and `clear_all_cache()`
no longer calls the django-redis-only `cache.keys()` method (which
raised AttributeError on Django's default LocMemCache backend).
"""
from typing import Dict, Any, Optional, List

from .models.feature_flag import FeatureFlag
from .models.rollout_rule import RolloutRule
from .models.flag_variant import FlagVariant
from .exceptions import FlagNotFoundError
from .utils import FlagCacheManager


class FlagEngine:
    """
    Engine for evaluating feature flags.
    """

    def __init__(self):
        """Initialize the flag engine."""
        self.cache_timeout = 300  # 5 minutes

    def is_enabled(self, flag_name: str, context: Optional[Dict[str, Any]] = None,
                    environment: str = 'production') -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the feature flag
            context: Optional context dictionary
            environment: NEW — environment to evaluate against (multi-env support)

        Returns:
            True if flag is enabled
        """
        cached_value = FlagCacheManager.get_enabled(flag_name, environment)
        if cached_value is not None:
            return cached_value

        try:
            flag = FeatureFlag.objects.get(name=flag_name, environment=environment)
        except FeatureFlag.DoesNotExist:
            raise FlagNotFoundError(f"Feature flag '{flag_name}' not found in environment '{environment}'")

        if flag.status != FeatureFlag.Status.ACTIVE:
            FlagCacheManager.set_enabled(flag_name, False, environment, self.cache_timeout)
            return False

        if context and flag.targeting_rules:
            if self.evaluate_rules(flag, context):
                FlagCacheManager.set_enabled(flag_name, True, environment, self.cache_timeout)
                return True

        if flag.rollout_percentage > 0 and context:
            from .utils import get_user_hash
            user_hash = get_user_hash(context.get('user_id', ''))
            is_enabled = (user_hash % 100) < flag.rollout_percentage
            FlagCacheManager.set_enabled(flag_name, is_enabled, environment, self.cache_timeout)
            return is_enabled

        is_enabled = flag.rollout_percentage == 100
        FlagCacheManager.set_enabled(flag_name, is_enabled, environment, self.cache_timeout)
        return is_enabled

    def get_value(self, flag_name: str, context: Optional[Dict[str, Any]] = None,
                  default_value: Any = None, environment: str = 'production') -> Any:
        """
        Get the value of a feature flag.

        Args:
            flag_name: Name of the feature flag
            context: Optional context dictionary
            default_value: Default value if flag is disabled
            environment: NEW — environment to evaluate against

        Returns:
            Flag value
        """
        if not self.is_enabled(flag_name, context, environment):
            return default_value

        try:
            flag = FeatureFlag.objects.get(name=flag_name, environment=environment)
        except FeatureFlag.DoesNotExist:
            raise FlagNotFoundError(f"Feature flag '{flag_name}' not found in environment '{environment}'")

        variants = FlagVariant.objects.filter(flag=flag, is_active=True)

        if variants.exists():
            from .utils import get_user_hash
            context = context or {}
            user_hash = get_user_hash(context.get('user_id', ''))
            total_weight = sum(v.weight for v in variants)

            if total_weight > 0:
                threshold = (user_hash % 100) / 100 * total_weight
                current_weight = 0

                for variant in variants:
                    current_weight += variant.weight
                    if threshold <= current_weight:
                        return variant.value

        return flag.default_value if default_value is None else default_value

    def evaluate_rules(self, flag: FeatureFlag, context: Dict[str, Any]) -> bool:
        """
        Evaluate rollout rules for a flag.
        """
        rules = RolloutRule.objects.filter(flag=flag, is_active=True).order_by('-priority')

        for rule in rules:
            if rule.evaluate(context):
                return True

        return False

    def clear_flag_cache(self, flag_name: str, environment: str = 'production') -> None:
        """Clear cache for a specific flag."""
        FlagCacheManager.clear_flag_cache(flag_name, environment)

    def clear_all_cache(self) -> None:
        """
        Clear all flag cache.

        FIX: previously called `cache.delete_many(cache.keys("flag_enabled:*"))`
        — `cache.keys()` is a django-redis-only extension and raised
        AttributeError on Django's default LocMemCache/FileBasedCache
        backends. `FlagCacheManager.clear_all_cache()` uses a versioned-key
        strategy that works on every cache backend.
        """
        FlagCacheManager.clear_all_cache()

    def get_all_flags(self, environment: str = 'production') -> List[FeatureFlag]:
        """Get all flags for an environment."""
        return list(FeatureFlag.objects.filter(environment=environment))

    def get_active_flags(self, environment: str = 'production') -> List[FeatureFlag]:
        """Get all active flags for an environment."""
        return list(FeatureFlag.objects.filter(
            environment=environment,
            status=FeatureFlag.Status.ACTIVE
        ))
