# api/analytics/services.py
"""
Business logic for analytics. Move complex logic out of views.
"""
import logging
from typing import Dict, Any
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for aggregated analytics."""

    @staticmethod
    def get_platform_summary(days: int = 30) -> Dict[str, Any]:
        """Return high-level platform metrics."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        since = timezone.now() - timedelta(days=days)
        return {
            "period_days": days,
            "new_users": User.objects.filter(date_joined__gte=since).count(),
            "total_users": User.objects.count(),
        }
