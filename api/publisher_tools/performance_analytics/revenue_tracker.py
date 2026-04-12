# api/publisher_tools/performance_analytics/revenue_tracker.py
"""
Revenue Tracker — Real-time ও historical revenue tracking utilities।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Optional

from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone


def get_revenue_by_dimension(
    publisher,
    start_date: date,
    end_date: date,
    dimension: str = 'date',
) -> List[Dict]:
    """
    Revenue data নির্দিষ্ট dimension-এ group করে return করে।
    dimension: 'date', 'country', 'ad_unit', 'earning_type', 'network'
    """
    from ..models import PublisherEarning

    valid_dimensions = {
        'date':         ['date'],
        'country':      ['country', 'country_name'],
        'ad_unit':      ['ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format'],
        'earning_type': ['earning_type'],
        'network':      ['network__name'],
        'hour':         ['date', 'hour'],
    }

    if dimension not in valid_dimensions:
        dimension = 'date'

    group_fields = valid_dimensions[dimension]

    return list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
        ).values(*group_fields).annotate(
            revenue=Sum('publisher_revenue'),
            gross=Sum('gross_revenue'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            requests=Sum('ad_requests'),
        ).order_by('-revenue')
    )


def get_top_performing_units(publisher, days: int = 30, limit: int = 10) -> List[Dict]:
    """Top performing ad units by revenue"""
    from ..models import PublisherEarning

    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__gte=start,
        ).values(
            'ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format'
        ).annotate(
            revenue=Sum('publisher_revenue'),
            ecpm=Sum('publisher_revenue') / Sum('impressions') * 1000,
            impressions=Sum('impressions'),
        ).order_by('-revenue')[:limit]
    )


def get_revenue_trend(publisher, days: int = 30) -> List[Dict]:
    """Day-by-day revenue trend"""
    from ..models import PublisherEarning

    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(
            publisher=publisher,
            date__gte=start,
            granularity='daily',
        ).values('date').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
        ).order_by('date')
    )


def calculate_revenue_growth(
    publisher,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
) -> Dict:
    """
    Two period-এর মধ্যে revenue growth calculate করে।
    Returns percentage change and absolute change.
    """
    from ..models import PublisherEarning

    def get_period_revenue(s, e):
        agg = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[s, e],
        ).aggregate(total=Sum('publisher_revenue'))
        return agg.get('total') or Decimal('0')

    current_rev  = get_period_revenue(current_start, current_end)
    previous_rev = get_period_revenue(previous_start, previous_end)

    absolute_change = current_rev - previous_rev
    if previous_rev > 0:
        percentage_change = float((absolute_change / previous_rev) * 100)
    else:
        percentage_change = 100.0 if current_rev > 0 else 0.0

    return {
        'current_period_revenue':  float(current_rev),
        'previous_period_revenue': float(previous_rev),
        'absolute_change':         float(absolute_change),
        'percentage_change':       round(percentage_change, 2),
        'is_growth':               absolute_change >= 0,
    }


def forecast_monthly_revenue(publisher, months_ahead: int = 1) -> Dict:
    """
    Simple linear regression দিয়ে monthly revenue forecast করে।
    """
    from ..models import PublisherEarning

    # Last 6 months data
    today = timezone.now().date()
    data_points = []

    for i in range(6, 0, -1):
        month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        month_end   = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        agg = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[month_start, month_end],
        ).aggregate(total=Sum('publisher_revenue'))
        data_points.append(float(agg.get('total') or 0))

    if not data_points or max(data_points) == 0:
        return {'forecast': 0, 'confidence': 'low', 'method': 'insufficient_data'}

    # Simple moving average forecast
    recent_avg = sum(data_points[-3:]) / 3
    trend = (data_points[-1] - data_points[0]) / len(data_points) if len(data_points) > 1 else 0
    forecast = recent_avg + (trend * months_ahead)

    return {
        'forecast': round(max(0, forecast), 2),
        'confidence': 'medium',
        'method': 'moving_average',
        'data_points': data_points,
        'trend': round(trend, 2),
    }
