# =============================================================================
# api/promotions/bidding/auction_logic.py
# Auction Engine — GSP / VCG / First-Price mechanisms
# Campaign slot এর জন্য real-time auction পরিচালনা করে
# =============================================================================

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('bidding.auction')

CACHE_PREFIX_AUCTION = 'bid:auction:{}'


class AuctionType(str, Enum):
    GSP         = 'gsp'
    VCG         = 'vcg'
    FIRST_PRICE = 'first_price'


@dataclass
class Bid:
    campaign_id:      int
    advertiser_id:    int
    bid_amount_usd:   Decimal
    quality_score:    float              # 0.0 - 1.0
    effective_bid:    Decimal = None     # bid × quality_score
    budget_remaining: Decimal = Decimal('0')
    priority:         int     = 0
    metadata:         dict    = field(default_factory=dict)

    def __post_init__(self):
        if self.effective_bid is None:
            self.effective_bid = self.bid_amount_usd * Decimal(str(self.quality_score))


@dataclass
class AuctionSlot:
    slot_id:         str
    platform:        str
    category:        str
    country_code:    str
    position:        int
    position_factor: float
    floor_price_usd: Decimal = Decimal('0.01')


@dataclass
class AuctionResult:
    slot_id:          str
    auction_type:     str
    winner:           Optional[Bid]
    winner_price_usd: Decimal
    all_bids:         list
    losers:           list
    auction_ms:       float
    revenue_usd:      Decimal
    floor_applied:    bool
    timestamp:        float = field(default_factory=time.time)


@dataclass
class MultiSlotAuctionResult:
    slot_assignments: list
    total_revenue:    Decimal
    auction_ms:       float
    unfilled_slots:   list


class AuctionEngine:
    """
    Multi-mechanism auction engine।

    GSP (Generalized Second Price):
    - Effective bid = bid_amount × quality_score
    - Winner pays next highest effective_bid / own quality_score + ε
    - Google AdWords এর মতো mechanism

    VCG (Vickrey-Clarke-Groves):
    - Truthful dominant strategy
    - Winner pays social welfare externality
    - Incentive-compatible

    First Price:
    - Winner pays own bid
    - RTB (Real-Time Bidding) এ common
    """

    def run_auction(
        self,
        slot:         AuctionSlot,
        bids:         list,
        auction_type: AuctionType = AuctionType.GSP,
    ) -> AuctionResult:
        start = time.monotonic()
        valid = self._filter_valid_bids(bids, slot)

        if not valid:
            return AuctionResult(
                slot_id=slot.slot_id, auction_type=auction_type.value,
                winner=None, winner_price_usd=Decimal('0'),
                all_bids=bids, losers=bids,
                auction_ms=round((time.monotonic() - start) * 1000, 2),
                revenue_usd=Decimal('0'), floor_applied=False,
            )

        ranked = self._rank_bids(valid)

        if auction_type == AuctionType.GSP:
            winner, price = self._gsp_pricing(ranked, slot)
        elif auction_type == AuctionType.VCG:
            winner, price = self._vcg_pricing(ranked, slot)
        else:
            winner, price = ranked[0], ranked[0].effective_bid

        floor_applied = False
        if price < slot.floor_price_usd:
            price = slot.floor_price_usd
            floor_applied = True

        price  = price * Decimal(str(slot.position_factor))
        losers = [b for b in ranked if b.campaign_id != winner.campaign_id]

        logger.info(
            f'Auction slot={slot.slot_id} winner=camp_{winner.campaign_id} '
            f'price=${price:.4f} type={auction_type.value}'
        )
        return AuctionResult(
            slot_id=slot.slot_id, auction_type=auction_type.value,
            winner=winner, winner_price_usd=price,
            all_bids=bids, losers=losers,
            auction_ms=round((time.monotonic() - start) * 1000, 2),
            revenue_usd=price, floor_applied=floor_applied,
        )

    def run_multi_slot_auction(
        self, slots: list, bids: list, auction_type: AuctionType = AuctionType.GSP,
    ) -> MultiSlotAuctionResult:
        start        = time.monotonic()
        assignments  = []
        total_rev    = Decimal('0')
        used         = set()
        unfilled     = []

        for slot in sorted(slots, key=lambda s: s.position):
            available = [b for b in bids if b.campaign_id not in used]
            result    = self.run_auction(slot, available, auction_type)

            if result.winner:
                assignments.append({
                    'slot_id':       slot.slot_id,
                    'campaign_id':   result.winner.campaign_id,
                    'advertiser_id': result.winner.advertiser_id,
                    'price_usd':     result.winner_price_usd,
                    'quality_score': result.winner.quality_score,
                    'position':      slot.position,
                })
                used.add(result.winner.campaign_id)
                total_rev += result.winner_price_usd
            else:
                unfilled.append(slot.slot_id)

        return MultiSlotAuctionResult(
            slot_assignments=assignments, total_revenue=total_rev,
            auction_ms=round((time.monotonic() - start) * 1000, 2),
            unfilled_slots=unfilled,
        )

    # ── Pricing ───────────────────────────────────────────────────────────────

    def _gsp_pricing(self, ranked: list, slot: AuctionSlot):
        winner  = ranked[0]
        epsilon = Decimal('0.001')
        if len(ranked) >= 2:
            price = (ranked[1].effective_bid / Decimal(str(max(winner.quality_score, 0.01)))) + epsilon
        else:
            price = slot.floor_price_usd
        return winner, price

    def _vcg_pricing(self, ranked: list, slot: AuctionSlot):
        winner = ranked[0]
        others = ranked[1:]
        welfare_loss = others[0].effective_bid if others else Decimal('0')
        return winner, max(welfare_loss, slot.floor_price_usd)

    def _filter_valid_bids(self, bids: list, slot: AuctionSlot) -> list:
        return [
            b for b in bids
            if b.budget_remaining >= slot.floor_price_usd
            and b.effective_bid >= slot.floor_price_usd * Decimal('0.5')
        ]

    @staticmethod
    def _rank_bids(bids: list) -> list:
        return sorted(bids, key=lambda b: (float(b.effective_bid), b.quality_score, b.priority), reverse=True)


class QualityScoreCalculator:
    """Campaign quality score — CTR + Relevance + Approval rate।"""

    WEIGHTS = {'expected_ctr': 0.45, 'ad_relevance': 0.30, 'historical_approve': 0.25}

    def calculate(
        self, campaign_id: int, platform: str = '', category: str = '',
        historical_approve_rate: float = 0.5,
        historical_ctr: float = 0.02,
        ad_relevance_score: float = 0.7,
    ) -> float:
        ctr_score = min(1.0, historical_ctr / 0.05)
        quality   = (
            ctr_score * self.WEIGHTS['expected_ctr'] +
            ad_relevance_score * self.WEIGHTS['ad_relevance'] +
            historical_approve_rate * self.WEIGHTS['historical_approve']
        )
        cache.set(CACHE_PREFIX_AUCTION.format(f'qs:{campaign_id}'), round(quality, 4), timeout=3600)
        return round(quality, 4)

    def bulk_calculate(self, campaigns: list) -> dict:
        return {c['id']: self.calculate(
            c['id'], c.get('platform', ''), c.get('category', ''),
            c.get('approve_rate', 0.5), c.get('ctr', 0.02), c.get('relevance', 0.7),
        ) for c in campaigns}
