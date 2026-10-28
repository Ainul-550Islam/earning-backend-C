"""
Real-time Metric service for Real-time Dashboard Backend.

DRY FIX: Previously duplicated _get_cached / _set_cached / _invalidate
pattern from WidgetService. Now inherits from BaseCachedService.
Removed the module-level _metric_cache_key() function — the base class
_cache_key() method replaces it.

DRY FIX (v1.5.0 — 360-degree audit): create_metric/update_metric/
delete_metric previously claimed "WIRED" in their docstrings but were
never actually called — RealTimeMetricViewSet.perform_create/update/
destroy reimplemented the same logic inline instead (verified empirically
by tracing every call site, not by trusting the comments). Worse,
create_metric()'s manual `RealTimeMetric.objects.create(name=data['name'],
...)` field-by-field mapping bypassed the DRF serializer entirely, so if
it HAD been called directly it would have skipped every validator in
validators.py. These three methods are now genuinely single-owner: they
accept the serializer's already-validated_data/instance and are the only
place that performs the write + cache side-effect. update_metric_value()
was a strict subset of update_metric() (same previous_value logic, fewer
fields) and has been removed rather than left as a second unused path.

WIRED (v1.5.0): RealTimeMetricViewSet.perform_create/perform_update/
perform_destroy now genuinely call create_metric/update_metric/
delete_metric below — confirmed by test_dry_unification.py, which spies
on the service methods to prove the viewset does not bypass them.
"""
import logging
from typing import Optional, Dict, Any

from ..models.real_time_metric import RealTimeMetric
from ..exceptions import MetricNotFoundError
from ..utils import check_metric_thresholds
from .base_service import BaseCachedService

logger = logging.getLogger(__name__)


class RealTimeMetricService(BaseCachedService):
    """
    Service for RealTimeMetric CRUD with read-through caching and
    business logic (previous_value tracking, threshold checks, broadcasts).

    Cache key format: f"{METRIC_CACHE_PREFIX}{metric_id}"
    """

    cache_prefix_setting = 'METRIC_CACHE_PREFIX'
    cache_timeout_setting = 'METRIC_CACHE_TIMEOUT'
    model_class = RealTimeMetric

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_metric(self, validated_data: Dict[str, Any]) -> RealTimeMetric:
        """
        Create a new metric from DRF-validated data and prime its cache entry.

        WIRED (v1.5.0): RealTimeMetricViewSet.perform_create() delegates
        here. Takes `serializer.validated_data` directly — every key
        already matches a model field name 1:1 (no FK fields on this
        model, so there is no instance-vs-id remapping to get wrong).
        Fields the client omitted are simply absent from validated_data,
        so the model's own `default=...` applies exactly as it would
        under plain `serializer.save()`.
        """
        metric = RealTimeMetric.objects.create(**validated_data)
        self._set_cached(metric)
        return metric

    def get_metric(self, metric_id: int) -> Optional[RealTimeMetric]:
        """
        Fetch a metric by ID with read-through cache.

        Returns None when not found. Use get_metric_or_raise() when
        absence is an error.

        NOTE: not currently called outside this service/its tests.
        DRF's default retrieve() correctly uses the ModelViewSet queryset
        directly (one query, no cache indirection needed there) — this
        method is kept as the documented cache-aware accessor for any
        future non-HTTP caller (Celery task, management command) that
        needs a single metric without paying for a full queryset. See
        the audit notes in CHANGELOG.md for why this was left available
        rather than force-wired into an unrelated call site.
        """
        cached = self._get_cached(metric_id)
        if cached is not None:
            return cached
        try:
            metric = RealTimeMetric.objects.get(id=metric_id)
            self._set_cached(metric)
            return metric
        except RealTimeMetric.DoesNotExist:
            return None

    def get_metric_or_raise(self, metric_id: int) -> RealTimeMetric:
        """
        Fetch a metric by ID, raising MetricNotFoundError when absent.

        Use in viewset actions where a missing metric is an error
        condition (returns 404 via the custom exception handler).
        See get_metric()'s note above — available for future callers.
        """
        metric = self.get_metric(metric_id)
        if metric is None:
            raise MetricNotFoundError(f'Metric {metric_id} not found')
        return metric

    def update_metric(self, instance: RealTimeMetric, validated_data: Dict[str, Any]) -> RealTimeMetric:
        """
        Apply a partial or full update to an already-fetched metric instance.

        If 'value' is in validated_data and differs from the current value,
        previous_value is captured automatically before the new value is
        applied — this is the single implementation of that rule.

        WIRED (v1.5.0): RealTimeMetricViewSet.perform_update() delegates
        here, passing serializer.instance (already fetched by DRF's
        get_object()) and serializer.validated_data — no redundant
        re-fetch by ID.
        """
        new_value = validated_data.get('value')
        if new_value is not None and new_value != instance.value:
            validated_data = {**validated_data, 'previous_value': instance.value}
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        self._invalidate(instance.pk)
        self._set_cached(instance)
        return instance

    def delete_metric(self, instance: RealTimeMetric) -> None:
        """
        Invalidate cache and delete an already-fetched metric instance.

        WIRED (v1.5.0): RealTimeMetricViewSet.perform_destroy() delegates
        here, passing the instance DRF's get_object() already resolved
        (and already 404'd on if missing) — so there is nothing left for
        this method to raise MetricNotFoundError about, unlike the old
        signature that re-fetched by ID.
        """
        self._invalidate(instance.pk)
        instance.delete()

    # ── Domain logic ──────────────────────────────────────────────────────────

    def check_thresholds(self, metric: RealTimeMetric) -> str:
        """
        Return threshold severity: 'critical', 'warning', or 'normal'.
        Delegates to utils.check_metric_thresholds — single implementation.

        NOTE: RealTimeMetricSerializer.get_threshold_status() calls
        utils.check_metric_thresholds() directly for the API-facing
        `threshold_status` field (it doesn't need a service instance for
        that). This method is the equivalent entry point for internal/
        non-HTTP callers that already hold a service instance.
        """
        return check_metric_thresholds(
            value=metric.value,
            warning=metric.warning_threshold,
            critical=metric.critical_threshold,
        )

    def get_metrics_by_type(self, metric_type: str) -> list:
        """
        Return all metrics of a given type.

        WIRED: RealTimeMetricViewSet.by_type() action delegates here.
        """
        return list(RealTimeMetric.objects.by_type(metric_type))

    def get_metrics_for_widget(self, widget_id: int) -> list:
        """
        Return all active metrics associated with a widget.

        WIRED: DashboardWidgetViewSet.metrics() action delegates here.
        Metrics declare their widget via metadata['widget_id'].
        """
        return list(
            RealTimeMetric.objects.filter(
                status='active',
                metadata__widget_id=widget_id,
            )
        )
