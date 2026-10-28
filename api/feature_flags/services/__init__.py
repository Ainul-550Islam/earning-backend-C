"""
Services for Feature Flags & A/B Testing.

FIX (DRY): `FlagEngineService` has been removed — it was a 100%
redundant wrapper that duplicated `FlagEngine.is_enabled()` /
`.get_value()` under different method names, and carried its own copy
of the `cache.keys()` bug fixed in `flag_engine.py`. Use `FlagEngine`
directly (or `FeatureFlagService`, which already wraps it) instead.
"""
from .feature_flag_service import FeatureFlagService
from .experiment_service import ExperimentService
from .rollout_service import RolloutService
from .analytics_service import AnalyticsService
from .variant_assignment_service import VariantAssignmentService
from .performance_service import PerformanceService  # NEW

__all__ = [
    'FeatureFlagService',
    'ExperimentService',
    'RolloutService',
    'AnalyticsService',
    'VariantAssignmentService',
    'PerformanceService',
]
