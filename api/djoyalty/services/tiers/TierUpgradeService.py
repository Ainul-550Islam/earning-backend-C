# api/djoyalty/services/tiers/TierUpgradeService.py
"""
TierUpgradeService — Customer এর tier upgrade logic।
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class TierUpgradeService:
    """Tier upgrade evaluation service।"""

    @staticmethod
    def check_and_upgrade(customer, tenant=None) -> object:
        """
        Customer এর lifetime_earned points এর উপর ভিত্তি করে
        tier upgrade দরকার হলে করে।
        Returns: UserTier or None
        """
        try:
            from .TierEvaluationService import TierEvaluationService
            return TierEvaluationService.evaluate(customer, tenant=tenant)
        except Exception as e:
            logger.error('TierUpgradeService.check_and_upgrade error: %s', e)
            return None

    @staticmethod
    def get_upgrade_progress(customer) -> dict:
        """
        Next tier এর জন্য progress information।
        Returns: {
            'current_tier': str,
            'next_tier': str | None,
            'current_points': Decimal,
            'points_needed': Decimal | None,
            'progress_percent': float,
        }
        """
        try:
            from ...utils import get_next_tier, get_points_needed_for_next_tier
            from ...constants import TIER_THRESHOLDS

            lp = customer.loyalty_points.first()
            lifetime_earned = lp.lifetime_earned if lp else Decimal('0')

            user_tier = customer.current_tier
            current_tier_name = user_tier.tier.name if user_tier and user_tier.tier else 'bronze'
            next_tier_name = get_next_tier(current_tier_name)
            points_needed = get_points_needed_for_next_tier(lifetime_earned, current_tier_name)

            if next_tier_name and points_needed is not None:
                next_threshold = TIER_THRESHOLDS.get(next_tier_name, Decimal('0'))
                current_threshold = TIER_THRESHOLDS.get(current_tier_name, Decimal('0'))
                tier_range = next_threshold - current_threshold
                progress_in_tier = lifetime_earned - current_threshold
                if tier_range > 0:
                    progress_percent = float(min(progress_in_tier / tier_range * 100, 100))
                else:
                    progress_percent = 100.0
            else:
                progress_percent = 100.0

            return {
                'current_tier': current_tier_name,
                'next_tier': next_tier_name,
                'current_points': lifetime_earned,
                'points_needed': points_needed,
                'progress_percent': round(progress_percent, 1),
            }
        except Exception as e:
            logger.error('TierUpgradeService.get_upgrade_progress error: %s', e)
            return {
                'current_tier': 'bronze',
                'next_tier': None,
                'current_points': Decimal('0'),
                'points_needed': None,
                'progress_percent': 0.0,
            }

    @staticmethod
    def force_upgrade(customer, target_tier_name: str, reason: str = '', tenant=None) -> object:
        """
        Admin: Customer কে নির্দিষ্ট tier এ force upgrade করো।
        """
        try:
            from ...models.tiers import LoyaltyTier, UserTier, TierHistory
            target_tier = LoyaltyTier.objects.filter(name=target_tier_name).first()
            if not target_tier:
                logger.error('TierUpgradeService.force_upgrade: tier %s not found', target_tier_name)
                return None
            current = customer.user_tiers.filter(is_current=True).first()
            if current and current.tier == target_tier:
                return current
            lp = customer.loyalty_points.first()
            balance = lp.lifetime_earned if lp else Decimal('0')
            if current:
                TierHistory.objects.create(
                    customer=customer,
                    from_tier=current.tier,
                    to_tier=target_tier,
                    change_type='upgrade',
                    reason=reason or 'Admin forced upgrade',
                    points_at_change=balance,
                )
                current.is_current = False
                current.save(update_fields=['is_current'])
            else:
                TierHistory.objects.create(
                    customer=customer,
                    from_tier=None,
                    to_tier=target_tier,
                    change_type='initial',
                    reason=reason or 'Admin forced upgrade',
                    points_at_change=balance,
                )
            new_user_tier = UserTier.objects.create(
                tenant=tenant or customer.tenant,
                customer=customer,
                tier=target_tier,
                is_current=True,
                points_at_assignment=balance,
            )
            logger.info('Force upgraded %s to %s', customer, target_tier_name)
            return new_user_tier
        except Exception as e:
            logger.error('TierUpgradeService.force_upgrade error: %s', e)
            return None
