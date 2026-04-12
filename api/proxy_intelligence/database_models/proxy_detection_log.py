"""Proxy Detection Log model helpers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ProxyDetectionLogManager(models.Manager):
    def recent(self, hours: int = 24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs    = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    def by_type(self, proxy_type: str, tenant=None):
        qs = self.filter(proxy_type=proxy_type)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def by_ip(self, ip_address: str, tenant=None, limit: int = 50):
        qs = self.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')[:limit]

    def high_confidence(self, min_confidence: float = 0.8, tenant=None):
        qs = self.filter(confidence_score__gte=min_confidence)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def anonymous_proxies(self, tenant=None):
        qs = self.filter(is_anonymous=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def elite_proxies(self, tenant=None):
        """Elite proxies don't reveal the real IP at all."""
        qs = self.filter(is_elite=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def stats(self, days: int = 30, tenant=None) -> dict:
        from django.db.models import Count, Avg
        since = timezone.now() - timedelta(days=days)
        qs    = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total':            qs.count(),
            'by_type':          list(qs.values('proxy_type').annotate(n=Count('id'))),
            'avg_confidence':   round(qs.aggregate(a=Avg('confidence_score'))['a'] or 0, 3),
            'anonymous':        qs.filter(is_anonymous=True).count(),
            'elite':            qs.filter(is_elite=True).count(),
            'confirmed':        qs.filter(confidence_score__gte=0.8).count(),
        }

    def cleanup_old(self, days: int = 90) -> int:
        cutoff   = timezone.now() - timedelta(days=days)
        deleted, _ = self.filter(created_at__lt=cutoff).delete()
        return deleted
