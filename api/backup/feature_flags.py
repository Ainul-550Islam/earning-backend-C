"""
Backup Module Feature Flags
Lightweight feature flag system for toggling backup features at runtime.
"""

import logging
from typing import Any, Dict, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Default flag values — override via settings.BACKUP_FEATURE_FLAGS
_DEFAULTS: Dict[str, bool] = {
    "backup_encryption": True,
    "backup_compression": True,
    "gcs_storage": False,
    "azure_storage": False,
    "webhook_notifications": True,
    "push_notifications": False,
    "openai_analysis": False,
    "audit_logging": True,
    "delta_backups": True,
    "parallel_uploads": False,
    "backup_deduplication": False,
    "restore_dry_run": True,
}

CACHE_PREFIX = "backup_feature_flag:"
CACHE_TIMEOUT = 60  # seconds


def _get_settings_flags() -> Dict[str, bool]:
    return getattr(settings, "BACKUP_FEATURE_FLAGS", {})


def flag_is_active(flag_name: str, default: Optional[bool] = None) -> bool:
    """
    Check if a feature flag is active.
    Resolution order: cache → settings → _DEFAULTS → default argument.
    """
    cache_key = f"{CACHE_PREFIX}{flag_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    settings_flags = _get_settings_flags()
    if flag_name in settings_flags:
        value = bool(settings_flags[flag_name])
    elif flag_name in _DEFAULTS:
        value = _DEFAULTS[flag_name]
    elif default is not None:
        value = default
    else:
        logger.warning("Unknown feature flag: %s — defaulting to False", flag_name)
        value = False

    cache.set(cache_key, value, CACHE_TIMEOUT)
    return value


def set_flag(flag_name: str, active: bool) -> None:
    """Temporarily override a flag in cache (does not persist to settings)"""
    cache_key = f"{CACHE_PREFIX}{flag_name}"
    cache.set(cache_key, active, CACHE_TIMEOUT)
    logger.info("Feature flag '%s' set to %s", flag_name, active)


def clear_flag_cache(flag_name: Optional[str] = None) -> None:
    """Clear cached flag(s). If flag_name is None, clears all known flags."""
    if flag_name:
        cache.delete(f"{CACHE_PREFIX}{flag_name}")
    else:
        for name in _DEFAULTS:
            cache.delete(f"{CACHE_PREFIX}{name}")


def all_flags() -> Dict[str, bool]:
    """Return current state of all known feature flags"""
    return {name: flag_is_active(name) for name in _DEFAULTS}


def require_flag(flag_name: str):
    """
    Decorator — raises FeatureFlagDisabledError if flag is not active.

    Usage:
        @require_flag("gcs_storage")
        def upload_to_gcs(...): ...
    """
    def decorator(func):
        import functools
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not flag_is_active(flag_name):
                raise FeatureFlagDisabledError(
                    f"Feature '{flag_name}' is disabled. Enable it via BACKUP_FEATURE_FLAGS."
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


class FeatureFlagDisabledError(Exception):
    """Raised when a disabled feature is accessed"""
    pass
