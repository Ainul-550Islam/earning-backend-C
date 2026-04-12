# api/publisher_tools/ad_placements/placement_position.py
"""Placement Position — Position scoring and optimization."""
from typing import Dict, List


POSITION_SCORES = {
    "above_fold":    100,
    "header":        95,
    "in_content":    90,
    "sticky_top":    88,
    "between_posts": 85,
    "sticky_bottom": 80,
    "popup":         75,
    "sidebar_left":  65,
    "sidebar_right": 60,
    "below_fold":    45,
    "footer":        35,
}

POSITION_VIEWABILITY_BENCHMARKS = {
    "above_fold":    85, "header": 82, "in_content": 78,
    "sticky_top":    85, "between_posts": 72, "sticky_bottom": 68,
    "popup":         65, "sidebar_right": 55, "sidebar_left": 52,
    "below_fold":    42, "footer": 38,
}

MOBILE_BEST_POSITIONS    = ["sticky_bottom", "in_content", "between_posts", "above_fold"]
DESKTOP_BEST_POSITIONS   = ["above_fold", "sidebar_right", "in_content", "header"]
APP_BEST_POSITIONS       = ["level_end", "app_start", "pause_menu", "in_feed"]


def get_position_score(position: str) -> int:
    return POSITION_SCORES.get(position, 50)


def get_viewability_benchmark(position: str) -> int:
    return POSITION_VIEWABILITY_BENCHMARKS.get(position, 50)


def rank_positions_by_performance(positions: List[str]) -> List[Dict]:
    return sorted(
        [{"position": p, "score": get_position_score(p), "viewability_benchmark": get_viewability_benchmark(p)} for p in positions],
        key=lambda x: x["score"], reverse=True
    )


def suggest_better_position(current_position: str, inventory_type: str = "site") -> str:
    if inventory_type == "app":
        better = [p for p in APP_BEST_POSITIONS if get_position_score(p) > get_position_score(current_position)]
    else:
        better = [p for p in DESKTOP_BEST_POSITIONS if get_position_score(p) > get_position_score(current_position)]
    return better[0] if better else current_position
