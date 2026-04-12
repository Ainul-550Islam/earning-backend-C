# api/publisher_tools/optimization_tools/viewability_optimizer.py
"""Viewability Optimizer — Improve ad viewability rates."""
from decimal import Decimal
from typing import Dict, List


VIEWABILITY_TARGETS = {
    "display": 70.0,
    "video":   50.0,
    "native":  60.0,
}

POSITION_VIEWABILITY = {
    "above_fold": 85, "header": 82, "in_content": 75,
    "sticky_bottom": 68, "sidebar_right": 55, "below_fold": 40,
}


def get_viewability_recommendations(site) -> List[Dict]:
    """Site viewability improvement recommendations।"""
    from api.publisher_tools.models import AdPlacement
    placements = AdPlacement.objects.filter(ad_unit__site=site, is_active=True)
    recommendations = []
    for p in placements:
        viewability = float(p.avg_viewability)
        target = VIEWABILITY_TARGETS.get(p.ad_unit.format, 70.0)
        if viewability < target:
            gap = target - viewability
            better_positions = [pos for pos, score in POSITION_VIEWABILITY.items() if score > POSITION_VIEWABILITY.get(p.position, 50) + 10]
            recommendations.append({
                "placement": p.name, "current_viewability": viewability, "target": target,
                "gap": gap, "suggested_positions": better_positions[:3],
                "action": f"Move from '{p.position}' to '{better_positions[0]}'" if better_positions else "Improve page content above ad",
            })
    return sorted(recommendations, key=lambda x: x["gap"], reverse=True)


def calculate_viewability_impact_on_ecpm(viewability_pct: float, current_ecpm: float) -> Dict:
    target = 70.0
    if viewability_pct >= target:
        return {"current_ecpm": current_ecpm, "projected_ecpm": current_ecpm, "uplift": 0}
    uplift_factor = (target / max(viewability_pct, 1)) * 0.30
    projected = current_ecpm * (1 + uplift_factor)
    return {
        "current_viewability": viewability_pct, "target_viewability": target,
        "current_ecpm": current_ecpm, "projected_ecpm": round(projected, 4),
        "uplift_pct": round(uplift_factor * 100, 2),
    }
