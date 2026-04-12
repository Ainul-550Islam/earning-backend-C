# api/publisher_tools/optimization_tools/audience_optimizer.py
"""Audience Optimizer — Audience-based targeting optimization."""
from typing import Dict, List


AUDIENCE_SEGMENT_VALUES = {
    "high_intent_buyers":   5.0,
    "in_market_auto":       4.5,
    "in_market_finance":    4.0,
    "tech_enthusiasts":     3.5,
    "sports_fans":          2.5,
    "news_readers":         2.0,
    "entertainment_fans":   1.8,
    "general_audience":     1.0,
}


def get_audience_value_recommendations(publisher) -> Dict:
    return {
        "high_value_segments": [
            {"segment": seg, "ecpm_multiplier": mult, "action": f"Add {seg} targeting to floor price rules"}
            for seg, mult in list(AUDIENCE_SEGMENT_VALUES.items())[:5]
        ],
        "recommendation": "Use Google DFP or Prebid audiences for first-party data targeting",
    }


def estimate_audience_targeting_revenue_lift(publisher, current_ecpm: float) -> Dict:
    potential_ecpm = current_ecpm * 2.5
    return {
        "current_ecpm": current_ecpm,
        "potential_ecpm_with_targeting": round(potential_ecpm, 4),
        "estimated_lift_pct": 150.0,
        "recommended_actions": [
            "Enable Google first-party audiences",
            "Implement Prebid user ID modules",
            "Add contextual targeting keywords",
        ],
    }


def analyze_audience_demographics(site) -> Dict:
    from api.publisher_tools.site_management.site_analytics import SiteAudienceProfile
    from django.utils import timezone
    today = timezone.now().date().replace(day=1)
    profile = SiteAudienceProfile.objects.filter(site=site, month=today).first()
    if not profile:
        return {"status": "no_data", "recommendation": "Add Google Analytics integration for audience data"}
    primary_age = max(
        [("18-24", float(profile.age_18_24_pct)), ("25-34", float(profile.age_25_34_pct)),
         ("35-44", float(profile.age_35_44_pct)), ("45-54", float(profile.age_45_54_pct))],
        key=lambda x: x[1]
    )[0]
    return {
        "primary_age_group": primary_age,
        "primary_device": profile.primary_device,
        "gender_split": {"male": float(profile.male_pct), "female": float(profile.female_pct)},
        "top_interests": profile.top_interests[:5],
        "monetization_tip": f"Audience is primarily {primary_age} on {profile.primary_device}. Optimize for this segment.",
    }
