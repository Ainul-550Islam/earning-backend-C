"""
Verification tests for all source-level bug fixes.

This file exists to provide explicit, named coverage for every bug that was
identified during the 360-degree audit and subsequently fixed. Each test
references the fix it verifies so future engineers know exactly WHY the test
exists and which regression it guards against.

Fix reference index
-------------------
FIX-ENGINE-1  : dashboard_engine_service.py — get_dashboard_widget_ids()
                called .values_list() on a JSONField (not a QuerySet).
                Fixed to use list(dashboard.widgets).

FIX-METRIC-1  : real_time_metric_service.py — MetricNotFoundError was
                defined in exceptions.py but never raised anywhere.
                Fixed via new get_metric_or_raise() method.

FIX-ENGINE-2  : Verify render_dashboard() end-to-end still works after
                the JSONField fix (regression guard).

FIX-THRESHOLD : Verify check_thresholds() delegates to utils rather than
                duplicating logic (DRY compliance).

FIX-DELETE-1  : real_time_metric_service.py — delete_metric() now raises
                MetricNotFoundError instead of silently doing nothing.
"""
import pytest
from api.realtime_dashboard.exceptions import (
    DashboardEngineError,
    MetricNotFoundError,
)
from api.realtime_dashboard.services.dashboard_engine_service import DashboardEngineService
from api.realtime_dashboard.services.real_time_metric_service import RealTimeMetricService
from .fixtures import (
    create_dashboard_widget,
    create_real_time_metric,
    create_user_dashboard,
)


# ─── FIX-ENGINE-1: get_dashboard_widget_ids JSONField fix ────────────────────

@pytest.mark.django_db
class TestGetDashboardWidgetIds:
    """
    guard against regression of the .values_list() on JSONField crash.

    ORIGINAL BUG:
        def get_dashboard_widget_ids(self, dashboard_id):
            dashboard = UserDashboard.objects.get(id=dashboard_id)
            return list(dashboard.widgets.values_list('id', flat=True))
                        ─────────────── AttributeError here ──────────────
        `widgets` is JSONField(default=list). It stores [1, 2, 3] as a plain
        Python list. Python lists have no .values_list() method.

    FIX:
        return list(dashboard.widgets)   # direct iteration over JSON list
    """

    @pytest.fixture
    def service(self):
        return DashboardEngineService()

    def test_returns_list_of_widget_ids(self, service):
        """FIX-ENGINE-1: must return a plain list of ints, not raise AttributeError."""
        w1 = create_dashboard_widget(name='W1')
        w2 = create_dashboard_widget(name='W2')
        dashboard = create_user_dashboard(widgets=[w1.pk, w2.pk])

        # Before the fix this raised:
        # AttributeError: 'list' object has no attribute 'values_list'
        result = service.get_dashboard_widget_ids(dashboard.pk)

        assert isinstance(result, list)
        assert set(result) == {w1.pk, w2.pk}

    def test_empty_widget_list_returns_empty_list(self, service):
        """FIX-ENGINE-1: empty JSONField list → empty return list (not error)."""
        dashboard = create_user_dashboard(widgets=[])
        result = service.get_dashboard_widget_ids(dashboard.pk)
        assert result == []

    def test_single_widget(self, service):
        """FIX-ENGINE-1: single-element JSON list returns single-element list."""
        widget = create_dashboard_widget(name='Solo')
        dashboard = create_user_dashboard(widgets=[widget.pk])
        result = service.get_dashboard_widget_ids(dashboard.pk)
        assert result == [widget.pk]

    def test_missing_dashboard_raises_engine_error(self, service):
        """FIX-ENGINE-1: missing dashboard_id raises DashboardEngineError (not DoesNotExist)."""
        with pytest.raises(DashboardEngineError, match='not found'):
            service.get_dashboard_widget_ids(999999)

    def test_result_is_list_not_queryset(self, service):
        """
        FIX-ENGINE-1: ensure the return type is a plain list (JSON-serialisable),
        not a Django QuerySet, ValuesQuerySet, or other lazy object.
        This matters for Celery tasks that serialise the result to JSON.
        """
        w = create_dashboard_widget(name='TypeCheck')
        dashboard = create_user_dashboard(widgets=[w.pk])
        result = service.get_dashboard_widget_ids(dashboard.pk)
        # If this were a QuerySet, list() would have been called on a QS —
        # the isinstance check catches cases where someone passes through
        # dashboard.widgets directly (which would be a list already but
        # could theoretically be a different type in future model changes).
        assert type(result) is list

    def test_ids_are_integers(self, service):
        """FIX-ENGINE-1: PKs stored in JSONField are ints, not strings."""
        widget = create_dashboard_widget(name='IntCheck')
        dashboard = create_user_dashboard(widgets=[widget.pk])
        result = service.get_dashboard_widget_ids(dashboard.pk)
        assert all(isinstance(pk, int) for pk in result), (
            f"Expected list of int PKs, got: {result!r}"
        )


