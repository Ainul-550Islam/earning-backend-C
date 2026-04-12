# api/publisher_tools/optimization_tools/ad_load_optimizer.py
"""Ad Load Optimizer — Optimal ad density per page/screen."""
from typing import Dict, List


AD_DENSITY_RECOMMENDATIONS = {
    "news":         {"max_ads_per_page": 4, "min_content_to_ad_ratio": 70},
    "blog":         {"max_ads_per_page": 3, "min_content_to_ad_ratio": 75},
    "ecommerce":    {"max_ads_per_page": 2, "min_content_to_ad_ratio": 80},
    "gaming":       {"max_ads_per_page": 5, "min_content_to_ad_ratio": 60},
    "entertainment":{"max_ads_per_page": 4, "min_content_to_ad_ratio": 65},
    "default":      {"max_ads_per_page": 3, "min_content_to_ad_ratio": 70},
}


def analyze_ad_load(site) -> Dict:
    """Site-এর ad load analyze করে।"""
    from api.publisher_tools.models import AdUnit, AdPlacement
    active_units = AdUnit.objects.filter(site=site, status="active").count()
    active_placements = AdPlacement.objects.filter(ad_unit__site=site, is_active=True).count()
    recommendations = AD_DENSITY_RECOMMENDATIONS.get(site.category, AD_DENSITY_RECOMMENDATIONS["default"])
    max_ads = recommendations["max_ads_per_page"]
    issues = []
    if active_placements > max_ads:
        issues.append(f"Too many active placements ({active_placements}). Recommended max: {max_ads}.")
    if active_units == 0:
        issues.append("No active ad units. Create at least one ad unit.")
    return {
        "site_id": site.site_id,
        "active_units": active_units,
        "active_placements": active_placements,
        "max_recommended": max_ads,
        "ad_density_score": max(0, 100 - max(0, active_placements - max_ads) * 20),
        "issues": issues,
        "recommendations": recommendations,
    }


def get_optimal_ad_unit_count(site_category: str, page_type: str = "article") -> int:
    page_multipliers = {"homepage": 1.0, "article": 1.0, "listing": 0.8, "checkout": 0.3}
    base = AD_DENSITY_RECOMMENDATIONS.get(site_category, AD_DENSITY_RECOMMENDATIONS["default"])["max_ads_per_page"]
    return max(1, round(base * page_multipliers.get(page_type, 1.0)))
