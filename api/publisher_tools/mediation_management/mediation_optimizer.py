# api/publisher_tools/mediation_management/mediation_optimizer.py
"""Mediation Optimizer — Full optimization pipeline."""
from decimal import Decimal
from typing import Dict, List
from django.utils import timezone


def run_full_optimization(publisher) -> Dict:
    """Publisher-এর সব mediation groups optimize করে।"""
    from api.publisher_tools.models import MediationGroup
    from api.publisher_tools.services import MediationService
    groups = MediationGroup.objects.filter(
        ad_unit__publisher=publisher, is_active=True, auto_optimize=True,
    )
    results = []
    for group in groups:
        try:
            MediationService.optimize_waterfall(group)
            results.append({"group_id": str(group.id), "name": group.name, "status": "optimized"})
        except Exception as e:
            results.append({"group_id": str(group.id), "name": group.name, "status": "error", "error": str(e)})
    return {"publisher_id": publisher.publisher_id, "optimized_at": timezone.now().isoformat(), "groups": results}


def get_optimization_opportunities(publisher) -> List[Dict]:
    """Optimization opportunities identify করে।"""
    from api.publisher_tools.models import MediationGroup
    opportunities = []
    groups = MediationGroup.objects.filter(ad_unit__publisher=publisher, is_active=True)
    for group in groups:
        from .bidding_optimizer import analyze_lost_bids
        from .network_priority import detect_underperforming_networks
        lost = analyze_lost_bids(group)
        underperf = detect_underperforming_networks(group)
        if lost["total_estimated_lost_revenue"] > 0 or underperf:
            opportunities.append({
                "group_id": str(group.id),
                "name": group.name,
                "estimated_revenue_opportunity": lost["total_estimated_lost_revenue"],
                "underperforming_networks": len(underperf),
                "action": "optimize_waterfall" if underperf else "adjust_floor_prices",
            })
    return sorted(opportunities, key=lambda x: x["estimated_revenue_opportunity"], reverse=True)


def schedule_auto_optimization(publisher, interval_hours: int = 24):
    """Auto-optimization schedule করে।"""
    from api.publisher_tools.models import MediationGroup
    from django.utils import timezone
    from datetime import timedelta
    next_run = timezone.now() + timedelta(hours=interval_hours)
    MediationGroup.objects.filter(
        ad_unit__publisher=publisher, is_active=True
    ).update(optimization_interval_hours=interval_hours)
    return {"scheduled_at": next_run.isoformat(), "interval_hours": interval_hours}
