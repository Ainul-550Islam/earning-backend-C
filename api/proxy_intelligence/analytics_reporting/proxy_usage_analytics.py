"""Proxy Usage Analytics — trends in VPN/proxy/Tor usage."""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg
from django.db.models.functions import TruncDay

class ProxyUsageAnalytics:
    def __init__(self, tenant=None, days: int = 30):
        self.tenant = tenant
        self.since = timezone.now() - timedelta(days=days)
        self.days = days

    def _qs(self):
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.filter(last_checked__gte=self.since)
        if self.tenant: qs = qs.filter(tenant=self.tenant)
        return qs

    def summary(self) -> dict:
        qs = self._qs()
        total = qs.count() or 1
        return {
            'total_ips': total,
            'vpn_count': qs.filter(is_vpn=True).count(),
            'proxy_count': qs.filter(is_proxy=True).count(),
            'tor_count': qs.filter(is_tor=True).count(),
            'datacenter_count': qs.filter(is_datacenter=True).count(),
            'vpn_pct': round(qs.filter(is_vpn=True).count()/total*100,1),
            'proxy_pct': round(qs.filter(is_proxy=True).count()/total*100,1),
            'tor_pct': round(qs.filter(is_tor=True).count()/total*100,1),
        }

    def daily_trend(self) -> list:
        return list(
            self._qs()
            .annotate(day=TruncDay('last_checked'))
            .values('day')
            .annotate(
                total=Count('id'),
                vpn=Count('id', filter=__import__('django.db.models',fromlist=['Q']).Q(is_vpn=True)),
                proxy=Count('id', filter=__import__('django.db.models',fromlist=['Q']).Q(is_proxy=True)),
                tor=Count('id', filter=__import__('django.db.models',fromlist=['Q']).Q(is_tor=True)),
            )
            .order_by('day')
        )

    def top_vpn_providers(self, limit: int = 10) -> list:
        from ..models import VPNDetectionLog
        qs = VPNDetectionLog.objects.filter(created_at__gte=self.since).exclude(vpn_provider='')
        if self.tenant: qs = qs.filter(tenant=self.tenant)
        return list(qs.values('vpn_provider').annotate(count=Count('id')).order_by('-count')[:limit])
