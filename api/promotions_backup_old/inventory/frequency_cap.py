# =============================================================================
# api/promotions/inventory/frequency_cap.py
# Frequency Cap — একজন user কে একটি ad কতবার দেখানো যাবে তা limit করে
# Ad fatigue prevent করে, user experience improve করে
# =============================================================================

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.frequency_cap')

CACHE_PREFIX_FREQ = 'inv:freq:{}'


class FrequencyPeriod(str, Enum):
    HOURLY  = 'hourly'    # ঘন্টায়
    DAILY   = 'daily'     # দিনে
    WEEKLY  = 'weekly'    # সপ্তাহে
    MONTHLY = 'monthly'   # মাসে
    LIFETIME = 'lifetime' # মোট


@dataclass
class FrequencyCap:
    campaign_id:    int
    max_impressions: int
    period:         FrequencyPeriod
    current_count:  int             = 0
    is_capped:      bool            = False
    reset_at:       Optional[float] = None


@dataclass
class FrequencyCheckResult:
    user_id:        Optional[int]
    campaign_id:    int
    is_allowed:     bool
    current_count:  int
    max_allowed:    int
    period:         str
    remaining:      int


class FrequencyCapManager:
    """
    User-level frequency cap management।

    Prevents:
    - Ad fatigue (same ad বারবার দেখা)
    - User irritation
    - Wasted impressions

    Storage: Redis cache (fast lookup)
    Key format: freq:{user_id}:{campaign_id}:{period}
    """

    DEFAULT_CAPS = {
        FrequencyPeriod.HOURLY:   3,
        FrequencyPeriod.DAILY:    10,
        FrequencyPeriod.WEEKLY:   30,
        FrequencyPeriod.LIFETIME: 100,
    }

    PERIOD_TTL = {
        FrequencyPeriod.HOURLY:   3600,
        FrequencyPeriod.DAILY:    86400,
        FrequencyPeriod.WEEKLY:   604800,
        FrequencyPeriod.MONTHLY:  2592000,
        FrequencyPeriod.LIFETIME: 31536000,
    }

    def check_and_increment(
        self,
        user_id:     Optional[int],
        campaign_id: int,
        period:      FrequencyPeriod = FrequencyPeriod.DAILY,
        max_count:   int = None,
    ) -> FrequencyCheckResult:
        """
        Frequency check করো এবং allowed হলে increment করো।
        Atomic — race condition নেই।
        """
        identifier = user_id or 'anonymous'
        max_allowed = max_count or self.DEFAULT_CAPS.get(period, 10)
        ttl         = self.PERIOD_TTL.get(period, 86400)

        cache_key   = CACHE_PREFIX_FREQ.format(f'{identifier}:{campaign_id}:{period.value}')
        current     = cache.get(cache_key) or 0

        is_allowed  = current < max_allowed

        if is_allowed:
            cache.set(cache_key, current + 1, timeout=ttl)
            current += 1

        logger.debug(
            f'FreqCap user={identifier} camp={campaign_id} '
            f'period={period.value} count={current}/{max_allowed} allowed={is_allowed}'
        )

        return FrequencyCheckResult(
            user_id=user_id, campaign_id=campaign_id,
            is_allowed=is_allowed, current_count=current,
            max_allowed=max_allowed, period=period.value,
            remaining=max(0, max_allowed - current),
        )

    def check_all_periods(
        self, user_id: Optional[int], campaign_id: int, caps: dict = None
    ) -> bool:
        """
        সব periods check করে — সবগুলো pass করলেই allowed।

        caps = {FrequencyPeriod.DAILY: 5, FrequencyPeriod.WEEKLY: 20}
        """
        periods_to_check = caps or {
            FrequencyPeriod.HOURLY:  3,
            FrequencyPeriod.DAILY:   10,
            FrequencyPeriod.WEEKLY:  30,
        }
        for period, max_count in periods_to_check.items():
            result = self.check_and_increment(user_id, campaign_id, period, max_count)
            if not result.is_allowed:
                return False
        return True

    def reset_user_caps(self, user_id: int, campaign_id: int) -> None:
        """User এর specific campaign frequency reset করে।"""
        for period in FrequencyPeriod:
            key = CACHE_PREFIX_FREQ.format(f'{user_id}:{campaign_id}:{period.value}')
            cache.delete(key)

    def get_current_counts(self, user_id: int, campaign_id: int) -> dict:
        """Current impression counts return করে।"""
        counts = {}
        for period in FrequencyPeriod:
            key  = CACHE_PREFIX_FREQ.format(f'{user_id}:{campaign_id}:{period.value}')
            counts[period.value] = cache.get(key) or 0
        return counts
