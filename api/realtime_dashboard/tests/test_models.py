"""
Tests for Real-time Dashboard Backend models and custom managers.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
from api.realtime_dashboard.models.widget_configuration import WidgetConfiguration
from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
from api.realtime_dashboard.models.dashboard_layout import DashboardLayout
from api.realtime_dashboard.models.user_dashboard import UserDashboard
from api.realtime_dashboard.models.websocket_connection import WebSocketConnection
from .fixtures import (
    create_dashboard_widget,
    create_widget_configuration,
    create_real_time_metric,
    create_dashboard_layout,
    create_user_dashboard,
    create_websocket_connection,
)


@pytest.mark.django_db
class TestDashboardWidget:
    """Tests for DashboardWidget model."""

    def test_create_widget(self):
        widget = create_dashboard_widget()
        assert widget.name == 'Test Widget'
        assert widget.widget_type == DashboardWidget.WidgetType.CHART
        assert widget.status == DashboardWidget.WidgetStatus.ACTIVE
        assert widget.refresh_interval == 60
        assert widget.width == 6
        assert widget.height == 4

    def test_widget_string_representation(self):
        widget = create_dashboard_widget(name='My Widget', widget_type='chart')
        assert str(widget) == 'My Widget (chart)'

    def test_widget_choices(self):
        assert 'chart' in DashboardWidget.WidgetType.values
        assert 'table' in DashboardWidget.WidgetType.values
        assert 'active' in DashboardWidget.WidgetStatus.values
        assert 'inactive' in DashboardWidget.WidgetStatus.values

    def test_widget_validation(self):
        """
        v1.5.0: this used to call create_dashboard_widget(refresh_interval=-1)
        — i.e. .objects.create(), an actual DB write — inside the
        pytest.raises(ValidationError) block, then call full_clean() on
        the result. That only worked because nothing stopped an invalid
        row from being written in the first place; full_clean() was
        catching it a step too late. Constructed as an unsaved instance
        instead, so this now tests full_clean() specifically (the model
        field's MinValueValidator(0)), without touching the DB. See
        test_widget_create_rejects_negative_refresh_interval_at_db_level
        for the new, stronger guarantee added in this audit pass.
        """
        widget = DashboardWidget(
            name='Unsaved', widget_type=DashboardWidget.WidgetType.CHART,
            status=DashboardWidget.WidgetStatus.ACTIVE, refresh_interval=-1,
            width=6, height=4,
        )
        with pytest.raises(ValidationError):
            widget.full_clean()

    def test_widget_create_rejects_negative_refresh_interval_at_db_level(self):
        """
        v1.5.0: dw_refresh_interval_non_negative CheckConstraint (added
        alongside DashboardWidget.clean()) now rejects a negative
        refresh_interval at INSERT time, regardless of whether anything
        remembered to call full_clean() first — closing the gap the
        previous version of this test's own setup silently relied on.
        """
        with pytest.raises(IntegrityError):
            create_dashboard_widget(refresh_interval=-1)

    def test_widget_create_rejects_out_of_range_width_at_db_level(self):
        """v1.5.0: dw_width_in_grid_range CheckConstraint (grid is 1-12 columns)."""
        with pytest.raises(IntegrityError):
            create_dashboard_widget(width=13)

    def test_widget_create_rejects_out_of_range_height_at_db_level(self):
        """v1.5.0: dw_height_in_grid_range CheckConstraint (grid is 1-24 rows)."""
        with pytest.raises(IntegrityError):
            create_dashboard_widget(height=0)

    def test_widget_clean_rejects_out_of_range_width(self):
        """v1.5.0: DashboardWidget.clean() — the friendly-ValidationError companion to the DB constraint."""
        widget = DashboardWidget(
            name='Unsaved', widget_type=DashboardWidget.WidgetType.CHART,
            status=DashboardWidget.WidgetStatus.ACTIVE, refresh_interval=60,
            width=13, height=4,
        )
        with pytest.raises(ValidationError, match='width'):
            widget.clean()

    def test_widget_clean_rejects_out_of_range_height(self):
        """v1.5.0: same as above, for height."""
        widget = DashboardWidget(
            name='Unsaved', widget_type=DashboardWidget.WidgetType.CHART,
            status=DashboardWidget.WidgetStatus.ACTIVE, refresh_interval=60,
            width=6, height=25,
        )
        with pytest.raises(ValidationError, match='height'):
            widget.clean()

    def test_widget_clean_accepts_valid_dimensions(self):
        """v1.5.0: positive control — clean() must NOT raise for in-range values."""
        widget = DashboardWidget(
            name='Unsaved', widget_type=DashboardWidget.WidgetType.CHART,
            status=DashboardWidget.WidgetStatus.ACTIVE, refresh_interval=60,
            width=6, height=4,
        )
        widget.clean()  # should not raise

    # --- WidgetManager / WidgetQuerySet ---

    def test_manager_active_returns_only_active(self):
        create_dashboard_widget(name='A', status='active')
        create_dashboard_widget(name='B', status='inactive')
        create_dashboard_widget(name='C', status='archived')
        qs = DashboardWidget.objects.active()
        statuses = list(qs.values_list('status', flat=True))
        assert all(s == 'active' for s in statuses)
        assert qs.filter(name='A').exists()
        assert not qs.filter(name='B').exists()

    def test_manager_by_type(self):
        create_dashboard_widget(name='Chart1', widget_type='chart')
        create_dashboard_widget(name='Table1', widget_type='table')
        charts = DashboardWidget.objects.by_type('chart')
        assert charts.filter(name='Chart1').exists()
        assert not charts.filter(name='Table1').exists()

    def test_manager_by_status(self):
        create_dashboard_widget(name='X', status='archived')
        qs = DashboardWidget.objects.by_status('archived')
        assert qs.filter(name='X').exists()

    def test_queryset_methods_chainable(self):
        """Verify manager methods work on QuerySet clones (from_queryset)."""
        create_dashboard_widget(name='ChartActive', widget_type='chart', status='active')
        create_dashboard_widget(name='ChartInactive', widget_type='chart', status='inactive')
        # Chain manager method on a filtered queryset clone
        result = DashboardWidget.objects.filter(widget_type='chart').active()
        assert result.filter(name='ChartActive').exists()
        assert not result.filter(name='ChartInactive').exists()


@pytest.mark.django_db
class TestWidgetConfiguration:
    """Tests for WidgetConfiguration model."""

    def test_create_configuration(self):
        widget = create_dashboard_widget()
        config = create_widget_configuration(widget)
        assert config.widget == widget
        assert config.config_type == WidgetConfiguration.ConfigType.CHART
        assert config.key == 'test_config'

    def test_configuration_string_representation(self):
        widget = create_dashboard_widget(name='Test Widget')
        config = create_widget_configuration(widget, key='config_key')
        assert str(config) == 'Test Widget - config_key'

    def test_configuration_unique_constraint(self):
        widget = create_dashboard_widget()
        create_widget_configuration(widget, key='config_key')
        with pytest.raises(Exception):
            create_widget_configuration(widget, key='config_key')


@pytest.mark.django_db
class TestRealTimeMetric:
    """Tests for RealTimeMetric model."""

    def test_create_metric(self):
        metric = create_real_time_metric()
        assert metric.name == 'Test Metric'
        assert metric.metric_type == RealTimeMetric.MetricType.GAUGE
        assert metric.status == RealTimeMetric.MetricStatus.ACTIVE
        assert metric.value == 100.0
        assert metric.unit == 'units'

    def test_metric_string_representation(self):
        metric = create_real_time_metric(name='My Metric', metric_type='gauge')
        assert str(metric) == 'My Metric (gauge)'

    def test_metric_thresholds(self):
        metric = create_real_time_metric(warning_threshold=80.0, critical_threshold=90.0)
        assert metric.warning_threshold == 80.0
        assert metric.critical_threshold == 90.0

    def test_metric_clean_rejects_warning_gte_critical(self):
        """v1.5.0: RealTimeMetric.clean() — friendly-ValidationError companion to the DB constraint."""
        metric = RealTimeMetric(
            name='Unsaved', metric_type=RealTimeMetric.MetricType.GAUGE,
            status=RealTimeMetric.MetricStatus.ACTIVE, value=100.0,
            warning_threshold=90.0, critical_threshold=90.0,  # equal -> invalid
        )
        with pytest.raises(ValidationError, match='warning_threshold'):
            metric.clean()

    def test_metric_clean_accepts_valid_thresholds(self):
        """v1.5.0: positive control — clean() must NOT raise when warning < critical."""
        metric = RealTimeMetric(
            name='Unsaved', metric_type=RealTimeMetric.MetricType.GAUGE,
            status=RealTimeMetric.MetricStatus.ACTIVE, value=100.0,
            warning_threshold=80.0, critical_threshold=90.0,
        )
        metric.clean()  # should not raise

    def test_metric_clean_accepts_thresholds_unset(self):
        """v1.5.0: positive control — clean() must NOT raise when either threshold is None."""
        metric = RealTimeMetric(
            name='Unsaved', metric_type=RealTimeMetric.MetricType.GAUGE,
            status=RealTimeMetric.MetricStatus.ACTIVE, value=100.0,
            warning_threshold=None, critical_threshold=None,
        )
        metric.clean()  # should not raise

    def test_metric_create_rejects_warning_gte_critical_at_db_level(self):
        """v1.5.0: rtm_warning_lt_critical CheckConstraint rejects it at INSERT time too."""
        with pytest.raises(IntegrityError):
            create_real_time_metric(warning_threshold=90.0, critical_threshold=80.0)

    def test_metric_create_allows_thresholds_unset_at_db_level(self):
        """v1.5.0: positive control — the OR isnull clauses must let NULL thresholds through."""
        metric = create_real_time_metric(warning_threshold=None, critical_threshold=None)
        assert metric.warning_threshold is None

    def test_metric_auto_update_last_updated(self):
        metric = create_real_time_metric()
        original_updated = metric.last_updated
        metric.value = 150.0
        metric.save()
        assert metric.last_updated >= original_updated

    # --- RealTimeMetricManager ---

    def test_manager_active(self):
        create_real_time_metric(name='ActiveM', status='active')
        create_real_time_metric(name='InactiveM', status='inactive')
        qs = RealTimeMetric.objects.active()
        assert qs.filter(name='ActiveM').exists()
        assert not qs.filter(name='InactiveM').exists()

    def test_manager_by_type(self):
        create_real_time_metric(name='Gauge1', metric_type='gauge')
        create_real_time_metric(name='Counter1', metric_type='counter')
        gauges = RealTimeMetric.objects.by_type('gauge')
        assert gauges.filter(name='Gauge1').exists()
        assert not gauges.filter(name='Counter1').exists()

    def test_manager_by_status(self):
        create_real_time_metric(name='Err', status='error')
        qs = RealTimeMetric.objects.by_status('error')
        assert qs.filter(name='Err').exists()


@pytest.mark.django_db
class TestDashboardLayout:
    """Tests for DashboardLayout model."""

    def test_create_layout(self):
        layout = create_dashboard_layout()
        assert layout.name == 'Test Layout'
        assert layout.layout_type == DashboardLayout.LayoutType.GRID
        assert layout.columns == 12
        assert layout.rows == 12

    def test_layout_string_representation(self):
        layout = create_dashboard_layout(name='My Layout', layout_type='grid')
        assert str(layout) == 'My Layout (grid)'

    def test_layout_configuration_json(self):
        config = {'grid': {'columns': 12, 'rows': 12}}
        layout = create_dashboard_layout(configuration=config)
        assert layout.configuration == config


@pytest.mark.django_db
class TestUserDashboard:
    """Tests for UserDashboard model."""

    def test_create_dashboard(self):
        dashboard = create_user_dashboard()
        assert dashboard.name == 'Test Dashboard'
        assert dashboard.status == UserDashboard.DashboardStatus.ACTIVE
        assert dashboard.user_id == 'test_user_123'
        assert dashboard.widgets == []

    def test_dashboard_string_representation(self):
        dashboard = create_user_dashboard(name='My Dashboard', user_id='user123')
        assert str(dashboard) == 'My Dashboard (user123)'

    def test_dashboard_with_layout(self):
        layout = create_dashboard_layout()
        dashboard = create_user_dashboard(layout=layout)
        assert dashboard.layout == layout

    # --- DashboardManager ---

    def test_manager_by_user(self):
        create_user_dashboard(name='U1D1', user_id='user1')
        create_user_dashboard(name='U1D2', user_id='user1')
        create_user_dashboard(name='U2D1', user_id='user2')
        qs = UserDashboard.objects.by_user('user1')
        assert qs.count() == 2
        assert not qs.filter(user_id='user2').exists()

    def test_manager_active(self):
        create_user_dashboard(name='Act', status='active')
        create_user_dashboard(name='Inact', status='inactive')
        qs = UserDashboard.objects.active()
        assert qs.filter(name='Act').exists()
        assert not qs.filter(name='Inact').exists()

    def test_manager_chain_by_user_active(self):
        create_user_dashboard(name='U1Active', user_id='user1', status='active')
        create_user_dashboard(name='U1Inactive', user_id='user1', status='inactive')
        create_user_dashboard(name='U2Active', user_id='user2', status='active')
        qs = UserDashboard.objects.by_user('user1').active()
        assert qs.count() == 1
        assert qs.first().name == 'U1Active'


@pytest.mark.django_db
class TestWebSocketConnection:
    """Tests for WebSocketConnection model."""

    def test_create_connection(self):
        connection = create_websocket_connection()
        assert connection.connection_id == 'test_connection_123'
        assert connection.user_id == 'test_user_123'
        assert connection.status == WebSocketConnection.ConnectionStatus.CONNECTED

    def test_connection_string_representation(self):
        connection = create_websocket_connection(connection_id='conn123', status='connected')
        assert str(connection) == 'conn123 (connected)'

    def test_connection_unique_constraint(self):
        create_websocket_connection(connection_id='conn123')
        with pytest.raises(Exception):
            create_websocket_connection(connection_id='conn123')

    def test_connection_disconnected_at(self):
        connection = create_websocket_connection()
        assert connection.disconnected_at is None
        connection.status = WebSocketConnection.ConnectionStatus.DISCONNECTED
        connection.disconnected_at = timezone.now()
        connection.save()
        assert connection.disconnected_at is not None

    def test_last_ping_not_overwritten_on_unrelated_save(self):
        """Verify the last_ping auto_now=True fix: saving an unrelated
        field must NOT reset last_ping to now."""
        from datetime import timedelta
        connection = create_websocket_connection()
        old_ping = timezone.now() - timedelta(hours=2)
        WebSocketConnection.objects.filter(pk=connection.pk).update(last_ping=old_ping)
        connection.refresh_from_db()
        assert connection.last_ping == old_ping

        # Saving an unrelated field (status) must leave last_ping unchanged
        connection.status = 'disconnected'
        connection.save()
        connection.refresh_from_db()
        assert connection.last_ping == old_ping  # would have reset with auto_now=True

    # --- WebSocketConnectionManager ---

    def test_manager_active(self):
        create_websocket_connection(connection_id='c1', status='connected')
        create_websocket_connection(connection_id='c2', status='disconnected')
        qs = WebSocketConnection.objects.active()
        assert qs.filter(connection_id='c1').exists()
        assert not qs.filter(connection_id='c2').exists()

    def test_manager_by_user(self):
        create_websocket_connection(connection_id='u1c1', user_id='user1')
        create_websocket_connection(connection_id='u2c1', user_id='user2')
        qs = WebSocketConnection.objects.by_user('user1')
        assert qs.filter(connection_id='u1c1').exists()
        assert not qs.filter(connection_id='u2c1').exists()


@pytest.mark.django_db
class TestWebSocketConnectionMigrationState:
    """
    Guards the finding from the remaining-tasks audit: disconnected_at is
    now written by track_disconnect() (base_consumer.py) AND by
    WebSocketManagerService.remove_connection() (websocket_manager.py), so
    it must be nullable both on the model AND in the migration that
    created the column, or a NOT NULL constraint would raise on the very
    first disconnect on a fresh database.

    Verified by inspection: 0001_initial.py already declares
    ('disconnected_at', models.DateTimeField(blank=True, null=True)) and
    `manage.py makemigrations --check` reports no pending changes — the
    model and migration state already agree, so no new migration was
    required. These two tests lock that fact in going forward.
    """

    def test_disconnected_at_field_is_nullable(self):
        field = WebSocketConnection._meta.get_field('disconnected_at')
        assert field.null is True
        assert field.blank is True

    def test_no_pending_migrations_for_this_app(self):
        """
        Equivalent of `manage.py makemigrations realtime_dashboard --check
        --dry-run`: fails loudly if a model field is ever changed without
        a matching migration being generated.
        """
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError

        out = StringIO()
        try:
            call_command(
                'makemigrations', 'realtime_dashboard',
                '--check', '--dry-run', stdout=out, stderr=out,
            )
        except (SystemExit, CommandError) as exc:
            pytest.fail(f'Model state has changes not reflected in a migration: {exc}\n{out.getvalue()}')
