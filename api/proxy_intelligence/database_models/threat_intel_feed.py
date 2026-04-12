"""Threat Intel Feed model helpers for feed management."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ThreatFeedProviderManager(models.Manager):
    def active(self):
        return self.filter(is_active=True).order_by('priority')

    def with_quota_remaining(self):
        from django.db.models import F
        return self.active().filter(used_today__lt=F('daily_quota'))

    def over_quota(self):
        from django.db.models import F
        return self.active().filter(used_today__gte=F('daily_quota'))

    def by_priority(self):
        return self.active().order_by('priority')

    def reset_daily_quotas(self) -> int:
        return self.all().update(used_today=0)

    def record_usage(self, feed_name: str, count: int = 1):
        self.filter(name=feed_name).update(
            used_today=models.F('used_today') + count,
            last_sync=timezone.now(),
        )

    def needs_sync(self, hours: int = 6):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.active().filter(
            models.Q(last_sync__lt=cutoff) | models.Q(last_sync__isnull=True)
        )

    def recently_synced(self, hours: int = 1):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.active().filter(last_sync__gte=cutoff)

    def get_by_name(self, name: str):
        return self.filter(name=name).first()

    def stats(self) -> dict:
        from django.db.models import Sum, Count
        qs = self.all()
        return {
            'total':        qs.count(),
            'active':       qs.filter(is_active=True).count(),
            'total_entries': qs.aggregate(s=Sum('total_entries'))['s'] or 0,
            'over_quota':   self.over_quota().count(),
            'needs_sync':   self.needs_sync().count(),
        }
