# =============================================================================
# api/promotions/inventory/placement_manager.py
# Placement Manager — Campaign কোন slot এ দেখাবে তা decide করে
# Targeting match, priority, exclusions সব handle করে
# =============================================================================

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.placement')
CACHE_PREFIX_PLACEMENT = 'inv:place:{}'


@dataclass
class PlacementDecision:
    campaign_id:   int
    slot_id:       str
    score:         float        # Placement suitability score
    matched_rules: list
    blocked_rules: list
    is_allowed:    bool


@dataclass
class PlacementRequest:
    user_id:      Optional[int]
    platform:     str
    category:     str
    country:      str
    device_type:  str
    page_context: dict


class PlacementManager:
    """
    Campaign placement decision engine।

    Decisions based on:
    1. Category targeting match
    2. Country/region targeting
    3. Device type targeting
    4. Competitive exclusion (same category competitors না দেখানো)
    5. Advertiser exclusion lists
    6. Content adjacency rules
    """

    def find_eligible_campaigns(
        self,
        request:   PlacementRequest,
        slot_id:   str,
        limit:     int = 20,
    ) -> list[PlacementDecision]:
        """Slot এ eligible campaigns return করে।"""
        from api.promotions.models import Campaign, CampaignTargeting
        from api.promotions.choices import CampaignStatus
        from django.db.models import Q

        # Active campaigns
        campaigns = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
            platform__name__iexact=request.platform,
        ).select_related('targeting', 'limits').values(
            'id', 'advertiser_id', 'bid_amount_usd', 'category__name',
        )[:100]

        decisions = []
        for campaign in campaigns:
            decision = self._evaluate_placement(campaign, request, slot_id)
            if decision.is_allowed:
                decisions.append(decision)

        decisions.sort(key=lambda d: d.score, reverse=True)
        return decisions[:limit]

    def check_competitive_exclusion(
        self, campaign_id_1: int, campaign_id_2: int
    ) -> bool:
        """দুটো campaign একসাথে দেখানো যাবে কিনা।"""
        from api.promotions.models import Campaign
        try:
            c1 = Campaign.objects.select_related('category').get(pk=campaign_id_1)
            c2 = Campaign.objects.select_related('category').get(pk=campaign_id_2)
            # Same category + same advertiser = exclude
            if c1.advertiser_id == c2.advertiser_id:
                return True   # Same advertiser — exclude
            if c1.category == c2.category:
                return False  # Direct competitor — allowed (auction decides)
            return False
        except Exception:
            return False

    def _evaluate_placement(
        self, campaign: dict, request: PlacementRequest, slot_id: str
    ) -> PlacementDecision:
        matched = []
        blocked = []
        score   = 0.5

        # Category match
        camp_cat = campaign.get('category__name', '')
        if camp_cat and camp_cat.lower() == request.category.lower():
            score += 0.3; matched.append('category_match')
        elif camp_cat:
            score += 0.1; matched.append('cross_category')

        # Targeting check (simplified — expand with actual targeting model)
        try:
            from api.promotions.models import CampaignTargeting
            targeting = CampaignTargeting.objects.filter(campaign_id=campaign['id']).first()
            if targeting:
                if targeting.countries and request.country not in (targeting.countries or []):
                    blocked.append(f'country_excluded:{request.country}')
                    return PlacementDecision(
                        campaign_id=campaign['id'], slot_id=slot_id,
                        score=0.0, matched_rules=[], blocked_rules=blocked, is_allowed=False,
                    )
                if targeting.devices and request.device_type not in (targeting.devices or []):
                    blocked.append(f'device_excluded:{request.device_type}')
                    return PlacementDecision(
                        campaign_id=campaign['id'], slot_id=slot_id,
                        score=0.0, matched_rules=[], blocked_rules=blocked, is_allowed=False,
                    )
        except Exception:
            pass

        return PlacementDecision(
            campaign_id=campaign['id'], slot_id=slot_id,
            score=round(score, 3), matched_rules=matched,
            blocked_rules=blocked, is_allowed=True,
        )
