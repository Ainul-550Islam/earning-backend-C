# =============================================================================
# api/promotions/bidding/bidder_profiles.py
# Bidder Profiles — Advertiser bidding behavior analysis ও strategy
# Historical data থেকে optimal bid strategy suggest করে
# =============================================================================

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('bidding.bidder_profiles')

CACHE_PREFIX_BIDDER = 'bid:profile:{}'
CACHE_TTL_BIDDER    = 3600 * 6   # 6 hours


@dataclass
class BidderProfile:
    advertiser_id:       int
    avg_bid_usd:         Decimal
    max_bid_usd:         Decimal
    min_bid_usd:         Decimal
    win_rate:            float           # 0.0 - 1.0
    avg_cpc_usd:         Decimal         # avg cost per conversion
    total_spend_usd:     Decimal
    total_auctions:      int
    total_wins:          int
    preferred_categories: list
    preferred_platforms:  list
    bidding_style:       str             # aggressive, conservative, balanced
    roi_score:           float           # ROI এর normalized score
    budget_utilization:  float           # daily budget কতটা use করছে


@dataclass
class BidRecommendation:
    campaign_id:      int
    recommended_bid:  Decimal
    confidence:       float
    strategy:         str
    expected_win_rate: float
    expected_cpc:     Decimal
    reasoning:        list[str]


