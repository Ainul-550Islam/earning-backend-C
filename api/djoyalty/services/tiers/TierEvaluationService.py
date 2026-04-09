# api/djoyalty/services/tiers/TierEvaluationService.py
import logging
from decimal import Decimal
from ...utils import get_tier_for_points

logger = logging.getLogger(__name__)

class TierEvaluationService:
    @staticmethod
    def evaluate(customer, tenant=None):
        try:
            lp = customer.loyalty_points.first()
            balance = lp.lifetime_earned if lp else Decimal('0')
            new_tier_name = get_tier_for_points(balance)
            from ...models.tiers import LoyaltyTier, UserTier
            tier_obj = LoyaltyTier.objects.filter(
                name=new_tier_name,
                tenant=tenant or customer.tenant,
            ).first()
            if not tier_obj:
                tier_obj = LoyaltyTier.objects.filter(name=new_tier_name).first()
            if not tier_obj:
                return None
            current = customer.user_tiers.filter(is_current=True).first()
            if current and current.tier == tier_obj:
                return current
            if current:
                change_type = 'upgrade' if tier_obj.rank > current.tier.rank else 'downgrade'
                current.is_current = False
                current.save(update_fields=['is_current'])
                from ...models.tiers import TierHistory
                TierHistory.objects.create(
                    customer=customer, from_tier=current.tier,
                    to_tier=tier_obj, change_type=change_type,
                    points_at_change=balance,
                )
            else:
                change_type = 'initial'
                from ...models.tiers import TierHistory
                TierHistory.objects.create(
                    customer=customer, from_tier=None,
                    to_tier=tier_obj, change_type=change_type,
                    points_at_change=balance,
                )
            new_user_tier = UserTier.objects.create(
                tenant=tenant or customer.tenant,
                customer=customer, tier=tier_obj, is_current=True,
                points_at_assignment=balance,
            )
            logger.info('Tier %s for %s', new_tier_name, customer)
            return new_user_tier
        except Exception as e:
            logger.error('TierEvaluationService error: %s', e)
            return None
