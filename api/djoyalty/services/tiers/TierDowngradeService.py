# api/djoyalty/services/tiers/TierDowngradeService.py
"""
TierDowngradeService — Customer এর tier downgrade logic।
Protection period সহ।
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class TierDowngradeService:
    """Tier downgrade evaluation service।"""

    @staticmethod
    def check_and_downgrade(customer, tenant=None) -> object:
        """
        Customer এর tier evaluate করে downgrade দরকার হলে করে।
        Protection period active থাকলে downgrade করে না।
        Returns: UserTier or None
        """
        try:
            from .TierEvaluationService import TierEvaluationService
            return TierEvaluationService.evaluate(customer, tenant=tenant)
        except Exception as e:
            logger.error('TierDowngradeService.check_and_downgrade error: %s', e)
            return None

    @staticmethod
    def is_downgrade_protected(customer) -> bool:
        """
        Customer এর tier downgrade protected কিনা চেক করো।
        TierConfig এর downgrade_protection_months অনুযায়ী।
        """
        try:
            user_tier = customer.current_tier
            if not user_tier:
                return False
            from ...models.tiers import TierConfig
            tenant = getattr(customer, 'tenant', None)
            config = None
            if tenant:
                config = TierConfig.objects.filter(tenant=tenant).first()
            protection_months = config.downgrade_protection_months if config else 3
            protection_cutoff = timezone.now() - timedelta(days=protection_months * 30)
            return user_tier.assigned_at >= protection_cutoff
        except Exception as e:
            logger.error('TierDowngradeService.is_downgrade_protected error: %s', e)
            return False

    @staticmethod
    def force_downgrade(customer, target_tier_name: str, reason: str = '', tenant=None) -> object:
        """
        Protection 무視 하고 강제 downgrade।
        Admin action only।
        """
        try:
            from ...models.tiers import LoyaltyTier, UserTier, TierHistory
            target_tier = LoyaltyTier.objects.filter(name=target_tier_name).first()
            if not target_tier:
                logger.error('TierDowngradeService.force_downgrade: tier %s not found', target_tier_name)
                return None
            current = customer.user_tiers.filter(is_current=True).first()
            if current:
                if current.tier == target_tier:
                    return current
                lp = customer.loyalty_points.first()
                balance = lp.lifetime_earned if lp else Decimal('0')
                TierHistory.objects.create(
                    customer=customer,
                    from_tier=current.tier,
                    to_tier=target_tier,
                    change_type='downgrade',
                    reason=reason or 'Admin forced downgrade',
                    points_at_change=balance,
                )
                current.is_current = False
                current.save(update_fields=['is_current'])
            new_user_tier = UserTier.objects.create(
                tenant=tenant or customer.tenant,
                customer=customer,
                tier=target_tier,
                is_current=True,
            )
            logger.info('Force downgraded %s to %s', customer, target_tier_name)
            return new_user_tier
        except Exception as e:
            logger.error('TierDowngradeService.force_downgrade error: %s', e)
            return None
