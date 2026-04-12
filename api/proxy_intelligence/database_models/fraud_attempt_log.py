"""Fraud Attempt Log — model helpers and querysets."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class FraudAttemptManager(models.Manager):
    def pending(self, tenant=None):
        qs = self.filter(status='detected')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score', '-created_at')

    def confirmed(self, tenant=None):
        qs = self.filter(status='confirmed')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def high_risk(self, threshold=70, tenant=None):
        qs = self.filter(risk_score__gte=threshold)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-risk_score')

    def by_ip(self, ip_address, tenant=None):
        qs = self.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    def by_user(self, user, limit=50):
        return self.filter(user=user).order_by('-created_at')[:limit]

    def recent(self, hours=24, tenant=None):
        since = timezone.now() - timedelta(hours=hours)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def stats(self, days=30, tenant=None):
        from django.db.models import Count, Avg
        since = timezone.now() - timedelta(days=days)
        qs = self.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total': qs.count(),
            'confirmed': qs.filter(status='confirmed').count(),
            'false_positives': qs.filter(status='false_positive').count(),
            'by_type': list(qs.values('fraud_type').annotate(n=Count('id')).order_by('-n')),
            'avg_risk': round(qs.aggregate(a=Avg('risk_score'))['a'] or 0, 1),
        }
