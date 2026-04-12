# api/publisher_tools/ad_unit_management/ad_unit_placement.py
"""Ad Unit Placement helper — Placement recommendations and analysis."""
from typing import List, Dict
from django.utils.translation import gettext_lazy as _


PLACEMENT_RECOMMENDATIONS = {
    "banner": ["above_fold", "in_content", "sticky_bottom"],
    "leaderboard": ["above_fold", "header"],
    "rectangle": ["sidebar_right", "in_content", "between_posts"],
    "interstitial": ["app_start", "level_end", "exit_intent"],
    "rewarded_video": ["level_end", "pause_menu"],
    "native": ["in_content", "between_posts", "in_feed"],
    "offerwall": ["pause_menu", "level_end", "app_start"],
    "video": ["in_content", "above_fold", "sticky_top"],
}

PLACEMENT_VIEWABILITY_BENCHMARKS = {
    "above_fold":    85,
    "header":        80,
    "in_content":    75,
    "between_posts": 70,
    "sticky_bottom": 65,
    "sidebar_right": 55,
    "sidebar_left":  55,
    "below_fold":    40,
    "footer":        35,
    "popup":         60,
}


def get_recommendations(ad_format: str) -> List[str]:
    """Ad format-এর জন্য recommended positions."""
    return PLACEMENT_RECOMMENDATIONS.get(ad_format, ["above_fold", "in_content"])


def get_viewability_benchmark(position: str) -> int:
    """Position-এর industry viewability benchmark."""
    return PLACEMENT_VIEWABILITY_BENCHMARKS.get(position, 50)


def analyze_placement_performance(placements) -> List[Dict]:
    """Placements analyze করে optimization suggestions দেয়।"""
    results = []
    for placement in placements:
        benchmark = get_viewability_benchmark(placement.position)
        actual = float(placement.avg_viewability)
        gap = benchmark - actual
        results.append({
            "placement_id": str(placement.id),
            "name": placement.name,
            "position": placement.position,
            "actual_viewability": actual,
            "benchmark_viewability": benchmark,
            "gap": gap,
            "status": "good" if gap <= 5 else "needs_improvement" if gap <= 20 else "poor",
            "recommendation": f"Move to {get_recommendations(placement.ad_unit.format)[0]}" if gap > 20 else "Maintain current position",
        })
    return sorted(results, key=lambda x: x["gap"], reverse=True)
