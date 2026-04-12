"""
api/ai_engine/ANALYTICS_INSIGHTS/insight_generator.py
======================================================
Insight Generator — automated business insights।
"""

import logging
from typing import List, Dict, Any
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class InsightGenerator:
    """
    Automated business insight generation।
    Data analyze করে actionable insights তৈরি করো।
    """

    def generate(self, tenant_id=None) -> List[Dict]:
        insights = []
        insights.extend(self._user_insights(tenant_id))
        insights.extend(self._revenue_insights(tenant_id))
        insights.extend(self._offer_insights(tenant_id))
        insights.extend(self._fraud_insights(tenant_id))
        return insights

    def _user_insights(self, tenant_id) -> List[Dict]:
        insights = []
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            week_ago = timezone.now() - timedelta(days=7)
            new_users = User.objects.filter(date_joined__gte=week_ago).count()

            if new_users > 0:
                insights.append({
                    'type':        'trend',
                    'title':       f'{new_users} new users this week',
                    'priority':    'medium',
                    'description': f'User acquisition: {new_users} new registrations in the last 7 days.',
                    'data':        {'new_users_7d': new_users},
                })
        except Exception as e:
            logger.error(f"User insight error: {e}")
        return insights

    def _revenue_insights(self, tenant_id) -> List[Dict]:
        return []  # Extend with revenue analytics

    def _offer_insights(self, tenant_id) -> List[Dict]:
        return []  # Extend with offer performance analytics

    def _fraud_insights(self, tenant_id) -> List[Dict]:
        insights = []
        try:
            from ..models import AnomalyDetectionLog
            day_ago = timezone.now() - timedelta(hours=24)
            critical_count = AnomalyDetectionLog.objects.filter(
                severity='critical', created_at__gte=day_ago, status='open'
            ).count()

            if critical_count > 5:
                insights.append({
                    'type':        'risk',
                    'title':       f'{critical_count} critical fraud anomalies in last 24h',
                    'priority':    'urgent',
                    'description': f'Unusual fraud activity detected. Immediate review recommended.',
                    'data':        {'critical_anomalies': critical_count},
                })
        except Exception as e:
            logger.error(f"Fraud insight error: {e}")
        return insights
