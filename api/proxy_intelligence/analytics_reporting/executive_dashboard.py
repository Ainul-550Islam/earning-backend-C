"""Executive Dashboard — high-level KPI summary for business reporting."""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg

class ExecutiveDashboard:
    def __init__(self, tenant=None, days: int = 30):
        self.tenant = tenant
        self.days = days
        self.since = timezone.now() - timedelta(days=days)

    def get_kpis(self) -> dict:
        from ..models import (IPIntelligence, FraudAttempt, IPBlacklist,
                              UserRiskProfile, AnomalyDetectionLog)

        ip_qs = IPIntelligence.objects.all()
        fraud_qs = FraudAttempt.objects.filter(created_at__gte=self.since)
        if self.tenant:
            ip_qs = ip_qs.filter(tenant=self.tenant)
            fraud_qs = fraud_qs.filter(tenant=self.tenant)

        total_ips = ip_qs.count() or 1
        blocked = IPBlacklist.objects.filter(is_active=True).count()
        if self.tenant:
            blocked = IPBlacklist.objects.filter(is_active=True, tenant=self.tenant).count()

        high_risk_users = UserRiskProfile.objects.filter(is_high_risk=True)
        if self.tenant:
            high_risk_users = high_risk_users.filter(tenant=self.tenant)

        return {
            'period_days': self.days,
            'total_ips_analysed': total_ips,
            'threat_detection_rate_pct': round(
                ip_qs.filter(risk_score__gte=41).count() / total_ips * 100, 1
            ),
            'vpn_proxy_tor_pct': round(
                ip_qs.filter(
                    __import__('django.db.models',fromlist=['Q']).Q(is_vpn=True) |
                    __import__('django.db.models',fromlist=['Q']).Q(is_proxy=True) |
                    __import__('django.db.models',fromlist=['Q']).Q(is_tor=True)
                ).count() / total_ips * 100, 1
            ),
            'fraud_attempts': fraud_qs.count(),
            'confirmed_fraud': fraud_qs.filter(status='confirmed').count(),
            'blocked_ips': blocked,
            'high_risk_users': high_risk_users.count(),
            'avg_risk_score': round(
                ip_qs.aggregate(a=Avg('risk_score'))['a'] or 0, 1
            ),
            'generated_at': timezone.now().isoformat(),
        }
