# api/admin_panel/admin_dashboard_widgets.py
"""All dashboard widget data providers — single file for all widgets."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class DashboardWidgets:
    """Provides data for all admin dashboard widgets."""

    @classmethod
    def users_stat_card(cls) -> Dict:
        from api.admin_panel.selectors import get_user_count, get_new_users_count
        return {
            'widget': 'users', 'label': 'Total Users',
            'value': get_user_count(), 'sub_value': get_new_users_count(1),
            'sub_label': 'new today', 'trend': 'up',
            'icon': '👤', 'color': '#4F46E5',
        }

    @classmethod
    def revenue_stat_card(cls, days: int = 1) -> Dict:
        from api.admin_panel.analytics import get_revenue_overview
        data = get_revenue_overview(days)
        return {
            'widget': 'revenue', 'label': f"Revenue ({days}d)",
            'value': data.get('total_earned', 0), 'currency': '৳',
            'icon': '💰', 'color': '#10B981',
        }

    @classmethod
    def pending_payouts_card(cls) -> Dict:
        from api.admin_panel.selectors import get_payout_stats
        stats = get_payout_stats(1)
        return {
            'widget': 'payouts', 'label': 'Pending Payouts',
            'value': stats.get('pending', 0),
            'sub_value': stats.get('total_pending_amount', 0),
            'sub_label': '৳ pending', 'icon': '💳', 'color': '#F59E0B',
            'action': '/admin-panel/payouts/pending/',
        }

    @classmethod
    def fraud_alerts_card(cls) -> Dict:
        from api.admin_panel.analytics import get_fraud_analytics
        data = get_fraud_analytics(1)
        return {
            'widget': 'fraud', 'label': 'Fraud Alerts (24h)',
            'value': data.get('total', 0),
            'sub_value': data.get('critical', 0),
            'sub_label': 'critical', 'icon': '🚨',
            'color': '#EF4444' if data.get('critical', 0) > 0 else '#6B7280',
        }

    @classmethod
    def kyc_pending_card(cls) -> Dict:
        from api.admin_panel.selectors import get_kyc_stats
        stats = get_kyc_stats()
        return {
            'widget': 'kyc', 'label': 'KYC Pending',
            'value': stats.get('pending', 0), 'icon': '🪪',
            'color': '#8B5CF6',
            'action': '/admin-panel/kyc/pending/',
        }

    @classmethod
    def system_health_card(cls) -> Dict:
        from api.admin_panel.monitoring import get_system_health_score
        score = get_system_health_score()
        return {
            'widget': 'health', 'label': 'System Health',
            'value': score, 'unit': '%',
            'color': '#10B981' if score >= 90 else '#F59E0B' if score >= 70 else '#EF4444',
            'icon': '🏥',
        }

    @classmethod
    def revenue_chart(cls, days: int = 7) -> Dict:
        from api.admin_panel.analytics import get_daily_revenue_trend
        trend = get_daily_revenue_trend(days)
        return {
            'widget': 'revenue_chart', 'type': 'line_chart',
            'title': f'Revenue ({days} days)',
            'data': [{'x': str(d.get('day')), 'y': float(d.get('total') or 0)} for d in trend],
            'color': '#10B981',
        }

    @classmethod
    def user_registration_chart(cls, days: int = 7) -> Dict:
        from api.admin_panel.analytics import get_user_registration_trend
        trend = get_user_registration_trend(days)
        return {
            'widget': 'reg_chart', 'type': 'bar_chart',
            'title': f'Registrations ({days} days)',
            'data': [{'x': str(d.get('day')), 'y': d.get('count', 0)} for d in trend],
            'color': '#4F46E5',
        }

    @classmethod
    def fraud_by_type_chart(cls, days: int = 7) -> Dict:
        from api.admin_panel.analytics import get_fraud_analytics
        data = get_fraud_analytics(days)
        return {
            'widget': 'fraud_chart', 'type': 'donut_chart',
            'title': 'Fraud by Type',
            'data': [{'label': d.get('attempt_type', 'unknown'), 'value': d.get('c', 0)}
                     for d in data.get('by_type', [])],
        }

    @classmethod
    def get_all_widgets(cls, days: int = 7) -> List[Dict]:
        """Get all widget data in one call."""
        widgets = []
        for method in [
            cls.users_stat_card, lambda: cls.revenue_stat_card(days),
            cls.pending_payouts_card, cls.fraud_alerts_card,
            cls.kyc_pending_card, cls.system_health_card,
            lambda: cls.revenue_chart(days),
            lambda: cls.user_registration_chart(days),
            lambda: cls.fraud_by_type_chart(days),
        ]:
            try:
                widgets.append(method())
            except Exception as e:
                logger.debug(f"[DashboardWidgets] {e}")
        return widgets


widgets = DashboardWidgets()