class BidderProfiler:
    """
    Advertiser bidding profile তৈরি ও analyze করে।

    Features:
    1. Historical bid analysis
    2. Optimal bid suggestion
    3. Competitor analysis
    4. Budget allocation recommendation
    """

    def build_profile(self, advertiser_id: int) -> BidderProfile:
        """Advertiser এর bidding profile তৈরি করে।"""
        cache_key = CACHE_PREFIX_BIDDER.format(advertiser_id)
        cached    = cache.get(cache_key)
        if cached:
            return BidderProfile(**cached)

        profile = self._compute_profile(advertiser_id)
        cache.set(cache_key, profile.__dict__, timeout=CACHE_TTL_BIDDER)
        return profile

    def recommend_bid(
        self,
        campaign_id:   int,
        advertiser_id: int,
        slot_context:  dict = None,
    ) -> BidRecommendation:
        """
        Campaign এর জন্য optimal bid recommend করে।

        Args:
            slot_context: {'platform': 'youtube', 'category': 'gaming', 'competition': 5}
        """
        profile   = self.build_profile(advertiser_id)
        ctx       = slot_context or {}
        reasoning = []

        # Base bid = historical avg
        base_bid  = profile.avg_bid_usd

        # Competition factor
        competition = ctx.get('competition', 3)   # number of active bidders
        if competition > 5:
            base_bid  *= Decimal('1.15')
            reasoning.append(f'Competition high ({competition} bidders) — bid +15%')
        elif competition <= 2:
            base_bid  *= Decimal('0.90')
            reasoning.append(f'Low competition — bid -10% to save budget')

        # Win rate adjustment
        if profile.win_rate < 0.2:
            base_bid  *= Decimal('1.20')
            reasoning.append(f'Win rate low ({profile.win_rate:.0%}) — bid +20%')
        elif profile.win_rate > 0.7:
            base_bid  *= Decimal('0.90')
            reasoning.append(f'Win rate high ({profile.win_rate:.0%}) — bid -10% to optimize CPC')

        # Category preference boost
        if ctx.get('category') in profile.preferred_categories:
            base_bid  *= Decimal('1.10')
            reasoning.append('Preferred category — bid +10%')

        # ROI-based cap
        max_roi_bid = profile.avg_cpc_usd * Decimal('2')
        if base_bid > max_roi_bid:
            base_bid  = max_roi_bid
            reasoning.append(f'Capped at 2× avg CPC for ROI protection')

        # Budget safety cap
        base_bid = min(base_bid, profile.max_bid_usd)
        base_bid = max(base_bid, profile.min_bid_usd)

        # Expected win rate at this bid
        exp_win_rate = min(0.9, float(base_bid) / float(max(profile.avg_bid_usd, Decimal('0.01'))) * profile.win_rate)

        strategy = (
            'aggressive'   if exp_win_rate > 0.6 else
            'conservative' if exp_win_rate < 0.3 else
            'balanced'
        )

        return BidRecommendation(
            campaign_id=campaign_id, recommended_bid=base_bid.quantize(Decimal('0.0001')),
            confidence=min(1.0, 0.5 + profile.total_auctions / 1000),
            strategy=strategy, expected_win_rate=round(exp_win_rate, 3),
            expected_cpc=profile.avg_cpc_usd, reasoning=reasoning,
        )

    def analyze_competition(
        self, platform: str, category: str, country: str
    ) -> dict:
        """Market competition analyze করে।"""
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        from django.db.models import Avg, Count, Max, Min

        active_campaigns = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
            platform__name__iexact=platform,
            category__name__iexact=category,
        )
        stats = active_campaigns.aggregate(
            count    = Count('id'),
            avg_bid  = Avg('bid_amount_usd'),
            max_bid  = Max('bid_amount_usd'),
            min_bid  = Min('bid_amount_usd'),
        )
        return {
            'active_bidders': stats['count'] or 0,
            'avg_bid_usd':    float(stats['avg_bid'] or 0),
            'max_bid_usd':    float(stats['max_bid'] or 0),
            'min_bid_usd':    float(stats['min_bid'] or 0),
            'competition_level': (
                'high'   if (stats['count'] or 0) > 10 else
                'medium' if (stats['count'] or 0) > 4 else
                'low'
            ),
        }

    def _compute_profile(self, advertiser_id: int) -> BidderProfile:
        """Database থেকে profile compute করে।"""
        from api.promotions.models import Campaign, AdminCommissionLog, TaskSubmission
        from api.promotions.choices import CampaignStatus, SubmissionStatus
        from django.db.models import Avg, Sum, Count, Max, Min

        campaigns = Campaign.objects.filter(advertiser_id=advertiser_id)

        agg = campaigns.aggregate(
            avg_bid  = Avg('bid_amount_usd'),
            max_bid  = Max('bid_amount_usd'),
            min_bid  = Min('bid_amount_usd'),
            total_sp = Sum('spent_usd'),
        )

        # Win/loss stats from commissions
        total_spend = agg['total_sp'] or Decimal('0')
        campaign_ids = list(campaigns.values_list('id', flat=True))
        total_subs  = TaskSubmission.objects.filter(campaign_id__in=campaign_ids).count()
        approved    = TaskSubmission.objects.filter(
            campaign_id__in=campaign_ids, status=SubmissionStatus.APPROVED
        ).count()

        win_rate = approved / max(total_subs, 1)
        avg_cpc  = (total_spend / max(approved, 1))

        cats     = list(
            campaigns.values_list('category__name', flat=True)
            .distinct()[:5]
        )
        plats    = list(
            campaigns.values_list('platform__name', flat=True)
            .distinct()[:5]
        )

        return BidderProfile(
            advertiser_id        = advertiser_id,
            avg_bid_usd          = Decimal(str(agg['avg_bid'] or '0.05')),
            max_bid_usd          = Decimal(str(agg['max_bid'] or '1.0')),
            min_bid_usd          = Decimal(str(agg['min_bid'] or '0.01')),
            win_rate             = round(win_rate, 3),
            avg_cpc_usd          = avg_cpc,
            total_spend_usd      = total_spend,
            total_auctions       = total_subs,
            total_wins           = approved,
            preferred_categories = [c for c in cats if c],
            preferred_platforms  = [p for p in plats if p],
            bidding_style        = 'aggressive' if win_rate > 0.6 else 'conservative' if win_rate < 0.3 else 'balanced',
            roi_score            = min(1.0, float(approved) / max(float(total_spend) * 10, 1)),
            budget_utilization   = 0.8,  # Simplified
        )
