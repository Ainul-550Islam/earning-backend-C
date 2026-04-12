# api/offer_inventory/ai_optimization/conversion_rate_optimizer.py
"""
Conversion Rate Optimizer.
Reorders, filters, and enriches offer lists
to maximize platform conversion rate.
"""
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ConversionRateOptimizer:
    """
    Optimizes offer presentation order using:
    - Historical CVR per offer
    - User interest match
    - Time-of-day patterns
    - Country/device match bonuses
    """

    @staticmethod
    def get_optimized_order(offers: list, user=None,
                            country: str = '', device: str = '') -> list:
        """Return offers sorted for maximum conversion."""
        if not offers:
            return []

        scored = []
        for offer in offers:
            score = ConversionRateOptimizer._score(offer, user, country, device)
            scored.append((score, offer))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [offer for _, offer in scored]

    @staticmethod
    def _score(offer, user, country: str, device: str) -> float:
        base      = float(offer.conversion_rate or 0) * 2.0
        payout_s  = float(offer.payout_amount or 0) * 0.5
        featured  = 5.0 if offer.is_featured else 0.0
        interest  = ConversionRateOptimizer._interest_bonus(offer, user)
        geo       = 3.0 if ConversionRateOptimizer._geo_match(offer, country) else 0.0
        time_b    = ConversionRateOptimizer._time_bonus()
        return base + payout_s + featured + interest + geo + time_b

    @staticmethod
    def _interest_bonus(offer, user) -> float:
        if not user or not offer.category_id:
            return 0.0
        try:
            from api.offer_inventory.models import UserInterest
            interest = UserInterest.objects.filter(
                user=user, category_id=offer.category_id
            ).values_list('score', flat=True).first()
            return float(interest or 0) * 5.0
        except Exception:
            return 0.0

    @staticmethod
    def _geo_match(offer, country: str) -> bool:
        if not country:
            return False
        try:
            for rule in offer.visibility_rules.filter(
                rule_type='country', operator='include', is_active=True
            ):
                if country in (rule.values or []):
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _time_bonus() -> float:
        """Peak hours (BD evening 6–10 PM = UTC 12–16) bonus."""
        from django.utils import timezone
        hour = timezone.now().hour
        return 2.0 if 12 <= hour <= 16 else 0.0

    @staticmethod
    def compute_all_cvr():
        """Batch recalculate CVR for all active offers."""
        from api.offer_inventory.models import Offer, Click, Conversion
        from django.db.models import Count, Q

        for offer in Offer.objects.filter(status='active'):
            clicks = Click.objects.filter(offer=offer, is_fraud=False).count()
            convs  = Conversion.objects.filter(
                offer=offer, status__name='approved'
            ).count()
            if clicks > 0:
                cvr = round(convs / clicks * 100, 2)
                Offer.objects.filter(id=offer.id).update(conversion_rate=cvr)
