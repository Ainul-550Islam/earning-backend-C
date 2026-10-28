"""
Base service classes for Real-time Dashboard Backend.

DRY FIX: WidgetService and RealTimeMetricService both had identical
_get_cached() / _set_cached() / _invalidate() methods differing only in
the cache key prefix and timeout setting name. That is a copy-paste
violation across two files (~25 lines each).

BaseCachedService encodes the pattern once. Subclasses declare:
    cache_prefix_setting  — e.g. 'WIDGET_CACHE_PREFIX'
    cache_timeout_setting — e.g. 'WIDGET_CACHE_TIMEOUT'
    model_class           — the Django Model class (for type hints only)

and inherit _get_cached / _set_cached / _invalidate for free.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Type

from django.core.cache import cache
from django.db import models

from ..app_settings import app_settings

logger = logging.getLogger(__name__)


class BaseCachedService:
    """
    Abstract base for services that cache individual model instances
    by primary key.

    Subclass contract:
        cache_prefix_setting  (str) — app_settings attribute name for
                                       the key prefix, e.g. 'WIDGET_CACHE_PREFIX'
        cache_timeout_setting (str) — app_settings attribute name for
                                       the TTL, e.g. 'WIDGET_CACHE_TIMEOUT'
        model_class           (Type[models.Model]) — model being cached
                                       (used in log messages only)

    Usage example:

        class WidgetService(BaseCachedService):
            cache_prefix_setting  = 'WIDGET_CACHE_PREFIX'
            cache_timeout_setting = 'WIDGET_CACHE_TIMEOUT'
            model_class = DashboardWidget
    """

    cache_prefix_setting: str = ''
    cache_timeout_setting: str = ''
    model_class: Optional[Type[models.Model]] = None

    def _cache_key(self, pk: int) -> str:
        """Build the cache key for a given primary key."""
        prefix = getattr(app_settings, self.cache_prefix_setting, '')
        return f"{prefix}{pk}"

    def _get_cached(self, pk: int) -> Optional[Any]:
        """
        Return a cached model instance or None.

        Returns None immediately when ENABLE_CACHING is False so that
        callers always hit the DB and tests are deterministic by default.
        """
        if not app_settings.ENABLE_CACHING:
            return None
        return cache.get(self._cache_key(pk))

    def _set_cached(self, instance: models.Model) -> None:
        """Store a model instance in cache under its pk."""
        if not app_settings.ENABLE_CACHING:
            return
        timeout = getattr(app_settings, self.cache_timeout_setting, 300)
        cache.set(self._cache_key(instance.pk), instance, timeout=timeout)

    def _invalidate(self, pk: int) -> None:
        """Remove a model instance from cache."""
        cache.delete(self._cache_key(pk))
        logger.debug(
            'Cache invalidated',
            extra={'model': getattr(self.model_class, '__name__', '?'), 'pk': pk},
        )
