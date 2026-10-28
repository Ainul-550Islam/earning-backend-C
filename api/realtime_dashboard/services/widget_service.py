"""
Widget service for Real-time Dashboard Backend.

DRY FIX: Previously duplicated _get_cached / _set_cached / _invalidate
from RealTimeMetricService (~25 lines of identical pattern). Now
inherits them from BaseCachedService — the only difference is which
app_settings keys are used for prefix and timeout.

DRY FIX (v1.5.0 — 360-degree audit): create_widget/update_widget/
delete_widget claimed "WIRED" below but were never actually called —
DashboardWidgetViewSet.perform_create/update/destroy called
serializer.save() directly and only reached into this service for the
low-level _set_cached()/_invalidate() primitives (verified empirically
by tracing every call site). create_widget()'s old manual
`.objects.create(name=data['name'], widget_type=data['widget_type'], ...)`
mapping is also the same pattern that, on the metric/dashboard services,
concealed a real bug once traced (see real_time_metric_service.py and
dashboard_service.py) — this model has no FK fields so it wasn't
miswired here, but it was still needless re-derivation of what the
serializer's validated_data already provides. Rewritten to take
validated_data / an already-fetched instance directly.
"""
import logging
from typing import Optional, Dict, Any

from ..models.dashboard_widget import DashboardWidget
from .base_service import BaseCachedService

logger = logging.getLogger(__name__)


class WidgetService(BaseCachedService):
    """
    Service for DashboardWidget CRUD with read-through caching.

    Cache key format: f"{WIDGET_CACHE_PREFIX}{widget_id}"
    Cache is primed on create and each successful get, invalidated on
    update and delete.
    """

    cache_prefix_setting = 'WIDGET_CACHE_PREFIX'
    cache_timeout_setting = 'WIDGET_CACHE_TIMEOUT'
    model_class = DashboardWidget

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_widget(self, validated_data: Dict[str, Any]) -> DashboardWidget:
        """
        Create a new DashboardWidget from DRF-validated data and prime
        its cache entry.

        WIRED (v1.5.0): DashboardWidgetViewSet.perform_create() delegates
        here.
        """
        widget = DashboardWidget.objects.create(**validated_data)
        self._set_cached(widget)
        return widget

    def get_widget(self, widget_id: int) -> Optional[DashboardWidget]:
        """
        Fetch a widget by ID with read-through cache.

        Cache hit  → return cached instance (no DB query).
        Cache miss → query DB, prime cache, return instance.
        Not found  → return None (no cache write).

        NOTE: like RealTimeMetricService.get_metric(), not currently
        called outside this service/its tests — DRF's default retrieve()
        correctly uses the viewset queryset directly. Left available for
        a future non-HTTP caller; see that method's docstring for the
        full rationale.
        """
        cached = self._get_cached(widget_id)
        if cached is not None:
            return cached
        try:
            widget = DashboardWidget.objects.get(id=widget_id)
            self._set_cached(widget)
            return widget
        except DashboardWidget.DoesNotExist:
            return None

    def update_widget(self, instance: DashboardWidget, validated_data: Dict[str, Any]) -> DashboardWidget:
        """
        Apply a partial or full update to an already-fetched widget
        instance and refresh its cache entry.

        WIRED (v1.5.0): DashboardWidgetViewSet.perform_update() delegates
        here, passing serializer.instance and serializer.validated_data —
        no redundant re-fetch by ID. Invalidates the old cache entry
        before writing the new one so stale reads are impossible even if
        cache.set() fails.
        """
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        self._invalidate(instance.pk)
        self._set_cached(instance)
        return instance

    def delete_widget(self, instance: DashboardWidget) -> None:
        """
        Invalidate cache and delete an already-fetched widget instance.

        WIRED (v1.5.0): DashboardWidgetViewSet.perform_destroy() delegates
        here, passing the instance DRF's get_object() already resolved.
        """
        self._invalidate(instance.pk)
        instance.delete()

    def get_widgets_by_type(self, widget_type: str) -> list:
        """
        Return all widgets of a given type via the custom manager.

        WIRED: DashboardWidgetViewSet.by_type() action delegates here.
        """
        return list(DashboardWidget.objects.by_type(widget_type))
