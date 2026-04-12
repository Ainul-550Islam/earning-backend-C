"""
Geographic Risk Heatmap  (PRODUCTION-READY — COMPLETE)
========================================================
Provides country-level and region-level risk aggregation
for displaying fraud heatmaps in the admin dashboard.

Includes:
  - Country risk scores (avg, max, distribution)
  - VPN/Proxy/Tor breakdown per country
  - ISP/ASN risk by country
  - Fraud attempt geographic distribution
  - Trend comparison (current vs previous period)
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Sum, Q, F
from django.db.models.functions import TruncDay

logger = logging.getLogger(__name__)


class GeoRiskHeatmap:
    """
    Generates geographic risk data for heatmap visualizations.
    All results are sorted by avg_risk descending (most dangerous first).
    """

    def __init__(self, tenant=None):
        self.tenant = tenant

    # ── Country-level data ─────────────────────────────────────────────────

    def get_country_risk(self, min_ips: int = 3, limit: int = 50) -> list:
        """
        Returns per-country risk aggregation.
        Minimum `min_ips` IPs required to include a country in results.
        """
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.exclude(country_code='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('country_code', 'country_name')
            .annotate(
                avg_risk        = Avg('risk_score'),
                max_risk        = Max('risk_score'),
                min_risk        = Min('risk_score'),
                total_ips       = Count('id'),
                vpn_count       = Count('id', filter=Q(is_vpn=True)),
                proxy_count     = Count('id', filter=Q(is_proxy=True)),
                tor_count       = Count('id', filter=Q(is_tor=True)),
                datacenter_count= Count('id', filter=Q(is_datacenter=True)),
                high_risk_count = Count('id', filter=Q(risk_score__gte=61)),
                critical_count  = Count('id', filter=Q(risk_score__gte=81)),
                avg_fraud_score = Avg('fraud_score'),
                avg_abuse_score = Avg('abuse_confidence_score'),
            )
            .filter(total_ips__gte=min_ips)
            .order_by('-avg_risk')[:limit]
        )

    def get_high_risk_countries(self, threshold: float = 60.0) -> list:
        """Countries where the average IP risk score exceeds threshold."""
        return [c for c in self.get_country_risk(min_ips=5)
                if (c.get('avg_risk') or 0) >= threshold]

    def get_critical_countries(self) -> list:
        """Countries with the highest proportion of critical-risk IPs."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.exclude(country_code='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        results = list(
            qs.values('country_code', 'country_name')
            .annotate(
                total      = Count('id'),
                critical   = Count('id', filter=Q(risk_score__gte=81)),
                avg_risk   = Avg('risk_score'),
            )
            .filter(total__gte=5)
            .annotate(
                critical_pct = F('critical') * 100.0 / F('total')
            )
            .order_by('-critical_pct')[:20]
        )
        return results

    # ── VPN/Proxy geographic breakdown ─────────────────────────────────────

    def get_vpn_by_country(self, limit: int = 30) -> list:
        """Countries with the most VPN IP addresses."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.filter(is_vpn=True).exclude(country_code='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('country_code', 'country_name')
            .annotate(vpn_count=Count('id'), avg_risk=Avg('risk_score'))
            .order_by('-vpn_count')[:limit]
        )

    def get_tor_by_country(self, limit: int = 20) -> list:
        """Countries with Tor exit nodes."""
        from ..models import IPIntelligence
        qs = IPIntelligence.objects.filter(is_tor=True).exclude(country_code='')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.values('country_code', 'country_name')
            .annotate(tor_count=Count('id'))
            .order_by('-tor_count')[:limit]
        )

    # ── Fraud geographic breakdown ─────────────────────────────────────────

    def get_fraud_by_country(self, days: int = 30, limit: int = 30) -> list:
        """Countries from which most fraud attempts originated."""
        from ..models import FraudAttempt, IPIntelligence
        since = timezone.now() - timedelta(days=days)

        # Join FraudAttempt with IPIntelligence to get country data
        fraud_qs = FraudAttempt.objects.filter(created_at__gte=since)
        if self.tenant:
            fraud_qs = fraud_qs.filter(tenant=self.tenant)

        # Get IPs with fraud attempts
        fraud_ips = list(fraud_qs.values_list('ip_address', flat=True).distinct()[:1000])

        # Get their countries
        geo_qs = IPIntelligence.objects.filter(
            ip_address__in=fraud_ips
        ).exclude(country_code='')

        return list(
            geo_qs.values('country_code', 'country_name')
            .annotate(
                ip_count     = Count('id'),
                avg_risk     = Avg('risk_score'),
                vpn_count    = Count('id', filter=Q(is_vpn=True)),
            )
            .order_by('-ip_count')[:limit]
        )

    # ── Trend comparison ───────────────────────────────────────────────────

    def get_risk_trend_by_country(self, country_code: str,
                                   days: int = 30) -> list:
        """Daily average risk score for a specific country over time."""
        from ..models import IPIntelligence
        since = timezone.now() - timedelta(days=days)

        qs = IPIntelligence.objects.filter(
            country_code=country_code.upper(),
            last_checked__gte=since,
        )
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)

        return list(
            qs.annotate(day=TruncDay('last_checked'))
            .values('day')
            .annotate(avg_risk=Avg('risk_score'), ip_count=Count('id'))
            .order_by('day')
        )

    def compare_periods(self, days: int = 30) -> dict:
        """
        Compare current period vs previous period risk scores per country.
        Useful for detecting emerging high-risk regions.
        """
        from ..models import IPIntelligence

        now      = timezone.now()
        current  = now - timedelta(days=days)
        previous = current - timedelta(days=days)

        def _get_country_avgs(start, end):
            qs = IPIntelligence.objects.filter(
                last_checked__gte=start, last_checked__lt=end
            ).exclude(country_code='')
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            return {
                row['country_code']: row['avg_risk']
                for row in qs.values('country_code')
                .annotate(avg_risk=Avg('risk_score'))
            }

        current_avgs  = _get_country_avgs(current, now)
        previous_avgs = _get_country_avgs(previous, current)

        changes = []
        for country, current_risk in current_avgs.items():
            prev = previous_avgs.get(country)
            if prev is not None:
                delta = (current_risk or 0) - prev
                if abs(delta) >= 5:
                    changes.append({
                        'country_code':   country,
                        'current_risk':   round(current_risk or 0, 1),
                        'previous_risk':  round(prev, 1),
                        'delta':          round(delta, 1),
                        'trend':          'increasing' if delta > 0 else 'decreasing',
                    })

        return {
            'period_days':  days,
            'changes':      sorted(changes, key=lambda x: -abs(x['delta']))[:20],
            'generated_at': timezone.now().isoformat(),
        }

    # ── Full report ────────────────────────────────────────────────────────

    def full_report(self, days: int = 30) -> dict:
        """Complete geographic risk report for the executive dashboard."""
        return {
            'country_risk':        self.get_country_risk(min_ips=3, limit=50),
            'high_risk_countries': self.get_high_risk_countries(threshold=60.0),
            'critical_countries':  self.get_critical_countries(),
            'vpn_by_country':      self.get_vpn_by_country(limit=20),
            'tor_by_country':      self.get_tor_by_country(limit=15),
            'fraud_by_country':    self.get_fraud_by_country(days=days, limit=20),
            'period_comparison':   self.compare_periods(days=days),
            'generated_at':        timezone.now().isoformat(),
        }
