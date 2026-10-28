# api/admin_panel/earning_engine.py
"""
Core earning calculation engine.
Calls api.promotions, api.djoyalty, api.wallet — admin_panel orchestrates.
Single source of truth for all earning logic.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class EarningEngine:
    """Calculate earnings for task completions, bonuses, multipliers."""

    @classmethod
    def calculate_task_reward(cls, campaign_id: Any, user_id: Any,
                               task_type: str = 'standard') -> Dict:
        """Calculate reward for a task completion."""
        try:
            from api.promotions.models import Campaign
            campaign = Campaign.objects.get(pk=campaign_id)
            base_reward = Decimal(str(campaign.reward_usd or 0))
        except Exception:
            base_reward = Decimal('0')

        # Apply multipliers
        multiplier = Decimal('1.0')

        # Publisher tier multiplier
        try:
            from api.admin_panel.rate_card import rate_card_manager
            tier_data = rate_card_manager.get_publisher_tier(user_id)
            multiplier *= Decimal(str(tier_data.get('rate_multiplier', 1.0)))
        except Exception:
            pass

        # Bonus period multiplier
        bonus = cls._get_active_bonus(user_id)
        multiplier *= Decimal(str(bonus.get('multiplier', 1.0)))

        final_reward = (base_reward * multiplier).quantize(Decimal('0.0001'))

        return {
            'base_reward': float(base_reward),
            'multiplier': float(multiplier),
            'final_reward': float(final_reward),
            'currency': 'BDT',
            'bonus_applied': bonus.get('bonus_name', ''),
            'campaign_id': campaign_id,
        }

    @classmethod
    def calculate_referral_commission(cls, referrer_id: Any,
                                       referred_earning: Decimal, level: int = 1) -> Decimal:
        """Calculate referral commission (multi-level)."""
        rates = {1: Decimal('0.05'), 2: Decimal('0.02'), 3: Decimal('0.01')}
        rate = rates.get(level, Decimal('0'))
        return (referred_earning * rate).quantize(Decimal('0.0001'))

    @classmethod
    def credit_user(cls, user_id: Any, amount: Decimal,
                     reason: str, transaction_type: str = 'earning') -> Dict:
        """Credit a user wallet. Calls api.wallet."""
        try:
            from api.wallet.models import Wallet
            from django.db import transaction
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(user_id=user_id)
                wallet.current_balance += amount
                wallet.total_earned += amount
                wallet.save(update_fields=['current_balance', 'total_earned'])
            return {'success': True, 'amount': float(amount), 'user_id': user_id}
        except Exception as e:
            logger.error(f"[EarningEngine.credit_user] {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def award_loyalty_points(cls, user_id: Any, points: int, reason: str) -> Dict:
        """Award loyalty points. Calls api.djoyalty."""
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.integ_handler import IntegrationHandler
            return IntegrationHandler.execute(
                app='djoyalty', action='grant_points',
                payload={'user_id': user_id, 'amount': points, 'reason': reason},
            )
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _get_active_bonus(cls, user_id: Any) -> Dict:
        """Get active bonus multiplier for a user."""
        from django.core.cache import cache
        bonus = cache.get(f'earning_bonus:{user_id}')
        if bonus:
            return bonus
        # Check system-wide bonus
        global_bonus = cache.get('earning_bonus:global')
        return global_bonus or {'multiplier': 1.0}

    @classmethod
    def set_earning_bonus(cls, multiplier: float, hours: int = 24,
                           user_id: Any = None, label: str = '') -> None:
        """Set an earning multiplier bonus."""
        from django.core.cache import cache
        bonus = {'multiplier': multiplier, 'bonus_name': label or f'{multiplier}x Bonus'}
        key = f'earning_bonus:{user_id}' if user_id else 'earning_bonus:global'
        cache.set(key, bonus, hours * 3600)
        logger.info(f"[EarningEngine] Bonus set: {multiplier}x for {hours}h (user={user_id or 'all'})")


earning_engine = EarningEngine()