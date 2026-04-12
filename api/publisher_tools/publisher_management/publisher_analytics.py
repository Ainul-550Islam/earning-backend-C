# api/publisher_tools/publisher_management/publisher_analytics.py
"""
Publisher Analytics — Comprehensive analytics & reporting।
Publisher dashboard-এর জন্য সব analytics data।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from django.db.models import Sum, Avg, Count, Q, Max, Min, F
from django.utils import timezone


def get_publisher_overview(publisher, period: str = 'last_30_days') -> Dict:
    """
    Publisher-এর complete overview।
    সব key metrics একসাথে।
    """
    from ..models import PublisherEarning, Site, App
    from ...utils import get_date_range, calculate_ecpm, calculate_ctr

    start_date, end_date = get_date_range(period)

    # Current period earnings
    current = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
    ).aggregate(
        revenue=Sum('publisher_revenue'),
        gross=Sum('gross_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
        requests=Sum('ad_requests'),
        ivt_deduction=Sum('invalid_traffic_deduction'),
    )

    # Previous period (for comparison)
    days_count = (end_date - start_date).days + 1
    prev_end   = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days_count - 1)

    previous = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[prev_start, prev_end],
    ).aggregate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    )

    current_rev  = current.get('revenue') or Decimal('0')
    previous_rev = previous.get('revenue') or Decimal('0')
    impressions  = current.get('impressions') or 0
    clicks       = current.get('clicks') or 0
    requests     = current.get('requests') or 0

    # Revenue change
    if previous_rev > 0:
        revenue_change_pct = float((current_rev - previous_rev) / previous_rev * 100)
    else:
        revenue_change_pct = 100.0 if current_rev > 0 else 0.0

    # Inventory counts
    active_sites = Site.objects.filter(publisher=publisher, status='active').count()
    active_apps  = App.objects.filter(publisher=publisher, status='active').count()
    from ..models import AdUnit
    active_units = AdUnit.objects.filter(publisher=publisher, status='active').count()

    return {
        'period':            {'start': str(start_date), 'end': str(end_date)},
        'revenue': {
            'current':         float(current_rev),
            'previous':        float(previous_rev),
            'change_pct':      round(revenue_change_pct, 2),
            'is_growth':       current_rev >= previous_rev,
            'gross':           float(current.get('gross') or 0),
            'ivt_deduction':   float(current.get('ivt_deduction') or 0),
        },
        'traffic': {
            'impressions':     impressions,
            'clicks':          clicks,
            'ad_requests':     requests,
            'ecpm':            float(calculate_ecpm(current_rev, impressions)),
            'ctr':             float(calculate_ctr(clicks, impressions)),
            'fill_rate':       round((impressions / requests * 100) if requests > 0 else 0, 2),
        },
        'inventory': {
            'active_sites':    active_sites,
            'active_apps':     active_apps,
            'active_ad_units': active_units,
        },
        'account': {
            'total_revenue':   float(publisher.total_revenue),
            'total_paid_out':  float(publisher.total_paid_out),
            'pending_balance': float(publisher.pending_balance),
            'available':       float(publisher.available_balance),
            'tier':            publisher.tier,
            'status':          publisher.status,
        },
    }


def get_revenue_breakdown(publisher, start_date: date, end_date: date) -> Dict:
    """
    Revenue breakdown by multiple dimensions।
    """
    from ..models import PublisherEarning

    qs = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
    )

    # By earning type
    by_type = list(qs.values('earning_type').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('-revenue'))

    # By country (top 10)
    by_country = list(qs.values('country', 'country_name').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('-revenue')[:10])

    # By ad unit (top 10)
    by_unit = list(qs.values(
        'ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format'
    ).annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('-revenue')[:10])

    # By site/app
    by_site = list(qs.filter(site__isnull=False).values(
        'site__site_id', 'site__name', 'site__domain'
    ).annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('-revenue'))

    by_app = list(qs.filter(app__isnull=False).values(
        'app__app_id', 'app__name', 'app__platform'
    ).annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('-revenue'))

    # By day
    by_day = list(qs.values('date').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
    ).order_by('date'))

    return {
        'by_earning_type': by_type,
        'by_country':      by_country,
        'by_ad_unit':      by_unit,
        'by_site':         by_site,
        'by_app':          by_app,
        'by_day':          by_day,
        'period': {'start': str(start_date), 'end': str(end_date)},
    }


def get_performance_metrics(publisher, days: int = 30) -> Dict:
    """
    Publisher performance metrics — eCPM, CTR, Fill Rate trends।
    """
    from ..models import PublisherEarning, AdUnit

    start = timezone.now().date() - timedelta(days=days)

    # Overall performance
    agg = PublisherEarning.objects.filter(
        publisher=publisher,
        date__gte=start,
    ).aggregate(
        total_revenue=Sum('publisher_revenue'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_requests=Sum('ad_requests'),
        avg_ecpm=Avg('ecpm'),
        avg_fill_rate=Avg('fill_rate'),
        avg_ctr=Avg('ctr'),
    )

    # Best performing day
    best_day = PublisherEarning.objects.filter(
        publisher=publisher, date__gte=start,
    ).values('date').annotate(
        revenue=Sum('publisher_revenue')
    ).order_by('-revenue').first()

    # Best performing ad unit
    best_unit = PublisherEarning.objects.filter(
        publisher=publisher, date__gte=start,
    ).values('ad_unit__unit_id', 'ad_unit__name').annotate(
        revenue=Sum('publisher_revenue')
    ).order_by('-revenue').first()

    # Ad unit count by status
    unit_stats = {
        row['status']: row['count']
        for row in AdUnit.objects.filter(
            publisher=publisher
        ).values('status').annotate(count=Count('id'))
    }

    return {
        'period_days': days,
        'overall': {
            'total_revenue':    float(agg.get('total_revenue') or 0),
            'total_impressions':agg.get('total_impressions') or 0,
            'total_clicks':     agg.get('total_clicks') or 0,
            'avg_ecpm':         float(agg.get('avg_ecpm') or 0),
            'avg_fill_rate':    float(agg.get('avg_fill_rate') or 0),
            'avg_ctr':          float(agg.get('avg_ctr') or 0),
        },
        'best_day':   best_day,
        'best_unit':  best_unit,
        'ad_unit_status': unit_stats,
    }


def get_revenue_forecast(publisher, days_ahead: int = 30) -> Dict:
    """
    Future revenue forecast using historical data।
    Simple linear trend extrapolation।
    """
    from ..models import PublisherEarning

    # Get last 90 days daily revenue
    start = timezone.now().date() - timedelta(days=90)
    daily_data = list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__gte=start,
            granularity='daily',
        ).values('date').annotate(
            revenue=Sum('publisher_revenue'),
        ).order_by('date').values_list('revenue', flat=True)
    )

    if len(daily_data) < 7:
        return {
            'forecast': 0,
            'confidence': 'low',
            'reason': 'insufficient_data',
            'message': 'Need at least 7 days of data for forecast.',
        }

    daily_data_float = [float(r) for r in daily_data]

    # Moving average (last 7 days)
    recent_avg = sum(daily_data_float[-7:]) / 7

    # Trend (linear regression slope)
    n = len(daily_data_float)
    x_mean = (n - 1) / 2
    y_mean = sum(daily_data_float) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(daily_data_float))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator > 0 else 0

    # Forecast
    forecast_daily = max(0, recent_avg + slope * days_ahead)
    forecast_total = forecast_daily * days_ahead

    # Confidence based on data consistency
    if n >= 60:
        confidence = 'high'
    elif n >= 30:
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'forecast_total':  round(forecast_total, 2),
        'forecast_daily':  round(forecast_daily, 2),
        'current_avg_daily': round(recent_avg, 2),
        'trend_direction':   'up' if slope > 0 else 'down' if slope < 0 else 'flat',
        'trend_daily':       round(slope, 4),
        'days_ahead':        days_ahead,
        'confidence':        confidence,
        'data_points':       n,
    }


def get_top_earning_content(publisher, days: int = 30, limit: int = 10) -> Dict:
    """
    Top earning sites, apps, ad units।
    """
    from ..models import PublisherEarning

    start = timezone.now().date() - timedelta(days=days)

    top_sites = list(
        PublisherEarning.objects.filter(
            publisher=publisher, date__gte=start,
            site__isnull=False,
        ).values('site__site_id', 'site__name', 'site__domain', 'site__category').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
            ecpm=Sum('publisher_revenue') / Sum('impressions') * 1000,
        ).order_by('-revenue')[:limit]
    )

    top_apps = list(
        PublisherEarning.objects.filter(
            publisher=publisher, date__gte=start,
            app__isnull=False,
        ).values('app__app_id', 'app__name', 'app__platform', 'app__category').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
        ).order_by('-revenue')[:limit]
    )

    top_units = list(
        PublisherEarning.objects.filter(
            publisher=publisher, date__gte=start,
        ).values(
            'ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format'
        ).annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
        ).order_by('-revenue')[:limit]
    )

    top_countries = list(
        PublisherEarning.objects.filter(
            publisher=publisher, date__gte=start,
        ).values('country', 'country_name').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
        ).order_by('-revenue')[:limit]
    )

    return {
        'period_days':   days,
        'top_sites':     top_sites,
        'top_apps':      top_apps,
        'top_ad_units':  top_units,
        'top_countries': top_countries,
    }


def get_comparison_analytics(
    publisher,
    current_start: date,
    current_end: date,
    compare_start: date,
    compare_end: date,
) -> Dict:
    """
    দুটো period compare করে।
    এই month vs last month, এই week vs last week, etc.
    """
    from ..models import PublisherEarning

    def get_period_stats(s: date, e: date) -> Dict:
        agg = PublisherEarning.objects.filter(
            publisher=publisher, date__range=[s, e],
        ).aggregate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            requests=Sum('ad_requests'),
        )
        rev = agg.get('revenue') or Decimal('0')
        imp = agg.get('impressions') or 0
        return {
            'revenue':     float(rev),
            'impressions': imp,
            'clicks':      agg.get('clicks') or 0,
            'ecpm':        float((rev / imp * 1000) if imp > 0 else 0),
            'period':      {'start': str(s), 'end': str(e)},
        }

    current  = get_period_stats(current_start, current_end)
    previous = get_period_stats(compare_start, compare_end)

    def pct_change(c, p):
        if p == 0:
            return 100.0 if c > 0 else 0.0
        return round((c - p) / p * 100, 2)

    return {
        'current':  current,
        'previous': previous,
        'changes': {
            'revenue':      pct_change(current['revenue'], previous['revenue']),
            'impressions':  pct_change(current['impressions'], previous['impressions']),
            'clicks':       pct_change(current['clicks'], previous['clicks']),
            'ecpm':         pct_change(current['ecpm'], previous['ecpm']),
        },
    }
