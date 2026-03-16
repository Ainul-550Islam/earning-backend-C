"""
Reward calculation utility
"""
import logging
from decimal import Decimal, ROUND_DOWN
from django.utils import timezone
from ..constants import *

logger = logging.getLogger(__name__)


class RewardCalculator:
    """Calculator for offer rewards and payouts"""
    
    def __init__(self, offer=None, provider=None):
        self.offer = offer
        self.provider = provider or (offer.provider if offer else None)
    
    def calculate_user_reward(self, payout_amount, currency='USD'):
        """
        Calculate user reward based on payout and revenue share
        
        Args:
            payout_amount: Payout from provider
            currency: Currency code
        
        Returns:
            Decimal: User reward amount
        """
        payout = Decimal(str(payout_amount))
        
        # Get revenue share percentage
        if self.provider:
            revenue_share = Decimal(str(self.provider.revenue_share)) / Decimal('100')
        else:
            revenue_share = Decimal(str(DEFAULT_REVENUE_SHARE)) / Decimal('100')
        
        # Calculate user reward
        user_reward = (payout * revenue_share).quantize(
            Decimal('0.000001'), 
            rounding=ROUND_DOWN
        )
        
        logger.info(
            f"Calculated reward: {payout} * {revenue_share} = {user_reward}"
        )
        
        return user_reward
    
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
    
    def calculate_tier_multiplier(self, user):
        """
        Calculate reward multiplier based on user tier
        
        Args:
            user: User instance
        
        Returns:
            Decimal: Tier multiplier
        """
        # Default multiplier
        multiplier = Decimal('1.0')
        
        # Check if user has premium/VIP status
        if hasattr(user, 'profile'):
            profile = user.profile
            
            if hasattr(profile, 'tier'):
                tier_multipliers = {
                    'bronze': Decimal('1.0'),
                    'silver': Decimal('1.1'),
                    'gold': Decimal('1.2'),
                    'platinum': Decimal('1.3'),
                    'diamond': Decimal('1.5'),
                }
                
                multiplier = tier_multipliers.get(
                    profile.tier.lower(),
                    Decimal('1.0')
                )
        
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
    
    def calculate_special_event_bonus(self):
        """
        Calculate bonus for special events (holidays, promotions)
        
        Returns:
            Decimal: Event bonus multiplier
        """
        now = timezone.now()
        
        # Example: Double rewards on weekends
        if now.weekday() >= 5:  # Saturday or Sunday
            return Decimal('2.0')
        
        # Add more special event logic here
        # - Holidays
        # - Flash sales
        # - User birthday
        # - Platform anniversary
        
        return Decimal('1.0')
    
    def calculate_all_bonuses(self, user, **kwargs):
        """
        Calculate all applicable bonuses
        
        Args:
            user: User instance
            **kwargs: Additional parameters
        
        Returns:
            dict: All bonus multipliers and total
        """
        bonuses = {
            'tier': self.calculate_tier_multiplier(user),
            'time': kwargs.get('time_bonus', Decimal('1.0')),
            'streak': kwargs.get('streak_bonus', Decimal('1.0')),
            'volume': kwargs.get('volume_bonus', Decimal('1.0')),
            'event': self.calculate_special_event_bonus(),
        }
        
        # Calculate total multiplier
        total_multiplier = Decimal('1.0')
        for bonus_type, multiplier in bonuses.items():
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
    
    def calculate_conversion_value(self, payout_amount, user=None, **kwargs):
        """
        Calculate complete conversion value with all bonuses
        
        Args:
            payout_amount: Payout from provider
            user: User instance
            **kwargs: Additional parameters
        
        Returns:
            dict: Complete breakdown of conversion value
        """
        # Base reward
        base_reward = self.calculate_user_reward(payout_amount)
        
        # Calculate bonuses if user provided
        bonuses = {}
        if user:
            bonuses = self.calculate_all_bonuses(user, **kwargs)
        
        # Apply bonuses
        final_reward = self.apply_bonuses_to_reward(base_reward, bonuses) if bonuses else base_reward
        
        # Platform fee
        platform_fee = self.calculate_platform_fee(payout_amount)
        
        return {
            'payout': Decimal(str(payout_amount)),
            'base_reward': base_reward,
            'bonuses': bonuses,
            'final_reward': final_reward,
            'platform_fee': platform_fee,
            'currency': self.offer.reward_currency if self.offer else 'Points',
            'bonus_breakdown': {
                'tier_bonus': bonuses.get('tier', Decimal('1.0')) - Decimal('1.0'),
                'time_bonus': bonuses.get('time', Decimal('1.0')) - Decimal('1.0'),
                'streak_bonus': bonuses.get('streak', Decimal('1.0')) - Decimal('1.0'),
                'volume_bonus': bonuses.get('volume', Decimal('1.0')) - Decimal('1.0'),
                'event_bonus': bonuses.get('event', Decimal('1.0')) - Decimal('1.0'),
            }
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
        
        converted = (amount * rate).quantize(
            Decimal('0.000001'),
            rounding=ROUND_DOWN
        )
        
        return converted