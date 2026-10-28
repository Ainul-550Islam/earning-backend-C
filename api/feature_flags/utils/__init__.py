"""
Utility package for Feature Flags & A/B Testing.

NEW (DRY fix): consolidates logic that was previously duplicated across
decorators.py, middleware.py, services/*.py, signals.py and viewsets/*.py
into single, reusable, well-tested classes:

  - ContextExtractor : the ONE place request -> context dict happens
  - FlagValidator     : the ONE place flag/variant field validation happens
  - FlagCacheManager  : the ONE place cache key naming + invalidation happens

This used to be a single root-level `utils.py`. It's now a package so the
new classes above can live in their own modules. Every function that used
to be importable from `feature_flags.utils` (get_user_hash,
validate_flag_name, calculate_sample_size, etc.) is re-exported below from
`helpers.py` so NO existing call site anywhere else in the codebase needed
to change.
"""
from .context_extractor import ContextExtractor
from .validators import FlagValidator
from .cache_manager import FlagCacheManager, FLAG_CACHE_PREFIX, DEFAULT_TIMEOUT
from .helpers import (
    get_user_hash,
    update_flag_analytics,
    normalize_context,
    validate_flag_name,
    validate_rollout_percentage,
    calculate_sample_size,
    calculate_statistical_significance,
    format_flag_value,
    get_flag_context_from_request,
)

__all__ = [
    'ContextExtractor',
    'FlagValidator',
    'FlagCacheManager',
    'FLAG_CACHE_PREFIX',
    'DEFAULT_TIMEOUT',
    'get_user_hash',
    'update_flag_analytics',
    'normalize_context',
    'validate_flag_name',
    'validate_rollout_percentage',
    'calculate_sample_size',
    'calculate_statistical_significance',
    'format_flag_value',
    'get_flag_context_from_request',
]
