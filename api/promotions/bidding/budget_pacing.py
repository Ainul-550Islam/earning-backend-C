# =============================================================================
# api/promotions/bidding/budget_pacing.py
# Budget Pacing — দিনের ২৪ ঘন্টায় budget সমানভাবে বিতরণ করে
# Overspend ও underspend দুটোই prevent করে
# =============================================================================

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import math
from datetime import datetime, timezone

from django.core.cache import cache

logger = logging.getLogger('bidding.budget_pacing')

CACHE_PREFIX_PACING = 'bid:pace:{}'
CACHE_TTL_PACING    = 3600


class PacingStrategy(str):
    EVEN       = 'even'         # সমান পরিমাণ প্রতি ঘন্টায়
    FRONTLOAD  = 'frontload'    # সকালে বেশি খরচ
    ACCELERATED = 'accelerated' # যত তাড়াতাড়ি সম্ভব খরচ করো
    DAYPARTING = 'dayparting'   # নির্দিষ্ট সময়ে বেশি


@dataclass
class PacingDecision:
    campaign_id:     int
    should_bid:      bool
    throttle_rate:   float      # 0.0 = বিড করবে না, 1.0 = সবসময় বিড
    current_spend:   Decimal
    target_spend:    Decimal
    pacing_ratio:    float      # actual/target — 1.0 = on pace
    recommendation:  str        # 'on_pace', 'behind', 'ahead', 'exhausted'
    remaining_budget: Decimal


@dataclass
class DailyPacingPlan:
    campaign_id:  int
    total_budget: Decimal
    hourly_targets: list        # 24 values, each = target spend for that hour
    strategy:     str


