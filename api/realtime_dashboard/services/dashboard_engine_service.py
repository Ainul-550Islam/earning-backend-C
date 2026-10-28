"""
Dashboard Engine service for Real-time Dashboard Backend.

This service is the single owner of dashboard-render operations.
Viewsets, tasks, and management commands call this service only —
they never instantiate DashboardEngine directly.

Ownership chain:
    ViewSet.render()  →  DashboardEngineService  →  DashboardEngine
                                                  →  RealTimeMetricService
                                                  →  WidgetService
"""
import logging
from typing import Dict, Any, List

from ..dashboard_engine import DashboardEngine
from ..exceptions import DashboardEngineError

logger = logging.getLogger(__name__)


class DashboardEngineService:
    """Service wrapping DashboardEngine for dashboard render operations."""

    def __init__(self) -> None:
        self.engine = DashboardEngine()

    def render_dashboard(self, dashboard_id: int) -> Dict[str, Any]:
        """
        Render a full dashboard: layout + widget data + live metrics.

        Args:
            dashboard_id: UserDashboard primary key

        Returns:
            Assembled dashboard dict ready for the API response.

        Raises:
            DashboardEngineError: if the dashboard or any widget is not found.
        """
        data = self.engine.render_dashboard(dashboard_id)
        logger.debug('render_dashboard: dashboard_id=%d', dashboard_id)
        return data

    def get_widget_data(self, widget_id: int) -> Dict[str, Any]:
        """
        Return assembled data for a single widget (config + live metrics).

        Args:
            widget_id: DashboardWidget primary key

        Returns:
            Widget dict with embedded metric snapshots.

        Raises:
            DashboardEngineError: if the widget is not found.
        """
        return self.engine.get_widget_data(widget_id)

    def get_dashboard_widget_ids(self, dashboard_id: int) -> List[int]:
        """
        Return the list of widget IDs attached to a dashboard.

        Convenience method used by tasks and tests that need widget IDs
        without triggering a full render.

        FIXED: previously called `dashboard.widgets.values_list('id', flat=True)`,
        treating `UserDashboard.widgets` as a ManyToManyField or related
        manager. `widgets` is defined as `JSONField(default=list)`, which
        stores a plain Python list of integer widget IDs — it is NOT a
        relational field and has no queryset or `.values_list()` method.
        Calling `.values_list()` on a list raises AttributeError at runtime.

        The correct implementation simply casts the JSON list to a Python
        list: `list(dashboard.widgets)`. The cast is defensive — if widgets
        is somehow stored as None, `list(None)` raises TypeError, which is
        preferable to silently returning an incorrect value.

        Args:
            dashboard_id: UserDashboard primary key

        Returns:
            List of integer widget IDs stored in dashboard.widgets JSONField.

        Raises:
            DashboardEngineError: if the dashboard does not exist.
        """
        from ..models.user_dashboard import UserDashboard
        try:
            dashboard = UserDashboard.objects.get(id=dashboard_id)
        except UserDashboard.DoesNotExist:
            raise DashboardEngineError(f'Dashboard {dashboard_id} not found')

        # widgets is a JSONField(default=list) — a plain Python list of IDs.
        # .values_list() is a QuerySet method and does not exist on a list.
        return list(dashboard.widgets)
