# api/publisher_tools/performance_analytics/ecpm_analyzer.py
"""
eCPM Analyzer — eCPM trends, comparisons, optimization suggestions।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict

from django.db.models import Sum, Avg, Max, Min
from django.utils import timezone


def get_ecpm_by_country(publisher, start_date: date, end_date: date) -> List[Dict]:
    """Country-wise eCPM breakdown"""
    from ..models import PublisherEarning

    data = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
        impressions__gt=0,
    ).values('country', 'country_name').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).filter(impressions__gt=0)

    result = []
    for row in data:
        ecpm = (Decimal(str(row['revenue'])) / Decimal(str(row['impressions']))) * 1000
        result.append({
            'country': row['country'],
            'country_name': row['country_name'],
            'ecpm': round(float(ecpm), 4),
            'revenue': float(row['revenue']),
            'impressions': row['impressions'],
        })

    return sorted(result, key=lambda x: x['ecpm'], reverse=True)


def get_ecpm_by_format(publisher, start_date: date, end_date: date) -> List[Dict]:
    """Ad format-wise eCPM breakdown"""
    from ..models import PublisherEarning

    data = PublisherEarning.objects.filter(
        publisher=publisher,
        date__range=[start_date, end_date],
        impressions__gt=0,
    ).values('ad_unit__format', 'earning_type').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    )

    result = []
    for row in data:
        if row['impressions'] > 0:
            ecpm = (Decimal(str(row['revenue'])) / Decimal(str(row['impressions']))) * 1000
            result.append({
                'format': row['ad_unit__format'],
                'earning_type': row['earning_type'],
                'ecpm': round(float(ecpm), 4),
                'revenue': float(row['revenue']),
                'impressions': row['impressions'],
            })

    return sorted(result, key=lambda x: x['ecpm'], reverse=True)


def get_ecpm_trend(publisher, days: int = 30) -> List[Dict]:
    """Daily eCPM trend"""
    from ..models import PublisherEarning

    start = timezone.now().date() - timedelta(days=days)
    data = PublisherEarning.objects.filter(
        publisher=publisher,
        date__gte=start,
        granularity='daily',
        impressions__gt=0,
    ).values('date').annotate(
        revenue=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
    ).order_by('date')

    result = []
    for row in data:
        if row['impressions'] > 0:
            ecpm = (Decimal(str(row['revenue'])) / Decimal(str(row['impressions']))) * 1000
            result.append({
                'date': str(row['date']),
                'ecpm': round(float(ecpm), 4),
                'revenue': float(row['revenue']),
                'impressions': row['impressions'],
            })

    return result


def get_ecpm_optimization_suggestions(publisher) -> List[Dict]:
    """
    eCPM optimize করার suggestions দেয়।
    Low eCPM-এর কারণ বিশ্লেষণ করে।
    """
    suggestions = []
    from ..models import AdUnit, MediationGroup

    # Check floor prices
    low_floor_units = AdUnit.objects.filter(
        publisher=publisher,
        status='active',
        floor_price=0,
    ).count()

    if low_floor_units > 0:
        suggestions.append({
            'type': 'floor_price',
            'priority': 'high',
            'title': 'Set Floor Prices',
            'description': f'{low_floor_units} ad unit(s) have no floor price set. Setting a floor price can increase eCPM.',
            'action': 'Set floor price of $0.50-$2.00 CPM for display ads.',
        })

    # Check mediation
    units_without_mediation = AdUnit.objects.filter(
        publisher=publisher,
        status='active',
    ).exclude(
        mediation_group__waterfall_items__status='active',
    ).count()

    if units_without_mediation > 0:
        suggestions.append({
            'type': 'mediation',
            'priority': 'high',
            'title': 'Add More Ad Networks',
            'description': f'{units_without_mediation} ad unit(s) have fewer than 2 active networks in waterfall.',
            'action': 'Add 3-5 ad networks to your waterfall for better competition.',
        })

    # Header bidding
    has_header_bidding = MediationGroup.objects.filter(
        ad_unit__publisher=publisher,
        mediation_type__in=['header_bidding', 'hybrid'],
        is_active=True,
    ).exists()

    if not has_header_bidding:
        suggestions.append({
            'type': 'header_bidding',
            'priority': 'medium',
            'title': 'Enable Header Bidding',
            'description': 'Header bidding creates real-time competition and typically increases eCPM by 20-40%.',
            'action': 'Enable Prebid.js or switch to hybrid mediation mode.',
        })

    return suggestions