# ─── FIX-ENGINE-2: render_dashboard end-to-end regression guard ─────────────

@pytest.mark.django_db
class TestRenderDashboardRegression:
    """
    End-to-end regression guard for render_dashboard() after the JSONField fix.
    If get_dashboard_widget_ids() is broken, render_dashboard() fails too —
    these tests catch both at the integration level.
    """

    @pytest.fixture
    def service(self):
        return DashboardEngineService()

    def test_render_with_multiple_widgets(self, service):
        """Dashboard with 2 widgets renders both correctly."""
        w1 = create_dashboard_widget(name='Revenue')
        w2 = create_dashboard_widget(name='Users')
        dashboard = create_user_dashboard(name='Main', widgets=[w1.pk, w2.pk])

        result = service.render_dashboard(dashboard.pk)

        assert result['id'] == dashboard.pk
        assert result['name'] == 'Main'
        assert len(result['widgets']) == 2
        widget_names = {w['name'] for w in result['widgets']}
        assert widget_names == {'Revenue', 'Users'}

    def test_render_empty_dashboard(self, service):
        """Dashboard with no widgets returns empty widget list (not error)."""
        dashboard = create_user_dashboard(name='Empty', widgets=[])
        result = service.render_dashboard(dashboard.pk)
        assert result['widgets'] == []

    def test_render_missing_dashboard_raises(self, service):
        """Missing dashboard_id raises DashboardEngineError."""
        with pytest.raises(DashboardEngineError):
            service.render_dashboard(999999)

    def test_render_references_deleted_widget_raises(self, service):
        """If a widget referenced in JSON list was deleted, raise DashboardEngineError."""
        dashboard = create_user_dashboard(widgets=[888888])  # non-existent widget
        with pytest.raises(DashboardEngineError):
            service.render_dashboard(dashboard.pk)


# ─── FIX-METRIC-1: MetricNotFoundError wiring ────────────────────────────────

@pytest.mark.django_db
class TestGetMetricOrRaise:
    """
    MetricNotFoundError was defined in exceptions.py but never raised
    anywhere in the codebase. Fixed by adding get_metric_or_raise()
    to RealTimeMetricService.
    """

    @pytest.fixture
    def service(self):
        return RealTimeMetricService()

    def test_raises_metric_not_found_error_for_missing_id(self, service):
        """FIX-METRIC-1: get_metric_or_raise() raises MetricNotFoundError."""
        with pytest.raises(MetricNotFoundError, match='not found'):
            service.get_metric_or_raise(999999)

    def test_raises_with_descriptive_message(self, service):
        """FIX-METRIC-1: error message includes the requested ID."""
        metric_id = 777777
        with pytest.raises(MetricNotFoundError, match=str(metric_id)):
            service.get_metric_or_raise(metric_id)

    def test_returns_metric_when_found(self, service):
        """FIX-METRIC-1: positive case — returns the metric object."""
        metric = create_real_time_metric(name='FoundMetric', value=42.0)
        result = service.get_metric_or_raise(metric.pk)
        assert result.pk == metric.pk
        assert result.name == 'FoundMetric'

    def test_get_metric_still_returns_none_for_missing(self, service):
        """
        FIX-METRIC-1: get_metric() (the original method) must still return
        None for backwards compatibility with callers that do optional-chaining.
        Only get_metric_or_raise() raises.
        """
        result = service.get_metric(999999)
        assert result is None

    def test_delete_metric_removes_existing_metric(self, service):
        """
        FIX-DELETE-1 / v1.5.0: delete_metric() succeeds (no exception) for
        an existing metric. Signature changed from delete_metric(id) to
        delete_metric(instance) so perform_destroy() can pass the instance
        DRF's get_object() already fetched, with no redundant re-query.
        The "missing id" case is no longer this method's concern — DRF's
        get_object() 404s before perform_destroy() (and therefore this
        method) is ever reached; see
        TestRealTimeMetricViewSet.test_delete_metric_not_found in
        test_viewsets.py for that path.
        """
        from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
        metric = create_real_time_metric(name='ToDelete')
        pk = metric.pk

        service.delete_metric(metric)

        assert not RealTimeMetric.objects.filter(pk=pk).exists()


