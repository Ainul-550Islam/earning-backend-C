# api/payment_gateways/services/GeoPricingEngine.py
# GEO-based dynamic offer pricing — like CPAlead's automatic GEO pricing
# Adjusts payouts based on traffic quality per country

from decimal import Decimal
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# Country tier classification (industry standard)
# Tier 1: Highest value traffic (premium CPA payouts)
# Tier 2: Mid-value traffic
# Tier 3: Lower-value traffic (BD, IN, PH, etc.)

TIER_1_COUNTRIES = frozenset({
    'US','CA','GB','AU','DE','FR','NL','SE','NO','DK','CH','AT',
    'NZ','IE','SG','HK','JP','KR','FI','BE','PT','IS','LU','LI',
})

TIER_2_COUNTRIES = frozenset({
    'IT','ES','PL','CZ','HU','RO','GR','ZA','IL','AE','SA','QA',
    'KW','BR','MX','AR','CL','CO','MY','TH','TW','TR','HR','SK',
})

TIER_3_COUNTRIES = frozenset({
    'BD','IN','PK','PH','ID','VN','EG','NG','KE','GH','UA','RU',
    'PY','PE','EC','BO','VE','MA','DZ','TN','LK','NP','MM','KH',
})

# Payout multiplier per tier
TIER_MULTIPLIERS = {
    1: Decimal('1.00'),   # Full payout
    2: Decimal('0.70'),   # 70% of base
    3: Decimal('0.35'),   # 35% of base
    0: Decimal('0.20'),   # Unknown/other: 20%
}

# CPA rate benchmarks per vertical per tier (USD)
VERTICAL_BENCHMARKS = {
    'mobile_install': {1: Decimal('2.50'), 2: Decimal('0.80'), 3: Decimal('0.15')},
    'gaming':         {1: Decimal('5.00'), 2: Decimal('2.00'), 3: Decimal('0.50')},
    'finance':        {1: Decimal('45.00'),2: Decimal('12.00'),3: Decimal('2.00')},
    'dating':         {1: Decimal('3.50'), 2: Decimal('1.20'), 3: Decimal('0.30')},
    'health':         {1: Decimal('35.00'),2: Decimal('8.00'), 3: Decimal('1.50')},
    'shopping':       {1: Decimal('2.00'), 2: Decimal('0.80'), 3: Decimal('0.20')},
    'sweepstakes':    {1: Decimal('1.80'), 2: Decimal('0.60'), 3: Decimal('0.10')},
    'crypto':         {1: Decimal('50.00'),2: Decimal('15.00'),3: Decimal('3.00')},
    'default':        {1: Decimal('2.00'), 2: Decimal('0.70'), 3: Decimal('0.20')},
}


