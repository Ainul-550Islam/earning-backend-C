# api/publisher_tools/ad_placements/placement_optimizer.py
"""Placement Optimizer — AI-driven placement optimization."""
from decimal import Decimal
from datetime import timedelta
from typing import List, Dict
from django.db.models import Avg, Sum
from django.utils import timezone


def analyze_all_placements(publisher) -> List[Dict]:
    """Publisher-এর সব placements analyze করে।"""
    from api.publisher_tools.models import AdPlacement, PublisherEarning
    placements = AdPlacement.objects.filter(
        ad_unit__publisher=publisher, is_active=True
    ).select_related("ad_unit")
    results = []
    for p in placements:
        score = _calculate_placement_health_score(p)
        results.append({
            "placement_id":   str(p.id),
            "name":           p.name,
            "position":       p.position,
            "health_score":   score,
            "viewability":    float(p.avg_viewability),
            "effective_floor":float(p.effective_floor_price),
            "is_active":      p.is_active,
            "issues":         _identify_issues(p),
            "recommendations":_get_recommendations(p),
        })
    return sorted(results, key=lambda x: x["health_score"])


def _calculate_placement_health_score(placement) -> int:
    score = 100
    if float(placement.avg_viewability) < 50:
        score -= 30
    elif float(placement.avg_viewability) < 70:
        score -= 15
    if float(placement.effective_floor_price) == 0:
        score -= 20
    if not placement.show_on_mobile:
        score -= 10
    return max(0, score)


def _identify_issues(placement) -> List[str]:
    issues = []
    if float(placement.avg_viewability) < 50:
        issues.append(f"Low viewability ({placement.avg_viewability}%). Consider moving ad above the fold.")
    if float(placement.effective_floor_price) == 0:
        issues.append("No floor price set. Missing revenue opportunity.")
    if placement.refresh_type == "none" and placement.position in ("sticky_bottom", "sticky_top"):
        issues.append("Sticky placement with no refresh. Enable refresh for more impressions.")
    return issues


def _get_recommendations(placement) -> List[str]:
    recs = []
    if float(placement.avg_viewability) < 70:
        from .placement_position import suggest_better_position
        better = suggest_better_position(placement.position)
        if better != placement.position:
            recs.append(f"Move to '{better}' for higher viewability.")
    if float(placement.effective_floor_price) < 0.50:
        recs.append("Set floor price to $0.50+ CPM to filter low-quality ads.")
    if placement.refresh_type == "none" and placement.position in ("above_fold", "sticky_bottom"):
        recs.append("Enable time-based refresh (30s) to increase impressions by 20-30%.")
    return recs


def auto_optimize_placement(placement) -> Dict:
    """Placement auto-optimize করে।"""
    changes = {}
    # Auto-set floor price if not set
    if float(placement.effective_floor_price) == 0:
        from .placement_floor_price import suggest_floor_price
        suggestion = suggest_floor_price(placement)
        if suggestion["suggested_floor"] > 0:
            placement.floor_price_override = Decimal(str(suggestion["suggested_floor"]))
            changes["floor_price"] = suggestion["suggested_floor"]
    # Enable refresh for sticky placements
    if placement.position in ("sticky_bottom", "sticky_top") and placement.refresh_type == "none":
        placement.refresh_type = "time_based"
        placement.refresh_interval_seconds = 30
        changes["refresh"] = "enabled (30s)"
    if changes:
        placement.save()
    return {"placement_id": str(placement.id), "changes": changes, "auto_optimized": bool(changes)}
