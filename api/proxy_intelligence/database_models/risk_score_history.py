"""Risk Score History model helpers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class RiskScoreHistoryManager(models.Manager):
    def for_user(self, user, days: int = 30):
        since = timezone.now() - timedelta(days=days)
        return self.filter(
            user=user, created_at__gte=since
        ).order_by('-created_at')

    def increasing_risk(self, min_delta: int = 10, tenant=None):
        qs = self.filter(score_delta__gte=min_delta)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-score_delta')

    def decreasing_risk(self, min_drop: int = 10, tenant=None):
        qs = self.filter(score_delta__lte=-min_drop)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('score_delta')

    def recent_spikes(self, hours: int = 6, min_delta: int = 20):
        since = timezone.now() - timedelta(hours=hours)
        return self.filter(
            created_at__gte=since,
            score_delta__gte=min_delta
        ).order_by('-score_delta')

    def trend(self, user, days: int = 30) -> list:
        """Daily average risk score trend for a user."""
        from django.db.models.functions import TruncDay
        from django.db.models import Avg
        since = timezone.now() - timedelta(days=days)
        return list(
            self.filter(user=user, created_at__gte=since)
            .annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(avg_score=Avg('new_score'), avg_delta=Avg('score_delta'))
            .order_by('day')
        )

    def get_triggered_by(self, trigger: str, days: int = 30, tenant=None):
        since = timezone.now() - timedelta(days=days)
        qs    = self.filter(triggered_by=trigger, created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def cleanup_old(self, days: int = 365) -> int:
        cutoff   = timezone.now() - timedelta(days=days)
        deleted, _ = self.filter(created_at__lt=cutoff).delete()
        return deleted
