# api/admin_panel/dashboard_builder.py
"""Custom widget drag-drop dashboard builder."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class DashboardBuilder:
    """Build custom admin dashboard layouts."""

    WIDGET_TYPES = {
        'stat_card':     'Single metric card with trend',
        'line_chart':    'Time series line chart',
        'bar_chart':     'Bar/column chart',
        'donut_chart':   'Donut/pie chart',
        'data_table':    'Sortable data table',
        'map':           'Geo heatmap',
        'activity_feed': 'Recent activity list',
        'fraud_live':    'Real-time fraud alerts',
        'user_online':   'Online users counter',
    }

    @classmethod
    def create_layout(cls, user, name: str, widgets: List[Dict]) -> Dict:
        """Save a custom dashboard layout."""
        try:
            from api.admin_panel.models.dashboard import DashboardLayout
            layout = DashboardLayout.objects.create(
                user=user, name=name, widgets=widgets, is_active=True,
            )
            return {'success': True, 'layout_id': layout.pk, 'name': name, 'widget_count': len(widgets)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_user_layout(cls, user) -> Optional[Dict]:
        try:
            from api.admin_panel.models.dashboard import DashboardLayout
            layout = DashboardLayout.objects.filter(user=user, is_active=True).first()
            if layout:
                return {'layout_id': layout.pk, 'name': layout.name, 'widgets': layout.widgets}
        except Exception:
            pass
        return None

    @classmethod
    def get_widget_data(cls, widget_type: str, config: Dict = None) -> Dict:
        """Fetch live data for a dashboard widget."""
        config = config or {}
        days = config.get('days', 7)
        from api.admin_panel.analytics import (
            get_revenue_overview, get_user_overview,
            get_offer_analytics, get_fraud_analytics
        )
        data_map = {
            'stat_card':     lambda: get_user_overview(),
            'revenue':       lambda: get_revenue_overview(days),
            'offers':        lambda: get_offer_analytics(days),
            'fraud_live':    lambda: get_fraud_analytics(1),
        }
        fn = data_map.get(widget_type, lambda: {})
        try:
            return {'widget_type': widget_type, 'data': fn(), 'fetched_at': timezone.now().isoformat()}
        except Exception as e:
            return {'widget_type': widget_type, 'error': str(e)}

    @classmethod
    def list_widget_types(cls) -> List[Dict]:
        return [{'type': k, 'description': v} for k, v in cls.WIDGET_TYPES.items()]

dashboard_builder = DashboardBuilder()
from typing import Optional