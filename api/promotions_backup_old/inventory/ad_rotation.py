# =============================================================================
# api/promotions/inventory/ad_rotation.py
# Ad Rotation — Multiple ads পরিবর্তন করে দেখায়
# Frequency cap ও performance-based rotation
# =============================================================================

import logging
import random
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.ad_rotation')

CACHE_PREFIX_ROT = 'inv:rot:{}'


class RotationStrategy(str, Enum):
    ROUND_ROBIN     = 'round_robin'      # সমান সুযোগ
    WEIGHTED        = 'weighted'         # Bid/performance অনুযায়ী
    PERFORMANCE     = 'performance'      # Best performing ads বেশি দেখায়
    RANDOM          = 'random'           # Random
    SEQUENTIAL      = 'sequential'       # Order অনুযায়ী


@dataclass
class RotationResult:
    selected_campaign_id: int
    strategy_used:        str
    rotation_count:       int     # এই campaign কতবার দেখানো হয়েছে
    total_in_pool:        int


class AdRotationEngine:
    """
    Ad rotation management।

    Features:
    1. Multiple rotation strategies
    2. Performance-weighted rotation (better CTR → more impressions)
    3. A/B test rotation
    4. Fair distribution (no campaign starved)
    5. Rotation analytics
    """

    def select_ad(
        self,
        slot_id:      str,
        campaign_pool: list,   # [{'id': 1, 'bid': 0.05, 'ctr': 0.02, 'weight': 1.0}]
        strategy:     RotationStrategy = RotationStrategy.WEIGHTED,
        user_context: dict = None,
    ) -> Optional[RotationResult]:
        """Campaign pool থেকে একটি ad select করে।"""
        if not campaign_pool:
            return None

        if strategy == RotationStrategy.ROUND_ROBIN:
            campaign = self._round_robin(slot_id, campaign_pool)
        elif strategy == RotationStrategy.WEIGHTED:
            campaign = self._weighted_select(campaign_pool)
        elif strategy == RotationStrategy.PERFORMANCE:
            campaign = self._performance_select(campaign_pool)
        elif strategy == RotationStrategy.RANDOM:
            campaign = random.choice(campaign_pool)
        else:  # SEQUENTIAL
            campaign = self._sequential(slot_id, campaign_pool)

        # Rotation count update
        count_key = CACHE_PREFIX_ROT.format(f'count:{slot_id}:{campaign["id"]}')
        count     = (cache.get(count_key) or 0) + 1
        cache.set(count_key, count, timeout=3600)

        return RotationResult(
            selected_campaign_id = campaign['id'],
            strategy_used        = strategy.value,
            rotation_count       = count,
            total_in_pool        = len(campaign_pool),
        )

    def update_performance(self, campaign_id: int, slot_id: str, clicked: bool, converted: bool) -> None:
        """Ad performance update করে।"""
        perf_key = CACHE_PREFIX_ROT.format(f'perf:{campaign_id}:{slot_id}')
        perf     = cache.get(perf_key) or {'impressions': 0, 'clicks': 0, 'conversions': 0}
        perf['impressions'] += 1
        if clicked:    perf['clicks'] += 1
        if converted:  perf['conversions'] += 1
        cache.set(perf_key, perf, timeout=86400)

    def get_performance_score(self, campaign_id: int, slot_id: str) -> float:
        """Campaign performance score (0.0 - 1.0)।"""
        perf_key = CACHE_PREFIX_ROT.format(f'perf:{campaign_id}:{slot_id}')
        perf     = cache.get(perf_key) or {'impressions': 0, 'clicks': 0, 'conversions': 0}
        impr     = perf['impressions']
        if impr == 0:
            return 0.5  # New campaign — neutral score
        ctr    = perf['clicks'] / impr
        cvr    = perf['conversions'] / max(perf['clicks'], 1)
        return min(1.0, ctr * 0.6 + cvr * 0.4)

    # ── Strategies ────────────────────────────────────────────────────────────

    def _round_robin(self, slot_id: str, pool: list) -> dict:
        idx_key = CACHE_PREFIX_ROT.format(f'rr_idx:{slot_id}')
        idx     = cache.get(idx_key) or 0
        selected = pool[idx % len(pool)]
        cache.set(idx_key, (idx + 1) % len(pool), timeout=3600)
        return selected

    def _weighted_select(self, pool: list) -> dict:
        """Bid amount weighted random selection।"""
        weights = [float(c.get('bid', 1.0)) for c in pool]
        total   = sum(weights)
        r       = random.uniform(0, total)
        cumul   = 0
        for c, w in zip(pool, weights):
            cumul += w
            if r <= cumul:
                return c
        return pool[-1]

    def _performance_select(self, pool: list) -> dict:
        """Performance score weighted selection।"""
        scored = [(c, c.get('performance_score', 0.5)) for c in pool]
        total  = sum(s for _, s in scored)
        if total == 0:
            return random.choice(pool)
        r      = random.uniform(0, total)
        cumul  = 0
        for c, s in scored:
            cumul += s
            if r <= cumul:
                return c
        return pool[-1]

    def _sequential(self, slot_id: str, pool: list) -> dict:
        """Sequential selection by campaign_id order।"""
        sorted_pool = sorted(pool, key=lambda c: c['id'])
        return self._round_robin(slot_id, sorted_pool)
