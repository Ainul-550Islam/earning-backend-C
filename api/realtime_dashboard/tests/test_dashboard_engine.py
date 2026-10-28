"""
Tests for Real-time Dashboard Backend dashboard engine.
"""
import pytest
from api.realtime_dashboard.dashboard_engine import DashboardEngine
from api.realtime_dashboard.exceptions import DashboardEngineError
from .fixtures import (
    create_dashboard_widget,
    create_real_time_metric,
    create_user_dashboard
)


@pytest.mark.django_db
class TestDashboardEngine:
    """Tests for DashboardEngine."""

    @pytest.fixture
    def engine(self):
        return DashboardEngine()

    def test_render_dashboard(self, engine):
        """Test rendering a dashboard."""
        widget1 = create_dashboard_widget(name='Widget 1', widget_type='chart')
        widget2 = create_dashboard_widget(name='Widget 2', widget_type='metric')

        dashboard = create_user_dashboard(
            name='Test Dashboard',
            widgets=[widget1.id, widget2.id]
        )

        result = engine.render_dashboard(dashboard.id)

        assert result['id'] == dashboard.id
        assert result['name'] == 'Test Dashboard'
        assert len(result['widgets']) == 2
        assert result['widgets'][0]['name'] == 'Widget 1'

    def test_render_dashboard_not_found(self, engine):
        """Test rendering a non-existent dashboard."""
        with pytest.raises(DashboardEngineError):
            engine.render_dashboard(99999)

    def test_get_widget_data(self, engine):
        """Test getting widget data."""
        widget = create_dashboard_widget(
            name='Test Widget',
            widget_type='chart',
            data_source='test_source'
        )

        create_real_time_metric(
            name='Widget Metric',
            value=100.0,
            unit='units',
            metadata={'widget_id': widget.id}
        )

        result = engine.get_widget_data(widget.id)

        assert result['id'] == widget.id
        assert result['name'] == 'Test Widget'
        assert result['type'] == 'chart'
        assert result['data_source'] == 'test_source'
        assert len(result['metrics']) == 1
        assert result['metrics'][0]['name'] == 'Widget Metric'

    def test_get_widget_data_not_found(self, engine):
        """Test getting data for non-existent widget."""
        with pytest.raises(DashboardEngineError):
            engine.get_widget_data(99999)

    def test_get_widget_data_without_metrics(self, engine):
        """Test getting widget data without associated metrics."""
        widget = create_dashboard_widget(
            name='Test Widget',
            widget_type='chart'
        )

        result = engine.get_widget_data(widget.id)

        assert result['id'] == widget.id
        assert result['name'] == 'Test Widget'
        assert len(result['metrics']) == 0

    def test_render_dashboard_with_empty_widgets(self, engine):
        """Test rendering dashboard with no widgets."""
        dashboard = create_user_dashboard(
            name='Empty Dashboard',
            widgets=[]
        )

        result = engine.render_dashboard(dashboard.id)

        assert result['id'] == dashboard.id
        assert result['name'] == 'Empty Dashboard'
        assert len(result['widgets']) == 0

    def test_render_dashboard_with_invalid_widget_id(self, engine):
        """Test rendering dashboard with invalid widget ID."""
        dashboard = create_user_dashboard(
            name='Invalid Dashboard',
            widgets=[99999]
        )

        with pytest.raises(DashboardEngineError):
            engine.render_dashboard(dashboard.id)
