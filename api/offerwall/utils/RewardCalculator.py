"""
Reward calculation utility
"""
import logging
from decimal import Decimal, ROUND_DOWN
from django.utils import timezone
from ..constants import (
    DEFAULT_REVENUE_SHARE,
)

logger = logging.getLogger(__name__)


class RewardCalculator:
    """Calculator for offer rewards and payouts"""
    
    def __init__(self, offer=None, provider=None):
        self.offer = offer
        self.provider = provider or (offer.provider if offer else None)

    def validate_payout_amount(self, amount) -> bool:
        """
        Validate that a payout amount is positive.
        Raises InvalidRewardException if amount <= 0.
        Returns True if valid.
        """
        from decimal import Decimal
        from ..exceptions import InvalidRewardException
        if amount is None or amount <= Decimal('0'):
            raise InvalidRewardException(
                f'Payout amount must be positive, got: {amount}')
        return True

    def calculate_user_reward(self, payout_amount, currency='USD'):
        """
        Calculate user reward from payout using provider revenue share.
        Returns Decimal reward amount. Handles provider being a User object.
        """
        from decimal import Decimal, ROUND_HALF_UP
        payout = Decimal(str(payout_amount))
        rs = None
        if self.provider and hasattr(self.provider, 'revenue_share'):
            try:
                rs = Decimal(str(self.provider.revenue_share)) / Decimal('100')
            except Exception:
                rs = None
        if rs is None:
            rs = Decimal('0.70')
        return (payout * rs).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

    def calculate_platform_fee(self, payout_amount):
        """
        Calculate platform fee
        
        Args:
            payout_amount: Payout from provider
        
        Returns:
            Decimal: Platform fee amount
        """
        payout = Decimal(str(payout_amount))
        user_reward = self.calculate_user_reward(payout)
        
        platform_fee = (payout - user_reward).quantize(
            Decimal('0.000001'),
            rounding=ROUND_DOWN
        )
        
        return platform_fee
    
    def calculate_bonus_reward(self, base_reward, bonus_multiplier=None):
        """
        Calculate bonus reward
        
        Args:
            base_reward: Base reward amount
            bonus_multiplier: Bonus multiplier (default from offer)
        
        Returns:
            Decimal: Bonus reward amount
        """
        if not self.offer or not self.offer.bonus_amount:
            return Decimal('0')
        
        # Use fixed bonus amount from offer
        if self.offer.bonus_amount > 0:
            return Decimal(str(self.offer.bonus_amount))
        
        # Or calculate based on multiplier
        if bonus_multiplier:
            base = Decimal(str(base_reward))
            multiplier = Decimal(str(bonus_multiplier))
            
            bonus = (base * multiplier).quantize(
                Decimal('0.000001'),
                rounding=ROUND_DOWN
            )
            
            return bonus
        
        return Decimal('0')
    
    def calculate_referral_bonus(self, base_reward, referral_rate=None):
        """
        Calculate referral bonus for referrer
        
        Args:
            base_reward: Base reward earned by referred user
            referral_rate: Referral commission rate (percentage)
        
        Returns:
            Decimal: Referral bonus amount
        """
        if not referral_rate:
            referral_rate = Decimal('10')  # Default 10%
        
        base = Decimal(str(base_reward))
        rate = Decimal(str(referral_rate)) / Decimal('100')
        
        referral_bonus = (base * rate).quantize(
            Decimal('0.000001'),
            rounding=ROUND_DOWN
        )
        
        return referral_bonus
    
    def calculate_total_reward(self, payout_amount, include_bonus=True):
        """
        Calculate total reward including bonuses
        
        Args:
            payout_amount: Payout from provider
            include_bonus: Whether to include bonus
        
        Returns:
            dict: Breakdown of rewards
        """
        base_reward = self.calculate_user_reward(payout_amount)
        
        bonus = Decimal('0')
        if include_bonus:
            bonus = self.calculate_bonus_reward(base_reward)
        
        total = base_reward + bonus
        
        return {
            'base_reward': base_reward,
            'bonus_reward': bonus,
            'total_reward': total,
            'currency': self.offer.reward_currency if self.offer else 'Points'
        }
    
    def calculate_tier_multiplier(self, user=None):
        """
        Calculate reward multiplier based on user tier.
        Returns float multiplier (1.0 = no bonus).
        """
        multiplier = 1.0
        target = user or (self.provider
                          if self.provider and not hasattr(self.provider, 'revenue_share')
                          else None)
        if target is None:
            return multiplier
        if hasattr(target, 'profile'):
            profile = target.profile
            if hasattr(profile, 'tier'):
                tier_map = {
                    'bronze': 1.0, 'silver': 1.1, 'gold': 1.2,
                    'platinum': 1.3, 'diamond': 1.5,
                }
                multiplier = tier_map.get(profile.tier.lower(), 1.0)
        return multiplier

    def calculate_time_bonus(self, completion_time_minutes):
        """
        Calculate bonus for fast completion
        
        Args:
            completion_time_minutes: Time taken to complete
        
        Returns:
            Decimal: Time bonus multiplier
        """
        if not self.offer:
            return Decimal('1.0')
        
        estimated_time = self.offer.estimated_time_minutes
        
        # If completed in less than half the estimated time, give bonus
        if completion_time_minutes <= (estimated_time / 2):
            return Decimal('1.2')  # 20% bonus
        elif completion_time_minutes <= estimated_time:
            return Decimal('1.1')  # 10% bonus
        
        return Decimal('1.0')  # No bonus
    
    def calculate_streak_bonus(self, user_streak_days):
        """
        Calculate bonus for consecutive daily completions
        
        Args:
            user_streak_days: Number of consecutive days
        
        Returns:
            Decimal: Streak bonus multiplier
        """
        if user_streak_days >= 30:
            return Decimal('1.5')  # 50% bonus for 30+ days
        elif user_streak_days >= 14:
            return Decimal('1.3')  # 30% bonus for 14+ days
        elif user_streak_days >= 7:
            return Decimal('1.2')  # 20% bonus for 7+ days
        elif user_streak_days >= 3:
            return Decimal('1.1')  # 10% bonus for 3+ days
        
        return Decimal('1.0')
    
    def calculate_volume_bonus(self, user_completion_count):
        """
        Calculate bonus based on total completions
        
        Args:
            user_completion_count: Total offers completed by user
        
        Returns:
            Decimal: Volume bonus multiplier
        """
        if user_completion_count >= 1000:
            return Decimal('1.5')
        elif user_completion_count >= 500:
            return Decimal('1.3')
        elif user_completion_count >= 100:
            return Decimal('1.2')
        elif user_completion_count >= 50:
            return Decimal('1.1')
        
        return Decimal('1.0')
    
    def calculate_special_event_bonus(self, base_reward=None):
        """
        Calculate bonus for special events (holidays, promotions).
        Args:
            base_reward: Optional base reward (unused, for API compatibility)
        Returns:
            Decimal: Event bonus multiplier
        """
        now = timezone.now()
        if now.weekday() >= 5:  # Saturday or Sunday — double rewards
            return Decimal('2.0')
        return Decimal('1.0')
    
    def calculate_all_bonuses(self, user, **kwargs):
        """
        Calculate all applicable bonuses.

        FIX: Was reading streak/volume/time from kwargs (always 1.0 default)
        instead of actually calling the calculator methods.
        Now calls every method and fetches required data from DB.

        Args:
            user: User instance
            **kwargs: completion_time_minutes (optional)
        """
        from api.offerwall.models import OfferConversion
        from django.utils import timezone
        from django.db.models import Count

        # 1. Tier multiplier — user subscription/profile tier (returns float, cast to Decimal)
        tier_mult = Decimal(str(self.calculate_tier_multiplier(user)))

        # 2. Time bonus — only if completion time passed in kwargs
        completion_time = kwargs.get('completion_time_minutes')
        time_mult = (self.calculate_time_bonus(completion_time)
                     if completion_time is not None else Decimal('1.0'))

        # 3. Streak bonus — consecutive days with at least one approved conversion
        streak_days = 0
        try:
            today = timezone.now().date()
            streak_days = 0
            for delta in range(30):  # check up to 30 days back
                check_date = today - __import__('datetime').timedelta(days=delta)
                had_conv = OfferConversion.objects.filter(
                    user=user, status='approved',
                    converted_at__date=check_date
                ).exists()
                if had_conv:
                    streak_days += 1
                elif delta > 0:   # day 0 (today) can be empty; break after gap
                    break
        except Exception:
            pass
        streak_mult = self.calculate_streak_bonus(streak_days)

        # 4. Volume bonus — total approved conversions by user
        total_completions = 0
        try:
            total_completions = OfferConversion.objects.filter(
                user=user, status='approved').count()
        except Exception:
            pass
        volume_mult = self.calculate_volume_bonus(total_completions)

        # 5. Special event (weekend / holiday)
        event_mult = self.calculate_special_event_bonus()

        bonuses = {
            'tier':   tier_mult,
            'time':   time_mult,
            'streak': streak_mult,
            'volume': volume_mult,
            'event':  event_mult,
        }

        total_multiplier = Decimal('1.0')
        for multiplier in bonuses.values():
            total_multiplier *= multiplier
        bonuses['total'] = total_multiplier

        return bonuses
    
    def apply_bonuses_to_reward(self, base_reward, bonuses):
        """
        Apply all bonuses to base reward
        
        Args:
            base_reward: Base reward amount
            bonuses: Dictionary of bonus multipliers
        
        Returns:
            Decimal: Final reward with bonuses
        """
        base = Decimal(str(base_reward))
        total_multiplier = bonuses.get('total', Decimal('1.0'))
        
        final_reward = (base * total_multiplier).quantize(
            Decimal('0.000001'),
            rounding=ROUND_DOWN
        )
        
        return final_reward
    
    def calculate_conversion_value(self, payout_amount=None, user=None, **kwargs):
        """
        Calculate complete conversion value with all bonuses.
        If payout_amount is None, uses offer.payout.
        Returns Decimal when user is None, dict when user is provided.
        """
        if payout_amount is None:
            payout_amount = (
                self.offer.payout if self.offer and self.offer.payout
                else Decimal('0')
            )
        payout_amount = Decimal(str(payout_amount))
        # Base reward
        base_reward = self.calculate_user_reward(payout_amount)
        # Quick path: no user → return bare Decimal
        if user is None:
            return base_reward
        # Full path: calculate all bonuses
        bonuses      = self.calculate_all_bonuses(user, **kwargs)
        final_reward = self.apply_bonuses_to_reward(base_reward, bonuses) if bonuses else base_reward
        platform_fee = self.calculate_platform_fee(payout_amount)
        return {
            'payout':          payout_amount,
            'base_reward':     base_reward,
            'bonuses':         bonuses,
            'final_reward':    final_reward,
            'platform_fee':    platform_fee,
            'currency':        self.offer.reward_currency if self.offer else 'Points',
            'bonus_breakdown': {
                'tier_bonus':   bonuses.get('tier',   Decimal('1.0')) - Decimal('1.0'),
                'time_bonus':   bonuses.get('time',   Decimal('1.0')) - Decimal('1.0'),
                'streak_bonus': bonuses.get('streak', Decimal('1.0')) - Decimal('1.0'),
                'volume_bonus': bonuses.get('volume', Decimal('1.0')) - Decimal('1.0'),
                'event_bonus':  bonuses.get('event',  Decimal('1.0')) - Decimal('1.0'),
            },
        }
    
    @staticmethod
    def convert_currency(amount, from_currency, to_currency, exchange_rate=None):
        """
        Convert amount between currencies
        
        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            exchange_rate: Optional custom exchange rate
        
        Returns:
            Decimal: Converted amount
        """
        if from_currency == to_currency:
            return Decimal(str(amount))
        
        amount = Decimal(str(amount))
        
        # Use provided exchange rate or fetch from service
        if exchange_rate:
            rate = Decimal(str(exchange_rate))
        else:
            # TODO: Implement real exchange rate fetching
            rate = Decimal('1.0')
        
        _STATIC_RATES = {
            ('USD', 'BDT'): Decimal('110'),
            ('BDT', 'USD'): Decimal('0.0091'),
            ('USD', 'EUR'): Decimal('0.92'),
            ('EUR', 'USD'): Decimal('1.09'),
            ('USD', 'GBP'): Decimal('0.79'),
            ('GBP', 'USD'): Decimal('1.27'),
        }
        if not exchange_rate:
            rate = _STATIC_RATES.get(
                (from_currency.upper(), to_currency.upper()), Decimal('1.0'))
        converted = (amount * rate).quantize(
            Decimal('0.000001'),
            rounding=ROUND_DOWN
        )
        
        return converted