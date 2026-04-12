# api/publisher_tools/mediation_management/mediation_manager.py
"""
Mediation Manager — Advanced mediation & waterfall management।
Auto-optimization, A/B testing, floor price management।
"""
from decimal import Decimal
from datetime import timedelta
from typing import List, Dict, Optional
from django.db import models, transaction
from django.db.models import Sum, Avg, F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class MediationConfig(TimeStampedModel):
    """
    Global mediation configuration settings।
    Platform-wide mediation rules ও defaults।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_mediationconfig_tenant', db_index=True,
    )

    # ── Ad Request Settings ───────────────────────────────────────────────────
    max_concurrent_requests   = models.IntegerField(default=5, verbose_name=_("Max Concurrent Ad Requests"))
    global_timeout_ms         = models.IntegerField(default=3000, verbose_name=_("Global Timeout (ms)"))
    no_fill_fallback_enabled  = models.BooleanField(default=True, verbose_name=_("Enable No-Fill Fallback"))
    fallback_ad_url           = models.URLField(blank=True, verbose_name=_("Fallback Ad URL"))

    # ── Optimization Settings ─────────────────────────────────────────────────
    auto_optimization_enabled = models.BooleanField(default=True)
    optimization_interval_hours = models.IntegerField(default=24)
    min_impressions_for_optimization = models.IntegerField(
        default=1000,
        verbose_name=_("Min Impressions for Optimization"),
        help_text=_("এত impressions না হলে optimize করবে না"),
    )
    ecpm_weight      = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.70'), verbose_name=_("eCPM Weight"))
    fill_rate_weight = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.20'), verbose_name=_("Fill Rate Weight"))
    latency_weight   = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.10'), verbose_name=_("Latency Weight"))

    # ── Floor Price Management ─────────────────────────────────────────────────
    dynamic_floor_prices_enabled = models.BooleanField(default=False)
    floor_price_update_interval  = models.IntegerField(default=6, verbose_name=_("Floor Price Update Interval (hours)"))
    min_global_floor_price       = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.1000'), verbose_name=_("Min Global Floor Price (USD CPM)"))

    # ── Header Bidding ────────────────────────────────────────────────────────
    header_bidding_enabled     = models.BooleanField(default=False)
    prebid_timeout_ms          = models.IntegerField(default=1000)
    prebid_price_granularity   = models.CharField(
        max_length=20,
        choices=[
            ('low',    'Low ($0.50 increments)'),
            ('medium', 'Medium ($0.10 increments)'),
            ('high',   'High ($0.01 increments)'),
            ('auto',   'Auto'),
            ('dense',  'Dense'),
        ],
        default='medium',
    )

    # ── Network Defaults ──────────────────────────────────────────────────────
    default_bid_timeout_ms = models.IntegerField(default=2000)
    retry_on_timeout       = models.BooleanField(default=False)
    max_retry_count        = models.IntegerField(default=1)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'publisher_tools_mediation_configs'
        verbose_name = _('Mediation Config')
        verbose_name_plural = _('Mediation Configs')

    def __str__(self):
        return f"Mediation Config — {self.tenant}"


class NetworkPerformanceSnapshot(TimeStampedModel):
    """
    Ad Network-এর daily performance snapshot।
    Waterfall optimization-এর জন্য historical data।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_networkperf_tenant', db_index=True,
    )

    network = models.ForeignKey(
        'ad_networks.AdNetwork',
        on_delete=models.CASCADE,
        related_name='performance_snapshots',
        verbose_name=_("Ad Network"),
        db_index=True,
    )
    ad_unit = models.ForeignKey(
        'publisher_tools.AdUnit',
        on_delete=models.CASCADE,
        related_name='network_performance_snapshots',
        verbose_name=_("Ad Unit"),
        db_index=True,
    )
    date = models.DateField(verbose_name=_("Date"), db_index=True)

    # ── Performance Metrics ────────────────────────────────────────────────────
    ad_requests  = models.BigIntegerField(default=0)
    impressions  = models.BigIntegerField(default=0)
    clicks       = models.BigIntegerField(default=0)
    revenue      = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0.000000'))
    fill_rate    = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    ecpm         = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    ctr          = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    avg_latency_ms = models.IntegerField(default=0)
    timeout_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    error_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # ── Bid Statistics ────────────────────────────────────────────────────────
    bid_requests  = models.BigIntegerField(default=0, verbose_name=_("Bid Requests Sent"))
    bid_responses = models.BigIntegerField(default=0, verbose_name=_("Bid Responses Received"))
    bid_wins      = models.BigIntegerField(default=0, verbose_name=_("Bid Wins"))
    avg_bid_price = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    win_rate      = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'publisher_tools_network_performance_snapshots'
        verbose_name = _('Network Performance Snapshot')
        verbose_name_plural = _('Network Performance Snapshots')
        unique_together = [['network', 'ad_unit', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['network', 'ad_unit', 'date']),
            models.Index(fields=['ecpm']),
        ]

    def __str__(self):
        return f"{self.network.name} — {self.ad_unit.unit_id} — {self.date} — eCPM: ${self.ecpm}"


