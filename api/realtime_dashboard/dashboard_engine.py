"""
Dashboard Engine for Real-time Dashboard Backend.
"""
from typing import Dict, Any

from .models.dashboard_widget import DashboardWidget
from .models.user_dashboard import UserDashboard
from .exceptions import DashboardEngineError


class DashboardEngine:
    """
    Engine for dashboard operations.
    """

    def __init__(self):
        """Initialize the dashboard engine."""
        pass

    def render_dashboard(self, dashboard_id: int) -> Dict[str, Any]:
        """
        Render a dashboard.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            Dictionary of dashboard data

        Raises:
            DashboardEngineError: if the dashboard, or any widget it
                references, does not exist.
        """
        try:
            dashboard = UserDashboard.objects.get(id=dashboard_id)
        except UserDashboard.DoesNotExist:
            raise DashboardEngineError(f'Dashboard {dashboard_id} not found')

        # FIXED: DashboardWidget.objects.get(id=widget_id) below can raise
        # DashboardWidget.DoesNotExist if dashboard.widgets references a
        # widget that no longer exists. Previously only
        # UserDashboard.DoesNotExist was caught (in a single try/except
        # wrapping this whole loop), so DashboardWidget.DoesNotExist
        # propagated uncaught instead of being reported as a
        # DashboardEngineError -
        # test_render_dashboard_with_invalid_widget_id expected
        # DashboardEngineError but would have received
        # DashboardWidget.DoesNotExist.
        widgets = []
        for widget_id in dashboard.widgets:
            try:
                widget = DashboardWidget.objects.get(id=widget_id)
            except DashboardWidget.DoesNotExist:
                raise DashboardEngineError(
                    f'Widget {widget_id} referenced by dashboard {dashboard_id} was not found'
                )

            widgets.append({
                'id': widget.id,
                'name': widget.name,
                'type': widget.widget_type,
                'configuration': widget.configuration,
                'width': widget.width,
                'height': widget.height
            })

        return {
            'id': dashboard.id,
            'name': dashboard.name,
            'description': dashboard.description,
            'layout': dashboard.layout_id,
            'widgets': widgets
        }

    def get_widget_data(self, widget_id: int) -> Dict[str, Any]:
        """
        Get assembled data for a widget, including its live metrics.

        OWNERSHIP FIX: previously queried RealTimeMetric.objects.filter(...)
        directly inside DashboardEngine. RealTimeMetric queries belong to
        RealTimeMetricService; DashboardEngine delegates to it instead of
        reaching across ownership boundaries.

        Args:
            widget_id: Widget ID

        Returns:
            Dictionary of widget data with embedded metric snapshots

        Raises:
            DashboardEngineError: if the widget does not exist.
        """
        try:
            widget = DashboardWidget.objects.get(id=widget_id)
        except DashboardWidget.DoesNotExist:
            raise DashboardEngineError(f'Widget {widget_id} not found')

        # Delegate metric lookup to RealTimeMetricService (the metric owner).
        from .services.real_time_metric_service import RealTimeMetricService
        metric_service = RealTimeMetricService()
        # Metrics associated with this widget store widget_id in metadata.
        # The service exposes get_metrics_for_widget() for this purpose.
        metrics = metric_service.get_metrics_for_widget(widget_id)

        return {
            'id': widget.id,
            'name': widget.name,
            'type': widget.widget_type,
            'configuration': widget.configuration,
            'data_source': widget.data_source,
            'metrics': [
                {
                    'name': m.name,
                    'value': m.value,
                    'unit': m.unit,
                    'last_updated': m.last_updated.isoformat()
                }
                for m in metrics
            ]
        }
