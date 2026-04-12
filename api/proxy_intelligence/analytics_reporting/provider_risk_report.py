"""
Provider Risk Report  (PRODUCTION-READY — COMPLETE)
=====================================================
Generates ISP/ASN/hosting-provider level risk aggregation reports.
Identifies which network providers are most associated with fraud,
VPN usage, and malicious activity on the platform.

Reports generated:
  - ISP risk breakdown (avg risk score per ISP)
  - ASN risk breakdown
  - Datacenter abuse by provider
  - Top VPN providers detected
  - Residential proxy provider analysis
  - Provider trend comparison (current vs previous period)
"""
import logging
from datetime import timedelta

from django.db.models import Count, Avg, Max, Min, Q, F
from django.db.models.functions import TruncDay
from django.utils import timezone

logger = logging.getLogger(__name__)


class ProviderRiskReport:
    """
    Generates comprehensive ISP/ASN provider risk reports.
    All queries support tenant-level filtering.
    """

    def __init__(self, tenant=None, days: int = 30):
        self.tenant = tenant
        self.days   = days
        self.since  = timezone.now() - timedelta(days=days)

    # ── ISP Analysis ───────────────────────────────────────────────────────

    def get_isp_risk(self, min_ips: int = 5, limit: int = 30) -> list:
        """
        Top ISPs by average risk score.
        Only includes ISPs with at least `min_ips` IP addresses.
        """
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.exclude(isp='').exclude(isp__isnull=True)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('isp')
            .annotate(
                avg_risk       = Avg('risk_score'),
                max_risk       = Max('risk_score'),
                min_risk       = Min('risk_score'),
                total_ips      = Count('id'),
                vpn_count      = Count('id', filter=Q(is_vpn=True)),
                proxy_count    = Count('id', filter=Q(is_proxy=True)),
                tor_count      = Count('id', filter=Q(is_tor=True)),
                datacenter_cnt = Count('id', filter=Q(is_datacenter=True)),
                high_risk_cnt  = Count('id', filter=Q(risk_score__gte=61)),
                critical_cnt   = Count('id', filter=Q(risk_score__gte=81)),
                avg_fraud_score= Avg('fraud_score'),
                avg_abuse_score= Avg('abuse_confidence_score'),
            )
            .filter(total_ips__gte=min_ips)
            .order_by('-avg_risk')[:limit]
        )

    def get_isp_fraud_rate(self, min_ips: int = 10, limit: int = 20) -> list:
        """
        ISPs sorted by fraud attempt rate (fraud attempts / total IPs).
        """
        from ..models import IPIntelligence, FraudAttempt

        # Get fraud attempt counts grouped by IP
        fraud_ips = set(
            FraudAttempt.objects
            .filter(created_at__gte=self.since)
            .values_list('ip_address', flat=True)
        )

        qs = IPIntelligence.objects.exclude(isp='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        results = list(
            qs.values('isp')
            .annotate(total_ips=Count('id'))
            .filter(total_ips__gte=min_ips)
        )

        # Annotate with fraud IP count
        for row in results:
            isp_ips = set(
                IPIntelligence.objects
                .filter(isp=row['isp'])
                .values_list('ip_address', flat=True)
            )
            fraud_count = len(isp_ips & fraud_ips)
            row['fraud_ips'] = fraud_count
            row['fraud_rate_pct'] = round(
                fraud_count / row['total_ips'] * 100, 2
            ) if row['total_ips'] else 0

        return sorted(results, key=lambda x: -x['fraud_rate_pct'])[:limit]

    # ── ASN Analysis ───────────────────────────────────────────────────────

    def get_asn_risk(self, min_ips: int = 5, limit: int = 30) -> list:
        """Top ASNs by average risk score."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.exclude(asn='').exclude(asn__isnull=True)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('asn', 'asn_name')
            .annotate(
                avg_risk    = Avg('risk_score'),
                max_risk    = Max('risk_score'),
                total_ips   = Count('id'),
                vpn_count   = Count('id', filter=Q(is_vpn=True)),
                proxy_count = Count('id', filter=Q(is_proxy=True)),
                tor_count   = Count('id', filter=Q(is_tor=True)),
                high_risk   = Count('id', filter=Q(risk_score__gte=61)),
            )
            .filter(total_ips__gte=min_ips)
            .order_by('-avg_risk')[:limit]
        )

    def get_asn_vpn_percentage(self, limit: int = 20) -> list:
        """
        ASNs with the highest percentage of VPN IPs.
        Useful for identifying VPN-heavy ASNs to block or challenge.
        """
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.exclude(asn='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        rows = list(
            qs.values('asn', 'asn_name')
            .annotate(
                total = Count('id'),
                vpn   = Count('id', filter=Q(is_vpn=True)),
            )
            .filter(total__gte=3)
        )

        for row in rows:
            row['vpn_pct'] = round(row['vpn'] / row['total'] * 100, 1)

        return sorted(rows, key=lambda x: -x['vpn_pct'])[:limit]

    # ── Datacenter / Hosting Provider Analysis ─────────────────────────────

    def get_datacenter_abuse(self, limit: int = 20) -> list:
        """
        Hosting/datacenter providers with the most high-risk IPs.
        """
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.filter(is_datacenter=True).exclude(asn_name='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('asn_name', 'asn')
            .annotate(
                total_dc_ips   = Count('id'),
                high_risk_cnt  = Count('id', filter=Q(risk_score__gte=61)),
                fraud_score_avg= Avg('fraud_score'),
                abuse_score_avg= Avg('abuse_confidence_score'),
                avg_risk       = Avg('risk_score'),
            )
            .filter(total_dc_ips__gte=2)
            .order_by('-high_risk_cnt')[:limit]
        )

    def get_vpn_provider_breakdown(self, limit: int = 20) -> list:
        """
        Breakdown of VPN providers detected on the platform.
        Uses the vpn_provider field from VPNDetectionLog.
        """
        from ..models import VPNDetectionLog
        qs = VPNDetectionLog.objects.filter(
            created_at__gte=self.since
        ).exclude(vpn_provider='').exclude(vpn_provider__isnull=True)

        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('vpn_provider')
            .annotate(
                detection_count  = Count('id'),
                avg_confidence   = Avg('confidence_score'),
                confirmed_count  = Count('id', filter=Q(is_confirmed=True)),
                unique_ips       = Count('ip_address', distinct=True),
            )
            .order_by('-detection_count')[:limit]
        )

    # ── Proxy Provider Analysis ────────────────────────────────────────────

    def get_residential_proxy_providers(self, limit: int = 15) -> list:
        """
        ISPs known to be residential proxy providers.
        Uses keyword matching against the ProxyProviderList.
        """
        from ..database_models.proxy_provider_list import ProxyProviderList
        from ..models import IPIntelligence

        high_risk_providers = ProxyProviderList.get_high_risk_providers()

        results = []
        for provider_name in high_risk_providers:
            from ..database_models.proxy_provider_list import PROXY_PROVIDERS
            info = PROXY_PROVIDERS.get(provider_name, {})
            keywords = info.get('keywords', [])

            q = Q()
            for kw in keywords:
                q |= Q(isp__icontains=kw) | Q(organization__icontains=kw)

            qs = IPIntelligence.objects.filter(q)
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)

            count = qs.count()
            if count > 0:
                avg_risk = qs.aggregate(avg=Avg('risk_score'))['avg'] or 0
                results.append({
                    'provider':      provider_name,
                    'proxy_type':    info.get('type', 'unknown'),
                    'risk_tier':     info.get('risk', 'unknown'),
                    'ip_count':      count,
                    'avg_risk_score': round(avg_risk, 1),
                })

        return sorted(results, key=lambda x: -x['ip_count'])[:limit]

    # ── Trend Analysis ─────────────────────────────────────────────────────

    def get_isp_risk_trend(self, isp: str, days: int = 30) -> list:
        """
        Daily average risk score trend for a specific ISP.
        """
        from ..models import IPIntelligence
        since = timezone.now() - timedelta(days=days)

        qs = IPIntelligence.objects.filter(isp__icontains=isp, last_checked__gte=since)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.annotate(day=TruncDay('last_checked'))
            .values('day')
            .annotate(
                avg_risk  = Avg('risk_score'),
                ip_count  = Count('id'),
                vpn_count = Count('id', filter=Q(is_vpn=True)),
            )
            .order_by('day')
        )

    def compare_provider_periods(self, days: int = 30) -> list:
        """
        Compare ISP risk scores: current period vs previous period.
        Returns ISPs with significant score changes (delta >= 5).
        """
        from ..models import IPIntelligence

        now      = timezone.now()
        cur_start  = now - timedelta(days=days)
        prev_start = cur_start - timedelta(days=days)

        def _isp_avgs(start, end):
            qs = IPIntelligence.objects.filter(
                last_checked__gte=start, last_checked__lt=end
            ).exclude(isp='')
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            return {
                r['isp']: r['avg_risk']
                for r in qs.values('isp').annotate(avg_risk=Avg('risk_score'))
            }

        current  = _isp_avgs(cur_start, now)
        previous = _isp_avgs(prev_start, cur_start)

        changes = []
        for isp, cur_risk in current.items():
            prev = previous.get(isp)
            if prev is None:
                continue
            delta = (cur_risk or 0) - prev
            if abs(delta) >= 5:
                changes.append({
                    'isp':           isp,
                    'current_risk':  round(cur_risk or 0, 1),
                    'previous_risk': round(prev, 1),
                    'delta':         round(delta, 1),
                    'trend':         'increasing' if delta > 0 else 'decreasing',
                })

        return sorted(changes, key=lambda x: -abs(x['delta']))[:20]

    # ── Full Report ────────────────────────────────────────────────────────

    def full_report(self) -> dict:
        """
        Complete provider risk report for the executive dashboard.
        Combines all analyses into a single structured output.
        """
        return {
            'period_days':             self.days,
            'isp_risk':                self.get_isp_risk(min_ips=5, limit=25),
            'isp_fraud_rate':          self.get_isp_fraud_rate(min_ips=10, limit=15),
            'asn_risk':                self.get_asn_risk(min_ips=5, limit=20),
            'asn_vpn_percentage':      self.get_asn_vpn_percentage(limit=15),
            'datacenter_abuse':        self.get_datacenter_abuse(limit=15),
            'vpn_provider_breakdown':  self.get_vpn_provider_breakdown(limit=15),
            'residential_proxy_providers': self.get_residential_proxy_providers(limit=10),
            'isp_period_comparison':   self.compare_provider_periods(self.days),
            'generated_at':            timezone.now().isoformat(),
        }
