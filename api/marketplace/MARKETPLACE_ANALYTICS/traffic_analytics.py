"""
MARKETPLACE_ANALYTICS/traffic_analytics.py — Traffic & Session Analytics
"""
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone


def daily_sessions(tenant, days: int = 30) -> list:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, event_type="app_open", created_at__gte=since)
        .annotate(day=TruncDay("created_at"))
        .values("day","platform")
        .annotate(sessions=Count("session_id",distinct=True), users=Count("user",distinct=True))
        .order_by("day")
    )


def peak_hours(tenant, days: int = 7) -> list:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, created_at__gte=since)
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("-count")[:24]
    )


def platform_breakdown(tenant, days: int = 30) -> list:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, created_at__gte=since)
        .values("platform")
        .annotate(sessions=Count("session_id",distinct=True))
        .order_by("-sessions")
    )


def top_search_queries(tenant, days: int = 7) -> list:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, event_type="search", created_at__gte=since)
        .values("properties__query")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
