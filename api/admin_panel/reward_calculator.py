# api/admin_panel/reward_calculator.py
"""Task reward calculation with bonuses, multipliers, and tier rewards."""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict
from django.utils import timezone

logger = logging.getLogger(__name__)


class RewardCalculator:
    """Centralized reward calculation — single source of truth."""

    @classmethod
    def calculate(cls, campaign_id: Any, user_id: Any,
                   submission_metadata: Dict = None) -> Dict:
        """Calculate final reward with all bonuses applied."""
        base = cls._get_base_reward(campaign_id)
        multipliers = []
        final = base

        # Tier multiplier
        try:
            from api.admin_panel.rate_card import rate_card_manager
            tier = rate_card_manager.get_publisher_tier(user_id)
            m = Decimal(str(tier.get('rate_multiplier', 1.0)))
            if m != Decimal('1.0'):
                multipliers.append({'type': 'tier', 'multiplier': float(m), 'tier': tier['tier']})
            final *= m
        except Exception:
            pass

        # Global bonus multiplier
        try:
            from api.admin_panel.earning_engine import earning_engine
            bonus = earning_engine._get_active_bonus(user_id)
            bm = Decimal(str(bonus.get('multiplier', 1.0)))
            if bm != Decimal('1.0'):
                multipliers.append({'type': 'bonus', 'multiplier': float(bm), 'name': bonus.get('bonus_name', '')})
            final *= bm
        except Exception:
            pass

        # Streak bonus
        try:
            from api.engagement.models import DailyCheckIn
            streak = DailyCheckIn.objects.filter(user_id=user_id).order_by('-created_at').first()
            if streak and streak.streak >= 7:
                streak_bonus = min(Decimal('1.5'), Decimal('1.0') + Decimal('0.05') * (streak.streak // 7))
                multipliers.append({'type': 'streak', 'multiplier': float(streak_bonus), 'streak_days': streak.streak})
                final *= streak_bonus
        except Exception:
            pass

        final = final.quantize(Decimal('0.0001'))
        return {
            'base_reward': float(base),
            'final_reward': float(final),
            'currency': 'BDT',
            'multipliers': multipliers,
            'total_multiplier': float(final / base) if base else 1.0,
            'campaign_id': campaign_id,
            'user_id': user_id,
        }

    @classmethod
    def _get_base_reward(cls, campaign_id: Any) -> Decimal:
        try:
            from api.promotions.models import Campaign
            c = Campaign.objects.get(pk=campaign_id)
            return Decimal(str(c.reward_usd or 0))
        except Exception:
            return Decimal('0')

    @classmethod
    def calculate_loyalty_points(cls, cash_reward: Decimal) -> int:
        """Convert cash reward to loyalty points."""
        try:
            from api.admin_panel.services.SystemConfigService import SystemConfigService
            rate = int(SystemConfigService.get('points_per_bdt', default=10))
            return int(cash_reward * rate)
        except Exception:
            return int(cash_reward * 10)


reward_calculator = RewardCalculator()