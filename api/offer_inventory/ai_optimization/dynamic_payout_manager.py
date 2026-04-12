# api/offer_inventory/ai_optimization/dynamic_payout_manager.py
"""
Dynamic Payout Manager.
Adjusts user reward percentages dynamically based on
time-of-day, loyalty tier, and market demand.
All arithmetic uses Decimal.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone

logger = logging.getLogger(__name__)

# Base share (70%)
BASE_USER_PCT = Decimal('70')

# Time bonuses (UTC hours)
PEAK_HOURS = range(12, 16)        # BD 6–10 PM
PEAK_BONUS  = Decimal('5')        # +5% during peak

# High-demand payout boost
HIGH_DEMAND_THRESHOLD = 100       # Clicks/hour to qualify
HIGH_DEMAND_BONUS     = Decimal('3')


class DynamicPayoutManager:
    """Calculates dynamic user reward percentage."""

    @classmethod
    def get_user_pct(cls, offer=None, user=None) -> Decimal:
        """
        Returns the dynamic user reward % for this offer/user combo.
        Result: Decimal between 60–90.
        """
        pct = BASE_USER_PCT

        # Peak hours bonus
        hour = timezone.now().hour
        if hour in PEAK_HOURS:
            pct += PEAK_BONUS

        # Loyalty bonus
        pct += cls._loyalty_bonus(user)

        # High-demand offer bonus
        if offer:
            pct += cls._demand_bonus(offer)

        # Clamp 60–90%
        pct = max(Decimal('60'), min(pct, Decimal('90')))
        return pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _loyalty_bonus(user) -> Decimal:
        if not user:
            return Decimal('0')
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.select_related('loyalty_level').get(user=user)
            if profile.loyalty_level:
                return Decimal(str(profile.loyalty_level.payout_bonus_pct or '0'))
        except Exception:
            pass
        return Decimal('0')

    @staticmethod
    def _demand_bonus(offer) -> Decimal:
        """Offers with high click volume get small bonus."""
        from django.core.cache import cache
        from datetime import timedelta
        key    = f'offer_hourly_clicks:{offer.id}'
        cached = cache.get(key)
        if cached is None:
            from api.offer_inventory.models import Click
            since  = timezone.now() - timedelta(hours=1)
            cached = Click.objects.filter(offer=offer, created_at__gte=since).count()
            cache.set(key, cached, 60)
        return HIGH_DEMAND_BONUS if cached >= HIGH_DEMAND_THRESHOLD else Decimal('0')

    @classmethod
    def calculate_reward(cls, payout: Decimal, offer=None, user=None) -> Decimal:
        """Calculate actual reward amount using dynamic %."""
        pct    = cls.get_user_pct(offer, user)
        reward = (payout * pct / Decimal('100')).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )
        return reward
