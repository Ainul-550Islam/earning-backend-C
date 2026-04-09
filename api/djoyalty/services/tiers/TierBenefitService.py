# api/djoyalty/services/tiers/TierBenefitService.py
"""
TierBenefitService — Customer এর tier benefits retrieve করে।
"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class TierBenefitService:
    """Tier benefit management service।"""

    @staticmethod
    def get_benefits_for_customer(customer) -> List:
        """
        Customer এর current tier এর সব active benefits।
        Tier না থাকলে empty list return করে।
        """
        try:
            user_tier = customer.current_tier
            if not user_tier or not user_tier.tier:
                return []
            from ...models.tiers import TierBenefit
            return list(TierBenefit.objects.filter(tier=user_tier.tier, is_active=True))
        except Exception as e:
            logger.error('TierBenefitService.get_benefits_for_customer error: %s', e)
            return []

    @staticmethod
    def get_benefits_for_tier(tier_id: int) -> List:
        """
        নির্দিষ্ট tier এর সব active benefits।
        """
        try:
            from ...models.tiers import TierBenefit
            return list(TierBenefit.objects.filter(tier_id=tier_id, is_active=True))
        except Exception as e:
            logger.error('TierBenefitService.get_benefits_for_tier error: %s', e)
            return []

    @staticmethod
    def get_all_tier_benefits_grouped() -> dict:
        """
        সব tier এর benefits tier_name → [benefits] format এ।
        Admin overview এর জন্য।
        """
        try:
            from ...models.tiers import LoyaltyTier, TierBenefit
            result = {}
            tiers = LoyaltyTier.objects.filter(is_active=True).prefetch_related('benefits').order_by('rank')
            for tier in tiers:
                result[tier.name] = list(tier.benefits.filter(is_active=True))
            return result
        except Exception as e:
            logger.error('TierBenefitService.get_all_tier_benefits_grouped error: %s', e)
            return {}

    @staticmethod
    def add_benefit(tier_id: int, title: str, description: str = None,
                    benefit_type: str = 'perk', value: str = None) -> object:
        """
        Tier এ নতুন benefit যোগ করো।
        """
        from ...models.tiers import TierBenefit
        return TierBenefit.objects.create(
            tier_id=tier_id,
            title=title,
            description=description,
            benefit_type=benefit_type,
            value=value,
            is_active=True,
        )

    @staticmethod
    def deactivate_benefit(benefit_id: int) -> bool:
        """Benefit deactivate করো।"""
        try:
            from ...models.tiers import TierBenefit
            count = TierBenefit.objects.filter(id=benefit_id).update(is_active=False)
            return count > 0
        except Exception as e:
            logger.error('TierBenefitService.deactivate_benefit error: %s', e)
            return False
