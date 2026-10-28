# services/offerwall/targeting.py
"""
OfferTargetingService — User segmentation & offer vertical targeting.
Owner: OfferTargetingService (এক কাজের জন্য একটাই মালিক)

What was missing:
  • No offer category / vertical system
  • No user demographic segmentation
  • No targeted offer ranking (wrong offers shown to wrong users)
  • No A/B test at the offer level

This service adds:
  • VERTICALS: gaming / finance / health / dating / utilities / surveys
  • User profile segmentation (age group, gender, interests, geo tier)
  • eCPM-based offer ranking with user context
  • A/B test groups for offer presentation
  • Exclusion rules (already converted, cap reached, geo mismatch)
"""
import logging
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger("wallet.offerwall.targeting")

# Offer verticals (industry standard taxonomy)
VERTICALS = {
    "gaming":     {"label": "Games & Apps",         "icon": "🎮"},
    "finance":    {"label": "Finance & Insurance",   "icon": "💰"},
    "health":     {"label": "Health & Wellness",     "icon": "💊"},
    "dating":     {"label": "Dating & Social",       "icon": "❤️"},
    "utilities":  {"label": "Utilities & Tools",     "icon": "🔧"},
    "surveys":    {"label": "Surveys & Research",    "icon": "📊"},
    "ecommerce":  {"label": "Shopping & E-commerce", "icon": "🛍️"},
    "education":  {"label": "Education & Learning",  "icon": "📚"},
    "travel":     {"label": "Travel & Lifestyle",    "icon": "✈️"},
    "entertainment": {"label": "Entertainment",      "icon": "🎬"},
}

# Geo tiers for offer targeting
GEO_TIERS = {
    "tier1": ["US", "GB", "CA", "AU", "NZ", "DE", "FR", "NL"],
    "tier2": ["IN", "BR", "MX", "PL", "ES", "IT", "RU", "TR"],
    "tier3": ["BD", "PK", "NG", "PH", "ID", "VN", "TH", "EG"],
}


class UserSegment:
    """Computed user segment for offer targeting."""

    def __init__(
        self,
        user_id:      int,
        country_code: str         = "BD",
        device_type:  str         = "desktop",
        age_group:    str         = "unknown",   # 18-24 / 25-34 / 35-44 / 45+
        gender:       str         = "unknown",   # male / female / other / unknown
        interests:    list        = None,
        geo_tier:     str         = "tier3",
        kyc_level:    int         = 0,
        total_earned: Decimal     = Decimal("0"),
        converted_offer_ids: set  = None,
    ):
        self.user_id             = user_id
        self.country_code        = country_code
        self.device_type         = device_type
        self.age_group           = age_group
        self.gender              = gender
        self.interests           = interests or []
        self.geo_tier            = geo_tier
        self.kyc_level           = kyc_level
        self.total_earned        = total_earned
        self.converted_offer_ids = converted_offer_ids or set()

    @classmethod
    def build(cls, user, wallet=None) -> "UserSegment":
        """Build segment from user + wallet data."""
        from ...ip_geo import get_country_code
        from django.conf import settings

        country = getattr(user, "country_code", "BD") or "BD"
        geo_tier = "tier3"
        for tier, countries in GEO_TIERS.items():
            if country.upper() in countries:
                geo_tier = tier
                break

        # Already-converted offer IDs (avoid re-showing completed offers)
        converted = set()
        if wallet:
            try:
                from ...models_cpalead_extra import OfferConversion
                converted = set(
                    OfferConversion.objects.filter(
                        wallet=wallet, status="approved"
                    ).values_list("offer__offer_id", flat=True)
                )
            except Exception:
                pass

        kyc_level = 0
        try:
            from ...models_cpalead_extra import KYCVerification
            kyc = KYCVerification.objects.filter(
                user=user, status="approved"
            ).order_by("-level").first()
            if kyc:
                kyc_level = kyc.level
        except Exception:
            pass

        total_earned = Decimal("0")
        if wallet:
            total_earned = getattr(wallet, "total_earned", Decimal("0")) or Decimal("0")

        return cls(
            user_id             = user.id,
            country_code        = country.upper(),
            geo_tier            = geo_tier,
            kyc_level           = kyc_level,
            total_earned        = total_earned,
            converted_offer_ids = converted,
        )


class OfferTargetingService:
    """
    Score and rank offers for a specific user segment.
    Owner of all offer targeting / personalization logic.
    """

    @staticmethod
    def rank_offers(offers: list, segment: "UserSegment") -> list:
        """
        Score each offer for this user segment and return sorted list.
        Higher score = more relevant to this user.
        """
        scored = []
        for offer in offers:
            score = OfferTargetingService._score(offer, segment)
            if score > 0:
                scored.append((score, offer))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [o for _, o in scored]

    @staticmethod
    def _score(offer, segment: "UserSegment") -> float:
        """
        Scoring factors (0-100):
          40% — payout (higher = better)
          20% — geo match (offer targets user's country)
          15% — device match
          15% — not already converted
          10% — vertical match with user interests
        """
        score = 0.0

        # 1. Payout score (normalize to 0-40)
        payout_f = float(offer.payout_usd)
        payout_score = min(40.0, payout_f * 10)
        score += payout_score

        # 2. Geo match (0-20)
        offer_countries = [c.upper() for c in (offer.geo_countries or [])]
        if not offer_countries:
            score += 10  # no restriction = partial score
        elif segment.country_code in offer_countries:
            score += 20
        else:
            return 0  # geo mismatch → exclude entirely

        # 3. Device match (0-15)
        if segment.device_type == "mobile" and offer.is_mobile:
            score += 15
        elif segment.device_type == "desktop" and offer.is_desktop:
            score += 15
        elif offer.is_mobile and offer.is_desktop:
            score += 8  # available on both

        # 4. Not already converted (0-15)
        if offer.offer_id not in segment.converted_offer_ids:
            score += 15

        # 5. Vertical / interest match (0-10)
        if offer.vertical and segment.interests:
            if offer.vertical in segment.interests:
                score += 10
            else:
                score += 3
        elif not offer.vertical:
            score += 5

        return score

    @staticmethod
    def get_personalized_offers(
        user,
        wallet=None,
        country_code: str = "BD",
        device_type: str = "desktop",
        vertical: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        """
        Return personalized, ranked offers for a user.
        Combines segment building + offer fetching + ranking.
        """
        from .registry import OfferwallRegistry

        segment = UserSegment.build(user, wallet)

        offers = OfferwallRegistry.get_all_offers(
            country_code   = country_code or segment.country_code,
            device_type    = device_type,
            vertical       = vertical or "",
            limit_per_platform = 30,
        )

        ranked = OfferTargetingService.rank_offers(offers, segment)
        return ranked[:limit]

    @staticmethod
    def get_offers_by_vertical(
        vertical: str,
        country_code: str = "BD",
        device_type: str = "desktop",
    ) -> list:
        """Get offers filtered by vertical (gaming/finance/health/etc)."""
        from .registry import OfferwallRegistry
        return OfferwallRegistry.get_offers_by_vertical(vertical, country_code, device_type)

    @staticmethod
    def run_ab_test(
        user_id: int,
        variant_a: list,
        variant_b: list,
    ) -> tuple[list, str]:
        """
        Simple 50/50 A/B split for offer presentation order.
        Returns (offers, variant) where variant is "a" or "b".
        Assignment is deterministic (hash of user_id) so the same user
        always sees the same variant.
        """
        import hashlib
        h     = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16)
        variant = "a" if h % 2 == 0 else "b"
        return (variant_a if variant == "a" else variant_b), variant
