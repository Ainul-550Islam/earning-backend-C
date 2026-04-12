"""IP Blacklist model helpers and managers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class IPBlacklistManager(models.Manager):
    def active(self, tenant=None):
        qs = self.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def permanent(self, tenant=None):
        return self.active(tenant).filter(is_permanent=True)

    def temporary(self, tenant=None):
        return self.active(tenant).filter(is_permanent=False)

    def expired(self):
        return self.filter(
            is_active=True, is_permanent=False,
            expires_at__lt=timezone.now()
        )

    def expiring_soon(self, hours: int = 24, tenant=None):
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.active(tenant).filter(
            is_permanent=False,
            expires_at__lte=cutoff,
            expires_at__gte=timezone.now()
        )

    def by_reason(self, reason: str, tenant=None):
        return self.active(tenant).filter(reason=reason)

    def by_source(self, source: str, tenant=None):
        return self.active(tenant).filter(source=source)

    def bulk_deactivate(self, ip_list: list, tenant=None) -> int:
        qs = self.filter(ip_address__in=ip_list)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.update(is_active=False)

    def deactivate_expired(self) -> int:
        count = self.expired().count()
        self.expired().update(is_active=False)
        return count

    def search(self, query: str, tenant=None):
        from django.db.models import Q
        qs = self.active(tenant).filter(
            Q(ip_address__icontains=query) |
            Q(description__icontains=query) |
            Q(source__icontains=query)
        )
        return qs

    def stats(self, tenant=None) -> dict:
        from django.db.models import Count
        qs = self.active(tenant)
        return {
            'total_active': qs.count(),
            'permanent':    self.permanent(tenant).count(),
            'temporary':    self.temporary(tenant).count(),
            'by_reason':    list(qs.values('reason').annotate(n=Count('id')).order_by('-n')),
            'by_source':    list(qs.values('source').annotate(n=Count('id')).order_by('-n')),
            'expiring_24h': self.expiring_soon(24, tenant).count(),
        }
