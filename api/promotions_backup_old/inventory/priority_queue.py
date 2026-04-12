# =============================================================================
# api/promotions/inventory/priority_queue.py
# Priority Queue — Campaign serving order management
# Premium campaigns আগে serve করা, guaranteed delivery ensure করা
# =============================================================================

import heapq
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntEnum
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.priority_queue')
CACHE_PREFIX_PQ = 'inv:pq:{}'


class CampaignPriority(IntEnum):
    GUARANTEED  = 1    # Guaranteed delivery — admin direct deal
    PREMIUM     = 2    # High budget premium campaigns
    STANDARD    = 3    # Regular auction campaigns
    REMNANT     = 4    # Backfill — remaining inventory


@dataclass
class QueuedCampaign:
    """Priority queue এ একটি campaign entry।"""
    priority:     int
    campaign_id:  int
    advertiser_id: int
    bid_usd:      Decimal
    quality_score: float
    target_impressions: int   # Guaranteed delivery এর জন্য
    delivered:    int = 0
    created_at:   float = field(default_factory=time.time)

    def __lt__(self, other):
        # heapq comparison — lower priority number = higher importance
        if self.priority != other.priority:
            return self.priority < other.priority
        return float(self.bid_usd) > float(other.bid_usd)  # Higher bid wins tie


class InventoryPriorityQueue:
    """
    Campaign serving priority queue।

    Priority order:
    1. GUARANTEED (1): Direct deal, must deliver
    2. PREMIUM (2): High-value auction winners
    3. STANDARD (3): Regular campaigns
    4. REMNANT (4): Backfill/house ads

    Within same priority: Bid amount decides।
    """

    def __init__(self, slot_id: str):
        self.slot_id = slot_id
        self._queue: list[QueuedCampaign] = []
        self._load_from_cache()

    def enqueue(self, campaign: QueuedCampaign) -> None:
        """Campaign queue এ add করে।"""
        heapq.heappush(self._queue, campaign)
        self._save_to_cache()
        logger.debug(f'Queued: campaign={campaign.campaign_id} priority={campaign.priority} slot={self.slot_id}')

    def dequeue(self) -> Optional[QueuedCampaign]:
        """Next campaign return করে।"""
        while self._queue:
            campaign = heapq.heappop(self._queue)
            # Budget/delivery check
            if self._is_still_eligible(campaign):
                self._save_to_cache()
                return campaign
        return None

    def peek(self) -> Optional[QueuedCampaign]:
        """Next campaign দেখে কিন্তু remove করে না।"""
        return self._queue[0] if self._queue else None

    def get_next_n(self, n: int) -> list[QueuedCampaign]:
        """Top N campaigns return করে।"""
        sorted_q = sorted(self._queue)
        return sorted_q[:n]

    def remove_campaign(self, campaign_id: int) -> bool:
        """Specific campaign remove করে।"""
        original_len = len(self._queue)
        self._queue  = [c for c in self._queue if c.campaign_id != campaign_id]
        heapq.heapify(self._queue)
        self._save_to_cache()
        return len(self._queue) < original_len

    def size(self) -> int:
        return len(self._queue)

    def get_priority_breakdown(self) -> dict:
        """Priority tier wise count।"""
        breakdown = {p.name: 0 for p in CampaignPriority}
        for c in self._queue:
            tier_name = CampaignPriority(c.priority).name
            breakdown[tier_name] = breakdown.get(tier_name, 0) + 1
        return breakdown

    # ── Cache persistence ─────────────────────────────────────────────────────

    def _save_to_cache(self) -> None:
        data = [
            {
                'priority': c.priority, 'campaign_id': c.campaign_id,
                'advertiser_id': c.advertiser_id, 'bid_usd': str(c.bid_usd),
                'quality_score': c.quality_score,
                'target_impressions': c.target_impressions,
                'delivered': c.delivered, 'created_at': c.created_at,
            }
            for c in self._queue
        ]
        cache.set(CACHE_PREFIX_PQ.format(self.slot_id), data, timeout=300)

    def _load_from_cache(self) -> None:
        data = cache.get(CACHE_PREFIX_PQ.format(self.slot_id)) or []
        self._queue = [
            QueuedCampaign(
                priority=d['priority'], campaign_id=d['campaign_id'],
                advertiser_id=d['advertiser_id'], bid_usd=Decimal(d['bid_usd']),
                quality_score=d['quality_score'],
                target_impressions=d['target_impressions'],
                delivered=d['delivered'], created_at=d['created_at'],
            )
            for d in data
        ]
        heapq.heapify(self._queue)

    def _is_still_eligible(self, campaign: QueuedCampaign) -> bool:
        """Campaign এখনও eligible কিনা।"""
        try:
            from api.promotions.models import Campaign
            from api.promotions.choices import CampaignStatus
            c = Campaign.objects.filter(
                pk=campaign.campaign_id,
                status=CampaignStatus.ACTIVE,
            ).values('spent_usd', 'total_budget_usd').first()
            if not c:
                return False
            return Decimal(str(c['spent_usd'])) < Decimal(str(c['total_budget_usd']))
        except Exception:
            return True  # Default allow
