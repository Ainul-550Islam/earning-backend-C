"""
Fraud Attempt Analytics
========================
Generates analytical reports on fraud attempt patterns.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q


class FraudAttemptAnalytics:
    """Analytics queries for fraud attempt data."""

    def __init__(self, tenant=None, days: int = 30):
        self.tenant = tenant
        self.days = days
        self.since = timezone.now() - timedelta(days=days)

    def _qs(self):
        from ..models import FraudAttempt
        qs = FraudAttempt.objects.filter(created_at__gte=self.since)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        return qs

    def summary(self) -> dict:
        qs = self._qs()
        return {
            'total_attempts': qs.count(),
            'confirmed_fraud': qs.filter(status='confirmed').count(),
            'false_positives': qs.filter(status='false_positive').count(),
            'pending_review': qs.filter(status='detected').count(),
            'avg_risk_score': round(qs.aggregate(avg=Avg('risk_score'))['avg'] or 0, 1),
        }

    def by_type(self) -> list:
        return list(
            self._qs()
            .values('fraud_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    def by_status(self) -> list:
        return list(
            self._qs()
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    def top_fraud_ips(self, limit: int = 10) -> list:
        return list(
            self._qs()
            .values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )

    def daily_trend(self) -> list:
        """Fraud attempts per day over the period."""
        from django.db.models.functions import TruncDay
        return list(
            self._qs()
            .annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

    def full_report(self) -> dict:
        return {
            'period_days': self.days,
            'summary': self.summary(),
            'by_type': self.by_type(),
            'by_status': self.by_status(),
            'top_fraud_ips': self.top_fraud_ips(),
            'daily_trend': self.daily_trend(),
            'generated_at': timezone.now().isoformat(),
        }
