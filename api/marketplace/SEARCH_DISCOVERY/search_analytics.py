"""
SEARCH_DISCOVERY/search_analytics.py — Search Performance Analytics
"""
from django.db import models
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta


class SearchLog(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="search_logs_tenant")
    query       = models.CharField(max_length=500)
    results_count = models.PositiveIntegerField(default=0)
    clicked_product_id = models.IntegerField(null=True, blank=True)
    user_id     = models.IntegerField(null=True, blank=True)
    session_id  = models.CharField(max_length=64, blank=True)
    engine      = models.CharField(max_length=20, default="django_orm")
    took_ms     = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_search_log"
        indexes   = [models.Index(fields=["tenant","created_at"])]


def log_search(tenant, query: str, results_count: int, took_ms: int = 0,
               user=None, session_id: str = "", engine: str = "django_orm"):
    SearchLog.objects.create(
        tenant=tenant, query=query[:500], results_count=results_count,
        took_ms=took_ms, user_id=getattr(user,"pk",None),
        session_id=session_id, engine=engine,
    )


def get_top_queries(tenant, days: int = 7, limit: int = 20) -> list:
    since = timezone.now() - timedelta(days=days)
    return list(
        SearchLog.objects.filter(tenant=tenant, created_at__gte=since)
        .values("query")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


def get_zero_result_queries(tenant, days: int = 7) -> list:
    since = timezone.now() - timedelta(days=days)
    return list(
        SearchLog.objects.filter(tenant=tenant, created_at__gte=since, results_count=0)
        .values("query")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