def calculate_network_composite_score(
    ecpm: float,
    fill_rate: float,
    avg_latency_ms: int,
    weights: Dict = None,
) -> float:
    """
    Ad Network-এর composite performance score calculate করে।
    Waterfall ordering-এর জন্য।
    """
    if weights is None:
        weights = {'ecpm': 0.70, 'fill_rate': 0.20, 'latency': 0.10}

    # Normalize latency (lower = better, max 3000ms)
    max_latency = 3000
    latency_score = max(0, 100 - (avg_latency_ms / max_latency * 100))

    # Normalize eCPM (assume max $10 CPM for normalization)
    max_ecpm = 10.0
    ecpm_score = min(100, (ecpm / max_ecpm) * 100)

    composite = (
        ecpm_score    * weights.get('ecpm', 0.70) +
        fill_rate     * weights.get('fill_rate', 0.20) +
        latency_score * weights.get('latency', 0.10)
    )
    return round(composite, 2)


def get_optimal_waterfall_order(group) -> List[Dict]:
    """
    Mediation group-এর optimal waterfall order calculate করে।
    Historical performance data-র ভিত্তিতে।
    """
    from ..models import WaterfallItem

    items = WaterfallItem.objects.filter(
        mediation_group=group, status='active'
    ).select_related('network')

    scored_items = []
    for item in items:
        score = calculate_network_composite_score(
            ecpm=float(item.avg_ecpm),
            fill_rate=float(item.fill_rate),
            avg_latency_ms=item.avg_latency_ms,
        )
        scored_items.append({
            'item_id':         str(item.id),
            'network_name':    item.network.name,
            'current_priority': item.priority,
            'avg_ecpm':        float(item.avg_ecpm),
            'fill_rate':       float(item.fill_rate),
            'avg_latency_ms':  item.avg_latency_ms,
            'composite_score': score,
            'floor_ecpm':      float(item.floor_ecpm),
        })

    # Sort by composite score descending
    scored_items.sort(key=lambda x: x['composite_score'], reverse=True)

    # Assign optimal priorities
    for i, item_data in enumerate(scored_items, start=1):
        item_data['optimal_priority'] = i
        item_data['needs_reorder'] = item_data['current_priority'] != i

    return scored_items


def analyze_mediation_performance(group, days: int = 30) -> Dict:
    """
    Mediation group-এর performance analysis।
    Problems identify করে এবং recommendations দেয়।
    """
    from ..models import WaterfallItem

    start = timezone.now().date() - timedelta(days=days)

    items = WaterfallItem.objects.filter(
        mediation_group=group, status='active'
    ).select_related('network')

    analysis = {
        'group_id': str(group.id),
        'group_name': group.name,
        'period_days': days,
        'networks': [],
        'issues': [],
        'recommendations': [],
        'overall_fill_rate': float(group.fill_rate),
        'overall_ecpm': float(group.avg_ecpm),
        'total_revenue': float(group.total_revenue),
    }

    for item in items:
        network_data = {
            'network': item.network.name,
            'priority': item.priority,
            'ecpm': float(item.avg_ecpm),
            'fill_rate': float(item.fill_rate),
            'latency_ms': item.avg_latency_ms,
            'revenue': float(item.total_revenue),
            'requests': item.total_ad_requests,
        }

        # Issues
        if float(item.fill_rate) < 10 and item.total_ad_requests > 1000:
            analysis['issues'].append({
                'type': 'low_fill_rate',
                'network': item.network.name,
                'severity': 'high',
                'message': f'{item.network.name} has {item.fill_rate:.1f}% fill rate — consider removing',
            })

        if item.avg_latency_ms > 1500:
            analysis['issues'].append({
                'type': 'high_latency',
                'network': item.network.name,
                'severity': 'medium',
                'message': f'{item.network.name} latency {item.avg_latency_ms}ms is too high',
            })

        analysis['networks'].append(network_data)

    # Check if waterfall is eCPM-sorted
    ecpms = [float(item.avg_ecpm) for item in items if item.avg_ecpm > 0]
    if ecpms != sorted(ecpms, reverse=True):
        analysis['recommendations'].append({
            'type': 'optimize_waterfall',
            'priority': 'high',
            'message': 'Waterfall is not sorted by eCPM. Run auto-optimization to fix.',
        })

    # Check network count
    if items.count() < 2:
        analysis['recommendations'].append({
            'type': 'add_networks',
            'priority': 'high',
            'message': 'Add at least 2-3 more ad networks to improve competition and fill rate.',
        })

    # Header bidding suggestion
    if group.mediation_type == 'waterfall':
        analysis['recommendations'].append({
            'type': 'enable_header_bidding',
            'priority': 'medium',
            'message': 'Switching to hybrid mediation with header bidding can increase eCPM by 20-40%.',
        })

    return analysis
