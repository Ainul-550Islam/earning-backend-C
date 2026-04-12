# =============================================================================
# api/promotions/bidding/floor_price.py
# Floor Price Engine — Dynamic floor price calculation
# Platform, category, competition, time-of-day সব বিবেচনা করে
# =============================================================================

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('bidding.floor_price')

CACHE_PREFIX_FLOOR = 'bid:floor:{}'
CACHE_TTL_FLOOR    = 300   # 5 min — dynamic price বারবার recalculate হয়


@dataclass
class FloorPriceResult:
    platform:      str
    category:      str
    country:       str
    floor_usd:     Decimal
    soft_floor:    Decimal   # Bid এর নিচে হলেও consider করা হয় — just at higher win probability
    calculation:   dict      # Breakdown of how floor was calculated
    valid_until:   float     # Unix timestamp


class FloorPriceEngine:
    """
    Dynamic floor price calculation।

    Factors:
    1. Historical clearing price (weighted avg)
    2. Demand level (active bidders)
    3. Time-of-day multiplier (peak hours expensive)
    4. Platform premium (YouTube > others)
    5. Country tier (US/UK expensive, tier-3 cheap)
    6. Competition intensity

    Goal:
    - Revenue maximize করা (floor too low = lost revenue)
    - Fill rate maintain করা (floor too high = unsold inventory)
    """

    # Platform base prices
    PLATFORM_BASE = {
        'youtube':    Decimal('0.050'),
        'facebook':   Decimal('0.040'),
        'instagram':  Decimal('0.045'),
        'tiktok':     Decimal('0.030'),
        'twitter':    Decimal('0.025'),
        'play_store': Decimal('0.060'),
        'default':    Decimal('0.020'),
    }

    # Country tier multipliers
    COUNTRY_TIERS = {
        'tier_1': {'countries': ['US', 'CA', 'GB', 'AU', 'NZ', 'DE', 'FR', 'JP'], 'multiplier': 2.5},
        'tier_2': {'countries': ['IN', 'BR', 'MX', 'TR', 'ID', 'PH', 'PK', 'BD'], 'multiplier': 0.6},
        'tier_3': {'countries': [], 'multiplier': 0.3},  # All others
    }

    # Peak hour multipliers (hour_of_day: multiplier)
    HOUR_MULTIPLIERS = {
        0: 0.6, 1: 0.5, 2: 0.5, 3: 0.5, 4: 0.6, 5: 0.7,
        6: 0.8, 7: 0.9, 8: 1.0, 9: 1.1, 10: 1.2, 11: 1.2,
        12: 1.3, 13: 1.2, 14: 1.1, 15: 1.1, 16: 1.2, 17: 1.3,
        18: 1.4, 19: 1.5, 20: 1.4, 21: 1.3, 22: 1.1, 23: 0.8,
    }

    def calculate(
        self,
        platform:    str,
        category:    str,
        country:     str,
        hour_of_day: int = None,
    ) -> FloorPriceResult:
        """
        Dynamic floor price calculate করে।
        """
        cache_key = CACHE_PREFIX_FLOOR.format(f'{platform}:{category}:{country}')
        cached    = cache.get(cache_key)
        if cached:
            return FloorPriceResult(**cached)

        if hour_of_day is None:
            hour_of_day = timezone.now().hour

        calc = {}

        # Base price
        base  = self.PLATFORM_BASE.get(platform.lower(), self.PLATFORM_BASE['default'])
        calc['base'] = float(base)

        # Country multiplier
        country_mult = self._get_country_multiplier(country.upper())
        calc['country_mult'] = country_mult

        # Time-of-day multiplier
        time_mult = self.HOUR_MULTIPLIERS.get(hour_of_day, 1.0)
        calc['time_mult'] = time_mult

        # Historical clearing price
        hist_price = self._get_historical_clearing_price(platform, category, country)
        calc['historical_avg'] = float(hist_price)

        # Competition multiplier
        comp_mult = self._get_competition_multiplier(platform, category, country)
        calc['competition_mult'] = comp_mult

        # Final floor
        calculated = base * Decimal(str(country_mult)) * Decimal(str(time_mult)) * Decimal(str(comp_mult))

        # Blend with historical (60% historical, 40% calculated)
        if hist_price > Decimal('0'):
            floor = hist_price * Decimal('0.6') + calculated * Decimal('0.4')
        else:
            floor = calculated

        floor      = floor.quantize(Decimal('0.0001'))
        soft_floor = (floor * Decimal('0.7')).quantize(Decimal('0.0001'))

        result = FloorPriceResult(
            platform=platform, category=category, country=country,
            floor_usd=floor, soft_floor=soft_floor,
            calculation=calc, valid_until=timezone.now().timestamp() + 300,
        )
        cache.set(cache_key, result.__dict__, timeout=CACHE_TTL_FLOOR)

        logger.debug(f'Floor price: {platform}/{category}/{country} → ${floor} (hour={hour_of_day})')
        return result

    def bulk_calculate(self, slots: list) -> dict:
        """Multiple slots এর floor price একসাথে।"""
        results = {}
        for slot in slots:
            key  = f'{slot["platform"]}:{slot["category"]}:{slot["country"]}'
            r    = self.calculate(slot['platform'], slot['category'], slot['country'])
            results[key] = r.floor_usd
        return results

    def update_floor_from_auction(
        self,
        platform:       str,
        category:       str,
        country:        str,
        clearing_price: Decimal,
        was_filled:     bool,
    ) -> None:
        """
        Auction result দিয়ে floor price adaptive update করে।
        Unfilled → floor কমাও। Consistently won at high price → floor বাড়াও।
        """
        history_key = CACHE_PREFIX_FLOOR.format(f'hist:{platform}:{category}:{country}')
        history     = cache.get(history_key) or {'prices': [], 'fills': []}

        history['prices'].append(float(clearing_price))
        history['fills'].append(int(was_filled))

        # Keep last 50 auctions
        history['prices'] = history['prices'][-50:]
        history['fills']  = history['fills'][-50:]
        cache.set(history_key, history, timeout=86400)

        # Invalidate floor cache
        cache.delete(CACHE_PREFIX_FLOOR.format(f'{platform}:{category}:{country}'))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_country_multiplier(self, country: str) -> float:
        for tier_info in self.COUNTRY_TIERS.values():
            if country in tier_info.get('countries', []):
                return tier_info['multiplier']
        return self.COUNTRY_TIERS['tier_3']['multiplier']

    def _get_historical_clearing_price(
        self, platform: str, category: str, country: str
    ) -> Decimal:
        history_key = CACHE_PREFIX_FLOOR.format(f'hist:{platform}:{category}:{country}')
        history     = cache.get(history_key)
        if not history or not history['prices']:
            return Decimal('0')
        avg = sum(history['prices']) / len(history['prices'])
        return Decimal(str(avg)).quantize(Decimal('0.0001'))

    def _get_competition_multiplier(self, platform: str, category: str, country: str) -> float:
        """Active bidder count থেকে competition factor।"""
        try:
            from api.promotions.models import Campaign
            from api.promotions.choices import CampaignStatus
            count = Campaign.objects.filter(
                status=CampaignStatus.ACTIVE,
                platform__name__iexact=platform,
            ).count()
            if count > 15: return 1.3
            if count > 8:  return 1.1
            if count < 3:  return 0.8
            return 1.0
        except Exception:
            return 1.0
