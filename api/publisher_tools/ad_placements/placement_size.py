# api/publisher_tools/ad_placements/placement_size.py
"""Placement Size — Size management and responsive breakpoints."""
from typing import Dict, Tuple


RESPONSIVE_BREAKPOINTS = {
    "mobile":  {"max_width": 767, "ad_sizes": ["320x50", "300x250"]},
    "tablet":  {"min_width": 768,  "max_width": 1023, "ad_sizes": ["728x90", "300x250"]},
    "desktop": {"min_width": 1024, "ad_sizes": ["728x90", "970x250", "300x250", "160x600"]},
}

SIZE_FLOOR_PRICE_MULTIPLIERS = {
    "970x250": 2.0,
    "728x90":  1.5,
    "300x600": 1.8,
    "300x250": 1.0,
    "160x600": 0.9,
    "320x50":  0.6,
    "300x50":  0.5,
}


def get_recommended_sizes_for_position(position: str) -> list:
    recommendations = {
        "above_fold":    ["728x90", "970x250", "320x50"],
        "header":        ["728x90", "970x90"],
        "sidebar_right": ["300x250", "300x600", "160x600"],
        "sidebar_left":  ["300x250", "160x600"],
        "in_content":    ["300x250", "336x280"],
        "between_posts": ["300x250", "728x90"],
        "sticky_bottom": ["320x50", "728x90"],
        "footer":        ["728x90", "300x250"],
    }
    return recommendations.get(position, ["300x250"])


def get_size_ecpm_multiplier(size_string: str) -> float:
    return SIZE_FLOOR_PRICE_MULTIPLIERS.get(size_string, 1.0)


def parse_size_string(size_str: str) -> Tuple[int, int]:
    """'300x250' → (300, 250)"""
    try:
        w, h = size_str.split("x")
        return int(w), int(h)
    except Exception:
        return (0, 0)


def get_responsive_config(width: int = None, height: int = None) -> Dict:
    """Responsive ad config generate করে।"""
    return {
        "is_responsive": True,
        "breakpoints": RESPONSIVE_BREAKPOINTS,
        "fallback_size": {"width": width or 300, "height": height or 250},
    }
