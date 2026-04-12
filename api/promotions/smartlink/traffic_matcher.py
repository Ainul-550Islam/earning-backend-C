# =============================================================================
# promotions/smartlink/traffic_matcher.py
# Advanced Traffic Matching — GEO + Device + OS + Browser targeting rules
# =============================================================================
from django.core.cache import cache
import hashlib


class AdvancedTrafficMatcher:
    """Advanced targeting: match visitor to campaign targeting rules."""

    def match_campaign_to_visitor(self, campaign, visitor_profile: dict) -> float:
        """Return match score 0.0 to 1.0 for campaign×visitor."""
        score = 1.0
        # Country targeting
        if hasattr(campaign, 'targeting') and campaign.targeting:
            allowed_countries = campaign.targeting.get('countries', [])
            if allowed_countries and visitor_profile.get('country') not in allowed_countries:
                return 0.0
        # Device targeting
        allowed_devices = getattr(campaign, 'target_devices', [])
        if allowed_devices and visitor_profile.get('device') not in allowed_devices:
            score *= 0.5  # Penalize but don't eliminate
        return score

    def get_visitor_value_score(self, visitor_profile: dict) -> float:
        """Estimate visitor value based on country + device."""
        country_values = {
            'US': 1.0, 'CA': 0.95, 'GB': 0.92, 'AU': 0.90,
            'DE': 0.85, 'FR': 0.82, 'JP': 0.80, 'KR': 0.75,
            'BR': 0.40, 'IN': 0.35, 'BD': 0.30, 'PK': 0.25,
        }
        device_values = {'desktop': 1.0, 'tablet': 0.85, 'mobile': 0.75}
        country_score = country_values.get(visitor_profile.get('country', 'US'), 0.50)
        device_score = device_values.get(visitor_profile.get('device', 'desktop'), 0.75)
        return country_score * device_score
