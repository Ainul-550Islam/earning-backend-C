# api/publisher_tools/performance_analytics/publisher_dashboard.py
"""
Publisher Dashboard — Real-time dashboard data aggregation।
সব key metrics একজায়গায় aggregate করে।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
from django.db.models import Sum, Avg, Count, Q, Max
from django.utils import timezone
from django.core.cache import cache


def get_realtime_stats(publisher) -> Dict:
    """
    Real-time stats (last 1 hour)।
    Live dashboard-এ দেখানোর জন্য।
    """
    from ..models import PublisherEarning, TrafficSafetyLog

    cache_key = f'realtime_stats:{publisher.publisher_id}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    now   = timezone.now()
    start = now - timedelta(hours=1)
    today = now.date()

    # Today's earnings (estimated)
    today_earnings = PublisherEarning.objects.filter(
        publisher=publisher,
        date=today,
    ).aggregate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
    )

    # IVT in last hour
    ivt_count = TrafficSafetyLog.objects.filter(
        publisher=publisher,
        detected_at__gte=start,
        is_false_positive=False,
    ).count()

    # Active ad units
    from ..models import AdUnit
    active_units = AdUnit.objects.filter(
        publisher=publisher, status='active'
    ).count()

    result = {
        'timestamp':        now.isoformat(),
        'today_revenue':    float(today_earnings.get('revenue') or 0),
        'today_impressions': today_earnings.get('impressions') or 0,
        'today_clicks':     today_earnings.get('clicks') or 0,
        'ivt_alerts_1h':   ivt_count,
        'active_ad_units':  active_units,
        'account_status':   publisher.status,
    }

    cache.set(cache_key, result, 60)  # 1 minute cache
    return result


def get_dashboard_summary(publisher, period: str = 'last_30_days') -> Dict:
    """
    Complete dashboard summary।
    Overview widget-গুলোর জন্য।
    """
    from ..models import PublisherEarning, Site, App, AdUnit, TrafficSafetyLog

    from ...utils import get_date_range, calculate_ecpm
    start_date, end_date = get_date_range(period)

    # Current period
    curr = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
    ).aggregate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
        requests=Sum('ad_requests'),
        ivt_deduction=Sum('invalid_traffic_deduction'),
    )

    # Previous period comparison
    days_count = (end_date - start_date).days + 1
    prev_end   = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days_count - 1)

    prev = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[prev_start, prev_end],
    ).aggregate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    )

    curr_rev = curr.get('revenue') or Decimal('0')
    prev_rev = prev.get('revenue') or Decimal('0')
    impressions = curr.get('impressions') or 0
    clicks      = curr.get('clicks') or 0
    requests    = curr.get('requests') or 0

    def change_pct(c, p):
        c, p = float(c), float(p)
        if p == 0: return 100.0 if c > 0 else 0.0
        return round((c - p) / p * 100, 2)

    # Inventory
    sites = Site.objects.filter(publisher=publisher)
    apps  = App.objects.filter(publisher=publisher)
    units = AdUnit.objects.filter(publisher=publisher)

    # IVT
    ivt_logs = TrafficSafetyLog.objects.filter(
        publisher=publisher,
        detected_at__date__range=[start_date, end_date],
        is_false_positive=False,
    )

    # Top sites by revenue
    top_sites = list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
            site__isnull=False,
        ).values('site__site_id', 'site__name', 'site__domain').annotate(
            revenue=Sum('publisher_revenue')
        ).order_by('-revenue')[:5]
    )

    # Revenue by day (chart data)
    daily_chart = list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
            granularity='daily',
        ).values('date').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
        ).order_by('date')
    )

    return {
        'period': {
            'label':    period,
            'start':    str(start_date),
            'end':      str(end_date),
            'days':     days_count,
        },
        'revenue_widget': {
            'current':         float(curr_rev),
            'previous':        float(prev_rev),
            'change_pct':      change_pct(curr_rev, prev_rev),
            'is_growth':       curr_rev >= prev_rev,
            'gross':           float(curr.get('revenue') or 0),
            'ivt_deduction':   float(curr.get('ivt_deduction') or 0),
            'formatted':       f"${float(curr_rev):,.2f}",
        },
        'traffic_widget': {
            'impressions':     impressions,
            'prev_impressions': prev.get('impressions') or 0,
            'change_pct':      change_pct(impressions, prev.get('impressions') or 0),
            'clicks':          clicks,
            'fill_rate':       round((impressions / requests * 100) if requests > 0 else 0, 2),
            'ecpm':            float(calculate_ecpm(curr_rev, impressions)),
            'ctr':             round((clicks / impressions * 100) if impressions > 0 else 0, 4),
        },
        'account_widget': {
            'total_revenue':   float(publisher.total_revenue),
            'total_paid_out':  float(publisher.total_paid_out),
            'pending':         float(publisher.pending_balance),
            'available':       float(publisher.available_balance),
            'status':          publisher.status,
            'tier':            publisher.tier,
            'tier_icon':       {'standard': '🥉', 'premium': '🥈', 'enterprise': '🏆'}.get(publisher.tier, '⭐'),
        },
        'inventory_widget': {
            'total_sites':    sites.count(),
            'active_sites':   sites.filter(status='active').count(),
            'pending_sites':  sites.filter(status='pending').count(),
            'total_apps':     apps.count(),
            'active_apps':    apps.filter(status='active').count(),
            'total_units':    units.count(),
            'active_units':   units.filter(status='active').count(),
        },
        'fraud_widget': {
            'total_ivt':      ivt_logs.count(),
            'critical':       ivt_logs.filter(severity='critical').count(),
            'high':           ivt_logs.filter(severity='high').count(),
            'revenue_at_risk':float(ivt_logs.aggregate(r=Sum('revenue_at_risk')).get('r') or 0),
            'pending_review': ivt_logs.filter(action_taken='pending').count(),
        },
        'top_sites':     top_sites,
        'daily_chart':   [
            {
                'date':        str(row['date']),
                'revenue':     float(row['revenue'] or 0),
                'impressions': row['impressions'] or 0,
            }
            for row in daily_chart
        ],
    }


def get_performance_alerts(publisher) -> List[Dict]:
    """
    Publisher-এর current performance alerts।
    Action needed items।
    """
    from ..models import Site, App, AdUnit, PublisherInvoice, SiteQualityMetric, TrafficSafetyLog

    alerts = []

    # KYC not done
    try:
        if not publisher.kyc.is_approved:
            alerts.append({
                'type': 'kyc_incomplete',
                'severity': 'high',
                'title': 'KYC Verification Required',
                'message': 'Complete KYC to unlock full payout features.',
                'action_url': '/publisher/kyc/',
                'action_text': 'Complete KYC',
            })
    except Exception:
        alerts.append({
            'type': 'kyc_not_started',
            'severity': 'medium',
            'title': 'KYC Not Started',
            'message': 'Start KYC verification to increase trust score.',
            'action_url': '/publisher/kyc/',
            'action_text': 'Start KYC',
        })

    # Pending sites
    pending_sites = Site.objects.filter(publisher=publisher, status='pending').count()
    if pending_sites > 0:
        alerts.append({
            'type': 'pending_sites',
            'severity': 'info',
            'title': f'{pending_sites} Site(s) Awaiting Verification',
            'message': 'Your sites are pending domain verification.',
            'action_url': '/publisher/sites/',
            'action_text': 'Verify Sites',
        })

    # Sites with quality alerts
    quality_alerts = SiteQualityMetric.objects.filter(
        site__publisher=publisher,
        date=timezone.now().date(),
        has_alerts=True,
    ).count()
    if quality_alerts > 0:
        alerts.append({
            'type': 'quality_alerts',
            'severity': 'high',
            'title': f'{quality_alerts} Site(s) Have Quality Issues',
            'message': 'Quality issues detected. Review and fix to maintain revenue.',
            'action_url': '/publisher/sites/quality/',
            'action_text': 'Review Issues',
        })

    # Overdue invoices
    overdue_invoices = PublisherInvoice.objects.filter(
        publisher=publisher,
        status='issued',
        due_date__lt=timezone.now().date(),
    ).count()
    if overdue_invoices > 0:
        alerts.append({
            'type': 'overdue_invoices',
            'severity': 'medium',
            'title': f'{overdue_invoices} Invoice(s) Overdue',
            'message': 'Payment processing for overdue invoices.',
            'action_url': '/publisher/invoices/',
            'action_text': 'View Invoices',
        })

    # High IVT
    today_ivt = TrafficSafetyLog.objects.filter(
        publisher=publisher,
        detected_at__date=timezone.now().date(),
        severity__in=['high', 'critical'],
        is_false_positive=False,
    ).count()
    if today_ivt >= 10:
        alerts.append({
            'type': 'high_ivt',
            'severity': 'critical',
            'title': f'{today_ivt} High-Risk IVT Events Today',
            'message': 'Unusual invalid traffic detected. Immediate review required.',
            'action_url': '/publisher/fraud/',
            'action_text': 'Review IVT',
        })

    # No payment method
    if not publisher.bank_accounts.filter(verification_status='verified').exists():
        alerts.append({
            'type': 'no_payment_method',
            'severity': 'high',
            'title': 'No Verified Payment Method',
            'message': 'Add and verify a payment method to receive payouts.',
            'action_url': '/publisher/payments/',
            'action_text': 'Add Payment Method',
        })

    return sorted(alerts, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'info': 3}.get(x['severity'], 4))


def get_earnings_chart_data(publisher, period: str = 'last_30_days', metric: str = 'revenue') -> List[Dict]:
    """
    Chart data for earnings visualization।
    metric: 'revenue', 'impressions', 'ecpm', 'ctr'
    """
    from ..models import PublisherEarning
    from ...utils import get_date_range

    start_date, end_date = get_date_range(period)

    qs = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
        granularity='daily',
    ).values('date').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
        avg_ecpm=Avg('ecpm'),
    ).order_by('date')

    chart_data = []
    for row in qs:
        point = {'date': str(row['date'])}
        if metric == 'revenue':
            point['value'] = float(row['revenue'] or 0)
        elif metric == 'impressions':
            point['value'] = row['impressions'] or 0
        elif metric == 'ecpm':
            point['value'] = float(row['avg_ecpm'] or 0)
        elif metric == 'ctr':
            imp = row['impressions'] or 0
            clk = row['clicks'] or 0
            point['value'] = round((clk / imp * 100) if imp > 0 else 0, 4)
        else:
            point['value'] = float(row['revenue'] or 0)
        chart_data.append(point)

    return chart_data
