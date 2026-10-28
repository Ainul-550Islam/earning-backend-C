# api/rate_limit/analytics.py
"""Analytics helpers for rate limit module."""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class RateLimitAnalytics:
    """Aggregate analytics for rate limit data."""

    def get_summary(self, days=7):
        try:
            from api.rate_limit.models import RateLimitLog
            since = timezone.now() - timedelta(days=days)
            qs = RateLimitLog.objects.filter(timestamp__gte=since)
            return {
                "total": qs.count(),
                "blocked": qs.filter(status="blocked").count(),
                "allowed": qs.filter(status="allowed").count(),
            }
        except Exception as e:
            logger.error(f"Analytics summary error: {e}")
            return {"total": 0, "blocked": 0, "allowed": 0}

    def get_top_abusers(self, limit=10):
        try:
            from api.rate_limit.models import RateLimitLog
            from django.db.models import Count
            return list(
                RateLimitLog.objects.filter(status="blocked")
                .values("user_id")
                .annotate(count=Count("id"))
                .order_by("-count")[:limit]
            )
        except Exception as e:
            logger.error(f"Top abusers error: {e}")
            return []


__all__ = ["RateLimitAnalytics"]


class AnalyticsEngine(RateLimitAnalytics):
    """Extended analytics engine with advanced aggregation."""

    def get_trend(self, days=30):
        data = []
        from api.rate_limit.models import RateLimitLog
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        for i in range(days):
            date = (timezone.now() - timedelta(days=i)).date()
            count = RateLimitLog.objects.filter(timestamp__date=date).count()
            data.append({'date': str(date), 'count': count})
        return data

    def get_endpoint_stats(self, limit=10):
        from api.rate_limit.models import RateLimitLog
        from django.db.models import Count
        return list(
            RateLimitLog.objects.values('endpoint')
            .annotate(count=Count('id')).order_by('-count')[:limit]
        )
