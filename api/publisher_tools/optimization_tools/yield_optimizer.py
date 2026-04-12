# api/publisher_tools/optimization_tools/yield_optimizer.py
"""
Yield Optimizer — Revenue maximize করার optimization algorithms।
"""
from decimal import Decimal
from datetime import timedelta
from typing import List, Dict, Tuple

from django.utils import timezone


def optimize_floor_prices(publisher) -> List[Dict]:
    """
    প্রতিটি Ad Unit-এর optimal floor price suggest করে।
    Historical eCPM data-র ভিত্তিতে।
    """
    from ..models import AdUnit, PublisherEarning

    suggestions = []
    units = AdUnit.objects.filter(publisher=publisher, status='active')
    last_30 = timezone.now().date() - timedelta(days=30)

    for unit in units:
        earnings = PublisherEarning.objects.filter(
            ad_unit=unit,
            date__gte=last_30,
        )

        if not earnings.exists():
            continue

        from django.db.models import Avg, Percentile
        from django.db.models import Sum

        agg = earnings.aggregate(
            avg_ecpm=Sum('publisher_revenue') / Sum('impressions') * 1000,
            total_impressions=Sum('impressions'),
            total_revenue=Sum('publisher_revenue'),
        )

        avg_ecpm = float(agg.get('avg_ecpm') or 0)
        if avg_ecpm <= 0:
            continue

        # Suggested floor = 70% of average eCPM
        suggested_floor = round(avg_ecpm * 0.70, 4)
        current_floor   = float(unit.floor_price)

        if suggested_floor > current_floor * 1.1:  # 10% higher than current
            suggestions.append({
                'unit_id':          unit.unit_id,
                'unit_name':        unit.name,
                'current_floor':    current_floor,
                'suggested_floor':  suggested_floor,
                'avg_ecpm':         avg_ecpm,
                'potential_uplift': f'+{round((suggested_floor - current_floor) / max(current_floor, 0.01) * 100, 1)}%',
                'confidence':       'high' if agg['total_impressions'] > 10000 else 'medium',
            })

    return sorted(suggestions, key=lambda x: x['potential_uplift'], reverse=True)


def suggest_waterfall_optimization(group) -> Dict:
    """
    Waterfall optimization suggestions।
    Low performing networks সরানো, high performing আগে রাখা।
    """
    from ..models import WaterfallItem

    items = WaterfallItem.objects.filter(
        mediation_group=group,
        status='active',
    ).order_by('priority')

    recommendations = []
    for item in items:
        if item.fill_rate < 10 and item.total_ad_requests > 1000:
            recommendations.append({
                'item_id': str(item.id),
                'network': item.network.name,
                'issue': 'very_low_fill_rate',
                'action': 'Consider removing or pausing this network (fill rate < 10%)',
                'fill_rate': float(item.fill_rate),
                'avg_ecpm': float(item.avg_ecpm),
            })
        elif item.avg_latency_ms > 800:
            recommendations.append({
                'item_id': str(item.id),
                'network': item.network.name,
                'issue': 'high_latency',
                'action': 'Move this network lower in waterfall (latency > 800ms)',
                'latency_ms': item.avg_latency_ms,
            })

    # Check if waterfall is sorted by eCPM
    ecpms = [float(item.avg_ecpm) for item in items if item.avg_ecpm > 0]
    is_optimal = ecpms == sorted(ecpms, reverse=True)

    return {
        'group_id': str(group.id),
        'is_ecpm_optimized': is_optimal,
        'recommendations': recommendations,
        'current_avg_ecpm': float(group.avg_ecpm),
        'current_fill_rate': float(group.fill_rate),
        'optimization_available': not is_optimal or len(recommendations) > 0,
    }


def get_ad_load_optimization(site) -> Dict:
    """
    Site-এর ad load optimization suggest করে।
    Too many/few ads চেক করে।
    """
    from ..models import AdUnit, AdPlacement

    active_units = AdUnit.objects.filter(site=site, status='active').count()
    active_placements = AdPlacement.objects.filter(
        ad_unit__site=site, is_active=True
    ).count()

    suggestions = []
    if active_units == 0:
        suggestions.append({
            'type': 'no_ads',
            'message': 'No active ad units on this site.',
            'action': 'Create at least one ad unit to start earning.',
        })
    elif active_units > 5:
        suggestions.append({
            'type': 'too_many_ads',
            'message': f'{active_units} active ad units may reduce user experience.',
            'action': 'Consider reducing to 3-4 ad units for better UX and higher eCPM.',
        })

    if active_placements > 0:
        # Check if any placements are above fold
        above_fold = AdPlacement.objects.filter(
            ad_unit__site=site,
            is_active=True,
            position__in=['above_fold', 'header'],
        ).count()

        if above_fold == 0:
            suggestions.append({
                'type': 'no_above_fold',
                'message': 'No above-the-fold placements.',
                'action': 'Add at least one ad unit above the fold for better viewability.',
            })

    return {
        'site_id': site.site_id,
        'domain': site.domain,
        'active_units': active_units,
        'active_placements': active_placements,
        'suggestions': suggestions,
        'optimization_score': max(0, 100 - len(suggestions) * 20),
    }


def calculate_revenue_opportunity(publisher) -> Dict:
    """
    Publisher-এর untapped revenue opportunity calculate করে।
    """
    from ..models import AdUnit, PublisherEarning
    from django.db.models import Sum
    from datetime import timedelta

    last_30 = timezone.now().date() - timedelta(days=30)

    actual_revenue = PublisherEarning.objects.filter(
        publisher=publisher,
        date__gte=last_30,
    ).aggregate(total=Sum('publisher_revenue')).get('total') or Decimal('0')

    # Estimated potential
    active_sites = publisher.sites.filter(status='active').count()
    active_apps  = publisher.apps.filter(status='active').count()
    active_units = AdUnit.objects.filter(publisher=publisher, status='active').count()

    # Very simplified potential estimate
    estimated_monthly_potential = Decimal(str(
        active_sites * 50 + active_apps * 30 + active_units * 20
    ))

    gap = max(Decimal('0'), estimated_monthly_potential - actual_revenue)
    gap_pct = float(gap / estimated_monthly_potential * 100) if estimated_monthly_potential > 0 else 0

    return {
        'actual_revenue_30d': float(actual_revenue),
        'estimated_potential_30d': float(estimated_monthly_potential),
        'revenue_gap': float(gap),
        'gap_percentage': round(gap_pct, 1),
        'opportunities': [
            'Enable header bidding (+20-40% eCPM)',
            'Add more ad networks to waterfall (+10-25% fill rate)',
            'Set optimal floor prices (+5-15% eCPM)',
            'Enable auto-refresh for display ads (+15-30% impressions)',
        ] if gap > 0 else [],
    }
