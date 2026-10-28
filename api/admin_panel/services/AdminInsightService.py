# api/admin_panel/services/AdminInsightService.py
"""Service for AI-powered admin insights."""
import logging
logger = logging.getLogger(__name__)


class AdminInsightService:
    @staticmethod
    def generate_all() -> dict:
        from ..tasks.insight_tasks import generate_insights
        return generate_insights()

    @staticmethod
    def get_unread_count() -> int:
        try:
            from ..models.reports import AdminInsight
            return AdminInsight.objects.filter(is_read=False, is_dismissed=False).count()
        except Exception:
            return 0

    @staticmethod
    def get_critical() -> list:
        try:
            from ..models.reports import AdminInsight
            from django.utils import timezone
            from django.db.models import Q
            return list(AdminInsight.objects.filter(
                priority='critical', is_dismissed=False
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
            ).order_by('-created_at'))
        except Exception:
            return []