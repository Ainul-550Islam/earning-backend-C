"""
Risk Trend Analytics
=====================
Tracks how risk scores change over time across IPs and users.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min


class RiskTrendAnalytics:
    """Analytics for risk score trends and distributions."""

    def __init__(self, tenant=None, days: int = 30):
        self.tenant = tenant
        self.days = days
        self.since = timezone.now() - timedelta(days=days)

    def ip_risk_distribution(self) -> dict:
        """Distribution of IPs across risk levels."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.all()
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return {
            'very_low': qs.filter(risk_score__lte=20).count(),
            'low': qs.filter(risk_score__gt=20, risk_score__lte=40).count(),
            'medium': qs.filter(risk_score__gt=40, risk_score__lte=60).count(),
            'high': qs.filter(risk_score__gt=60, risk_score__lte=80).count(),
            'critical': qs.filter(risk_score__gt=80).count(),
        }

    def user_risk_trend(self) -> list:
        """User risk score changes over the period."""
        from ..models import RiskScoreHistory
        from django.db.models.functions import TruncDay
        qs = RiskScoreHistory.objects.filter(created_at__gte=self.since)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        return list(
            qs.annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(
                avg_score=Avg('new_score'),
                avg_delta=Avg('score_delta'),
                count=Count('id')
            )
            .order_by('day')
        )

    def detection_stats(self) -> dict:
        """VPN/Proxy/Tor detection percentages."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.all()
        total = qs.count() or 1
        return {
            'total_ips': total,
            'vpn_pct': round(qs.filter(is_vpn=True).count() / total * 100, 1),
            'proxy_pct': round(qs.filter(is_proxy=True).count() / total * 100, 1),
            'tor_pct': round(qs.filter(is_tor=True).count() / total * 100, 1),
            'datacenter_pct': round(qs.filter(is_datacenter=True).count() / total * 100, 1),
            'clean_pct': round(
                qs.filter(is_vpn=False, is_proxy=False, is_tor=False).count() / total * 100, 1
            ),
        }

    def geo_risk_heatmap(self, limit: int = 20) -> list:
        """Countries with highest average risk scores."""
        from ..models import IPIntelligence
        return list(
            IPIntelligence.objects.exclude(country_code='')
            .values('country_code')
            .annotate(avg_risk=Avg('risk_score'), count=Count('id'))
            .filter(count__gte=5)
            .order_by('-avg_risk')[:limit]
        )

    def full_report(self) -> dict:
        return {
            'period_days': self.days,
            'ip_risk_distribution': self.ip_risk_distribution(),
            'user_risk_trend': self.user_risk_trend(),
            'detection_stats': self.detection_stats(),
            'geo_risk_heatmap': self.geo_risk_heatmap(),
            'generated_at': timezone.now().isoformat(),
        }