class GeoPricingEngine:
    """
    Dynamic GEO-based pricing for offers and payouts.

    Features:
        1. Auto-adjust publisher payout based on visitor's country
        2. Calculate advertiser cost for specific GEO
        3. Suggest optimal payout for new offers
        4. Compare country-specific conversion rates
        5. Auto-block countries with negative ROI

    CPAlead uses this to:
        - Show US traffic publishers 10x more than BD traffic
        - Route high-value traffic to high-payout offers
        - Auto-optimize SmartLinks by GEO
    """

    def get_country_tier(self, country_code: str) -> int:
        """Get traffic tier (1, 2, or 3) for a country."""
        c = country_code.upper()
        if c in TIER_1_COUNTRIES: return 1
        if c in TIER_2_COUNTRIES: return 2
        if c in TIER_3_COUNTRIES: return 3
        return 0  # Unknown

    def get_payout_multiplier(self, country_code: str) -> Decimal:
        """Get payout multiplier for a country."""
        tier = self.get_country_tier(country_code)
        return TIER_MULTIPLIERS.get(tier, Decimal('0.20'))

    def calculate_geo_payout(self, base_payout: Decimal,
                              country_code: str,
                              offer_type: str = 'default') -> Decimal:
        """
        Calculate actual payout for a visitor from a specific country.

        Args:
            base_payout:  Base payout (usually for Tier 1 / US traffic)
            country_code: Visitor's country code (ISO 3166-1 alpha-2)
            offer_type:   Offer vertical for benchmark comparison

        Returns:
            Decimal: GEO-adjusted payout

        Example:
            engine = GeoPricingEngine()
            # US visitor gets full $2.50 payout
            us_payout = engine.calculate_geo_payout(Decimal('2.50'), 'US')  # → 2.50
            # BD visitor gets 35% → $0.875
            bd_payout = engine.calculate_geo_payout(Decimal('2.50'), 'BD')  # → 0.88
        """
        multiplier    = self.get_payout_multiplier(country_code)
        geo_payout    = (base_payout * multiplier).quantize(Decimal('0.0001'))
        return geo_payout

    def get_benchmark_payout(self, country_code: str,
                              vertical: str = 'default') -> Decimal:
        """
        Get industry benchmark payout for a country+vertical combination.
        Useful when advertisers don't know what to set as payout.
        """
        tier       = self.get_country_tier(country_code)
        benchmarks = VERTICAL_BENCHMARKS.get(vertical, VERTICAL_BENCHMARKS['default'])
        return benchmarks.get(tier, Decimal('0.10'))

    def get_top_paying_countries(self, offer_type: str = 'default', limit: int = 20) -> list:
        """
        Get list of highest-paying countries for a given offer type.
        Used by SmartLink engine to prioritize traffic routing.
        """
        benchmarks = VERTICAL_BENCHMARKS.get(offer_type, VERTICAL_BENCHMARKS['default'])

        countries  = []
        for country in TIER_1_COUNTRIES:
            countries.append({
                'country':    country,
                'tier':       1,
                'benchmark':  float(benchmarks.get(1, Decimal('2.00'))),
            })
        for country in TIER_2_COUNTRIES:
            countries.append({
                'country':    country,
                'tier':       2,
                'benchmark':  float(benchmarks.get(2, Decimal('0.70'))),
            })

        return sorted(countries, key=lambda x: x['benchmark'], reverse=True)[:limit]

    def calculate_offer_revenue_share(self, advertiser_cost: Decimal,
                                       country_code: str,
                                       platform_margin: Decimal = Decimal('30')) -> dict:
        """
        Calculate revenue split between publisher, platform, and advertiser.

        Args:
            advertiser_cost: What advertiser pays per conversion
            country_code:    GEO of conversion
            platform_margin: Platform keeps X% (default 30%)

        Returns:
            dict: {publisher_payout, platform_fee, advertiser_cost, country, tier}
        """
        tier           = self.get_country_tier(country_code)
        multiplier     = self.get_payout_multiplier(country_code)

        # Publisher gets (100-margin)% of geo-adjusted advertiser cost
        geo_cost       = advertiser_cost * multiplier
        platform_cut   = (geo_cost * platform_margin) / 100
        publisher_gets = geo_cost - platform_cut

        return {
            'advertiser_cost':  float(advertiser_cost),
            'geo_adjusted_cost':float(geo_cost),
            'publisher_payout': float(publisher_gets.quantize(Decimal('0.0001'))),
            'platform_fee':     float(platform_cut.quantize(Decimal('0.0001'))),
            'platform_margin':  float(platform_margin),
            'country':          country_code,
            'tier':             tier,
            'multiplier':       float(multiplier),
        }

    def should_block_country(self, country_code: str,
                              min_payout_threshold: Decimal = Decimal('0.01')) -> bool:
        """
        Determine if a country should be blocked from an offer
        due to extremely low expected payout.
        """
        tier      = self.get_country_tier(country_code)
        benchmark = VERTICAL_BENCHMARKS['default'].get(tier, Decimal('0.10'))
        return benchmark < min_payout_threshold

    def optimize_offer_targeting(self, offer) -> dict:
        """
        Analyze an offer and suggest optimal country targeting.
        Returns countries to target and countries to block for best ROI.
        """
        base_payout   = offer.publisher_payout
        category      = getattr(offer, 'category', 'default')

        targets  = []
        blocks   = []
        neutral  = []

        all_countries = list(TIER_1_COUNTRIES) + list(TIER_2_COUNTRIES) + list(TIER_3_COUNTRIES)

        for country in all_countries:
            geo_payout = self.calculate_geo_payout(base_payout, country, category)
            if geo_payout >= base_payout * Decimal('0.5'):
                targets.append({'country': country, 'expected_payout': float(geo_payout)})
            elif geo_payout < Decimal('0.05'):
                blocks.append(country)
            else:
                neutral.append({'country': country, 'expected_payout': float(geo_payout)})

        return {
            'recommend_target':  sorted(targets, key=lambda x: x['expected_payout'], reverse=True)[:20],
            'recommend_block':   blocks[:10],
            'neutral_countries': neutral[:10],
            'optimization_note': f'Target Tier 1 countries for {float(base_payout):.2f} payouts. '
                                  f'Block low-value countries to improve campaign ROI.',
        }
