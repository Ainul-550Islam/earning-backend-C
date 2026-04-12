# =============================================================================
# promotions/geo_pricing/geo_payout_calculator.py
# Geo-based Dynamic Pricing — Tier 1/2/3 payout calculation
# Same offer: US=$5, DE=$2, BD=$0.20
# =============================================================================
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

GEO_TIERS = {
    1: ['US','CA','GB','AU','IE','NZ','SG','CH','NO','SE','DK','FI','NL','BE','AT'],
    2: ['DE','FR','IT','ES','PT','PL','CZ','HU','RO','GR','HR','SK','BG','SI','LT','LV','EE'],
    3: ['IN','BD','PK','NG','GH','KE','UG','TZ','PH','ID','MY','TH','VN','BR','MX','AR','CO'],
}

TIER_MULTIPLIERS = {1: Decimal('1.0'), 2: Decimal('0.4'), 3: Decimal('0.15')}


def get_country_tier(country: str) -> int:
    country = country.upper()
    for tier, countries in GEO_TIERS.items():
        if country in countries: return tier
    return 3  # Default tier 3


def calculate_geo_payout(base_payout_usd: Decimal, country: str) -> dict:
    tier = get_country_tier(country)
    multiplier = TIER_MULTIPLIERS[tier]
    adjusted = (base_payout_usd * multiplier).quantize(Decimal('0.0001'))
    return {
        'country': country, 'tier': tier,
        'base_payout': str(base_payout_usd),
        'multiplier': str(multiplier),
        'adjusted_payout': str(adjusted),
        'tier_name': ['', 'Tier 1 (Premium)', 'Tier 2 (Mid)', 'Tier 3 (Economy)'][tier],
    }


def get_best_geo_offers(publisher_country: str, available_offers: list) -> list:
    """Sort offers by adjusted payout for publisher's geo."""
    scored = []
    for offer in available_offers:
        base = Decimal(str(offer.get('payout', '0')))
        geo = calculate_geo_payout(base, publisher_country)
        scored.append({**offer, 'geo_payout': geo['adjusted_payout'], 'geo_tier': geo['tier']})
    return sorted(scored, key=lambda x: Decimal(x['geo_payout']), reverse=True)


@api_view(['GET'])
@permission_classes([AllowAny])
def geo_pricing_view(request):
    """GET /api/promotions/geo/pricing/?country=BD&base_payout=5.00"""
    country = request.query_params.get('country', 'US')
    base = Decimal(str(request.query_params.get('base_payout', '1.00')))
    return Response(calculate_geo_payout(base, country))


@api_view(['GET'])
@permission_classes([AllowAny])
def geo_tiers_view(request):
    return Response({
        'tiers': {
            f'Tier {t}': {'multiplier': str(m), 'countries': GEO_TIERS.get(t, [])}
            for t, m in TIER_MULTIPLIERS.items()
        }
    })
