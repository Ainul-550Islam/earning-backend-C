# api/publisher_tools/optimization_tools/placement_optimizer.py
"""Placement Optimizer — Full placement optimization pipeline."""
from typing import Dict, List


def run_placement_optimization(publisher) -> Dict:
    """Publisher-এর সব placements optimize করে।"""
    from api.publisher_tools.models import AdPlacement
    placements = AdPlacement.objects.filter(ad_unit__publisher=publisher).select_related("ad_unit")
    results = []
    for p in placements:
        changes = _optimize_single_placement(p)
        if changes:
            results.append({"placement": p.name, "changes": changes})
    return {"publisher_id": publisher.publisher_id, "optimized_count": len(results), "details": results}


def _optimize_single_placement(placement) -> Dict:
    changes = {}
    # Auto-set floor price if 0
    if float(placement.effective_floor_price) == 0:
        from .yield_optimizer import suggest_floor_price
        suggestion = suggest_floor_price(placement)
        if suggestion.get("suggested_floor", 0) > 0:
            from decimal import Decimal
            placement.floor_price_override = Decimal(str(suggestion["suggested_floor"]))
            changes["floor_price"] = suggestion["suggested_floor"]
    # Enable refresh for sticky
    if placement.position in ("sticky_bottom", "sticky_top") and placement.refresh_type == "none":
        placement.refresh_type = "time_based"
        placement.refresh_interval_seconds = 30
        changes["refresh"] = "30s time-based"
    # Disable on bad devices
    if float(placement.avg_viewability) < 20 and placement.show_on_mobile:
        changes["suggestion"] = "Consider testing with mobile=False due to low viewability"
    if changes:
        placement.save()
    return changes


def score_all_placements(publisher) -> List[Dict]:
    from api.publisher_tools.models import AdPlacement
    from api.publisher_tools.ad_placements.placement_reporting import get_placement_efficiency_score
    placements = AdPlacement.objects.filter(ad_unit__publisher=publisher).select_related("ad_unit")
    return sorted(
        [get_placement_efficiency_score(p) for p in placements],
        key=lambda x: x["efficiency_score"]
    )
