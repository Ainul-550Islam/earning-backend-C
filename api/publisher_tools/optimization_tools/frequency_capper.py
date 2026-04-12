# api/publisher_tools/optimization_tools/frequency_capper.py
"""Frequency Capper — Optimal frequency capping for better UX and eCPM."""
from decimal import Decimal
from typing import Dict


OPTIMAL_FREQUENCY_CAPS = {
    "banner":       {"per_day": 10, "per_session": 3},
    "interstitial": {"per_day": 3,  "per_session": 2},
    "rewarded_video":{"per_day": 5, "per_session": 3},
    "native":       {"per_day": 8,  "per_session": 4},
    "offerwall":    {"per_day": 2,  "per_session": 1},
    "video":        {"per_day": 5,  "per_session": 2},
}


def get_recommended_frequency_cap(ad_format: str) -> Dict:
    return OPTIMAL_FREQUENCY_CAPS.get(ad_format, {"per_day": 5, "per_session": 2})


def analyze_frequency_caps(publisher) -> Dict:
    from api.publisher_tools.models import AdUnit
    from api.publisher_tools.ad_unit_management.ad_unit_frequency import FrequencyCap
    units = AdUnit.objects.filter(publisher=publisher, status="active")
    over_capped = []
    under_capped = []
    for unit in units:
        caps = FrequencyCap.objects.filter(ad_unit=unit, is_active=True)
        recommended = get_recommended_frequency_cap(unit.format)
        if not caps.exists():
            under_capped.append({"unit_id": unit.unit_id, "format": unit.format, "issue": "no_frequency_cap", "recommended": recommended})
        else:
            day_cap = caps.filter(window_type="day").first()
            if day_cap and day_cap.max_count > recommended["per_day"] * 2:
                over_capped.append({"unit_id": unit.unit_id, "current": day_cap.max_count, "recommended": recommended["per_day"]})
    return {
        "over_capped": over_capped, "under_capped": under_capped,
        "recommendation": "Set frequency caps to reduce ad fatigue and improve CTR",
    }


def estimate_ctr_improvement(current_frequency: int, recommended_frequency: int) -> float:
    if current_frequency <= recommended_frequency:
        return 0.0
    reduction = (current_frequency - recommended_frequency) / current_frequency
    return round(reduction * 15, 2)