class BudgetPacer:
    """
    Budget Pacing — campaign budget সময়মতো ব্যবহার নিশ্চিত করে।

    Problems solved:
    1. Overspend — budget শেষ হয়ে যায় দিনের শুরুতেই
    2. Underspend — রাতে অনেক budget পড়ে থাকে
    3. Peak hour optimization — high traffic সময়ে বেশি bid করা

    Algorithm:
    - প্রতি ঘন্টার target spend calculate করে
    - Actual vs target compare করে throttle rate বের করে
    - Throttle rate দিয়ে bid participate করবে কিনা decide করে
    """

    def check_pacing(self, campaign_id: int) -> PacingDecision:
        """
        Campaign এর current pacing status check করে।
        Bid করার আগে এটা call করো।
        """
        from api.promotions.models import Campaign, AdminCommissionLog
        from django.db.models import Sum
        from django.utils import timezone as tz

        try:
            campaign = Campaign.objects.select_related().get(pk=campaign_id)
        except Campaign.DoesNotExist:
            return PacingDecision(
                campaign_id=campaign_id, should_bid=False, throttle_rate=0.0,
                current_spend=Decimal('0'), target_spend=Decimal('0'),
                pacing_ratio=0.0, recommendation='not_found',
                remaining_budget=Decimal('0'),
            )

        # Today's spend
        today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_spend = AdminCommissionLog.objects.filter(
            campaign=campaign, created_at__gte=today_start
        ).aggregate(total=Sum('commission_usd'))['total'] or Decimal('0')

        remaining = campaign.total_budget_usd - campaign.spent_usd

        # Ideal spend by now
        target     = self._calculate_target_spend_by_now(
            daily_budget   = campaign.daily_budget_usd or (campaign.total_budget_usd / 30),
            strategy       = getattr(campaign, 'pacing_strategy', PacingStrategy.EVEN),
            hour_of_day    = tz.now().hour,
        )

        pacing_ratio = float(today_spend) / float(max(target, Decimal('0.001')))
        throttle     = self._calculate_throttle_rate(pacing_ratio, remaining)
        should_bid   = throttle > 0 and self._probabilistic_bid(throttle)

        if pacing_ratio < 0.7:     rec = 'behind'
        elif pacing_ratio > 1.3:   rec = 'ahead'
        elif remaining <= Decimal('0.01'): rec = 'exhausted'
        else:                       rec = 'on_pace'

        logger.debug(
            f'Pacing camp_{campaign_id}: ratio={pacing_ratio:.2f}, '
            f'throttle={throttle:.2f}, rec={rec}'
        )
        return PacingDecision(
            campaign_id=campaign_id, should_bid=should_bid,
            throttle_rate=round(throttle, 3), current_spend=today_spend,
            target_spend=target, pacing_ratio=round(pacing_ratio, 3),
            recommendation=rec, remaining_budget=remaining,
        )

    def create_daily_plan(
        self,
        campaign_id:  int,
        total_budget: Decimal,
        strategy:     str = PacingStrategy.EVEN,
        peak_hours:   list = None,
    ) -> DailyPacingPlan:
        """
        দিনের ২৪ ঘন্টার জন্য hourly budget plan তৈরি করে।

        peak_hours: [8, 9, 10, 18, 19, 20] — এই ঘন্টায় বেশি budget
        """
        hourly = self._build_hourly_plan(total_budget, strategy, peak_hours or [])

        plan = DailyPacingPlan(
            campaign_id=campaign_id, total_budget=total_budget,
            hourly_targets=hourly, strategy=strategy,
        )
        cache.set(
            CACHE_PREFIX_PACING.format(f'plan:{campaign_id}'),
            {'hourly': [float(h) for h in hourly], 'strategy': strategy},
            timeout=86400,
        )
        return plan

    def get_bid_modifier(self, campaign_id: int) -> float:
        """
        Bid amount modifier return করে।
        Behind pace → modifier > 1.0 (বেশি bid করো)
        Ahead of pace → modifier < 1.0 (কম bid করো)
        """
        decision = self.check_pacing(campaign_id)
        if not decision.should_bid:
            return 0.0
        if decision.pacing_ratio < 0.7:
            return 1.2   # 20% বেশি bid
        if decision.pacing_ratio > 1.3:
            return 0.8   # 20% কম bid
        return 1.0

    # ── Internal Methods ──────────────────────────────────────────────────────

    def _calculate_target_spend_by_now(
        self, daily_budget: Decimal, strategy: str, hour_of_day: int
    ) -> Decimal:
        """এখন পর্যন্ত কতটা spend হওয়া উচিত ছিল।"""
        hourly = self._build_hourly_plan(daily_budget, strategy, [])
        target = sum(hourly[:hour_of_day + 1])
        return Decimal(str(target))

    def _build_hourly_plan(
        self, total_budget: Decimal, strategy: str, peak_hours: list
    ) -> list:
        budget = float(total_budget)

        if strategy == PacingStrategy.FRONTLOAD:
            # সকালে বেশি, রাতে কম (exponential decay)
            weights = [max(0.5, 2.0 - i * 0.06) for i in range(24)]
        elif strategy == PacingStrategy.ACCELERATED:
            # যত তাড়াতাড়ি পারা যায়
            weights = [3.0 if i < 8 else 1.0 if i < 16 else 0.5 for i in range(24)]
        elif strategy == PacingStrategy.DAYPARTING and peak_hours:
            weights = [2.5 if i in peak_hours else 0.5 for i in range(24)]
        else:  # EVEN
            weights = [1.0] * 24

        total_weight = sum(weights)
        return [budget * (w / total_weight) for w in weights]

    @staticmethod
    def _calculate_throttle_rate(pacing_ratio: float, remaining: Decimal) -> float:
        """Throttle rate calculate করে।"""
        if remaining <= Decimal('0'):
            return 0.0
        # Sigmoid-based smooth throttling
        if pacing_ratio > 1.5:
            return max(0.1, 1.0 - (pacing_ratio - 1.0) * 0.5)
        if pacing_ratio < 0.5:
            return min(1.0, 1.0 + (1.0 - pacing_ratio) * 0.3)
        return 1.0

    @staticmethod
    def _probabilistic_bid(throttle_rate: float) -> bool:
        """Throttle rate অনুযায়ী probabilistically bid করে।"""
        import random
        return random.random() < throttle_rate
