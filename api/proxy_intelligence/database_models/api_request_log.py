"""API Request Log — model helpers and analytics."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class APIRequestLogManager(models.Manager):
    def recent(self, hours=24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def by_ip(self, ip_address: str, hours=24):
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            ip_address=ip_address, created_at__gte=since
        ).order_by("-created_at")

    def errors(self, tenant=None):
        qs = self.filter(status_code__gte=400)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-created_at")

    def slow_requests(self, min_ms=1000, tenant=None):
        qs = self.filter(response_time_ms__gte=min_ms)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by("-response_time_ms")

    def stats(self, hours=24, tenant=None) -> dict:
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(hours=hours)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            "total": qs.count(),
            "errors": qs.filter(status_code__gte=400).count(),
            "avg_response_ms": round(qs.aggregate(a=Avg("response_time_ms"))["a"] or 0, 1),
            "by_endpoint": list(
                qs.values("endpoint").annotate(n=Count("id")).order_by("-n")[:10]
            ),
        }

    def cleanup_old(self, days=30) -> int:
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = self.filter(created_at__lt=cutoff).delete()
        return deleted