# ─── FIX-THRESHOLD: check_thresholds() DRY compliance ───────────────────────

@pytest.mark.django_db
class TestCheckThresholds:
    """
    Verify that RealTimeMetricService.check_thresholds() produces the correct
    severity levels. This doubles as coverage for the utils.check_metric_thresholds
    delegation (DRY fix — previously duplicated logic existed in two places).
    """

    @pytest.fixture
    def service(self):
        return RealTimeMetricService()

    def test_returns_critical_when_above_critical_threshold(self, service):
        metric = create_real_time_metric(
            value=95.0, warning_threshold=80.0, critical_threshold=90.0
        )
        assert service.check_thresholds(metric) == 'critical'

    def test_returns_warning_when_above_warning_threshold(self, service):
        metric = create_real_time_metric(
            value=85.0, warning_threshold=80.0, critical_threshold=90.0
        )
        assert service.check_thresholds(metric) == 'warning'

    def test_returns_normal_when_below_warning_threshold(self, service):
        metric = create_real_time_metric(
            value=50.0, warning_threshold=80.0, critical_threshold=90.0
        )
        assert service.check_thresholds(metric) == 'normal'

    def test_returns_normal_when_no_thresholds_set(self, service):
        metric = create_real_time_metric(
            value=100.0, warning_threshold=None, critical_threshold=None
        )
        assert service.check_thresholds(metric) == 'normal'

    def test_critical_threshold_exactly_at_boundary(self, service):
        metric = create_real_time_metric(
            value=90.0, warning_threshold=80.0, critical_threshold=90.0
        )
        # At exactly the critical threshold → 'critical'
        assert service.check_thresholds(metric) == 'critical'

    def test_warning_threshold_exactly_at_boundary(self, service):
        metric = create_real_time_metric(
            value=80.0, warning_threshold=80.0, critical_threshold=90.0
        )
        # At exactly the warning threshold → 'warning'
        assert service.check_thresholds(metric) == 'warning'


# ─── FIX-UPDATE: update_metric tracks previous value ─────────────────────────

@pytest.mark.django_db
class TestUpdateMetricValue:
    """
    update_metric() must set previous_value before overwriting value.

    v1.5.0: update_metric_value(id, value) was removed — it duplicated
    exactly this previous_value-tracking rule with a narrower signature
    (only 'value', fetched by id) while update_metric(instance, data)
    (the method perform_update() actually calls) already covered the
    identical rule for any field set including 'value'. Keeping both
    was the DRY violation the 360-degree audit flagged; these tests now
    exercise the single remaining implementation.
    """

    @pytest.fixture
    def service(self):
        return RealTimeMetricService()

    def test_previous_value_is_updated(self, service):
        metric = create_real_time_metric(value=100.0)
        service.update_metric(metric, {'value': 200.0})
        metric.refresh_from_db()
        assert metric.value == 200.0
        assert metric.previous_value == 100.0

    def test_consecutive_updates_track_correctly(self, service):
        metric = create_real_time_metric(value=10.0)
        service.update_metric(metric, {'value': 20.0})
        service.update_metric(metric, {'value': 30.0})
        metric.refresh_from_db()
        assert metric.value == 30.0
        assert metric.previous_value == 20.0

    def test_same_value_does_not_overwrite_previous_value(self, service):
        """Re-submitting the SAME value must not touch previous_value at all."""
        metric = create_real_time_metric(value=50.0, previous_value=10.0)
        service.update_metric(metric, {'value': 50.0})
        metric.refresh_from_db()
        assert metric.value == 50.0
        assert metric.previous_value == 10.0
