# api/djoyalty/services/redemption/RewardCatalogService.py
"""
RewardCatalogService — Customer এর জন্য available rewards দেখায়।
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class RewardCatalogService:
    """Reward catalog service — available redemptions for a customer।"""

    @staticmethod
    def get_available_rewards(customer, tenant=None):
        """
        Customer এর current balance এর মধ্যে afford করতে পারবে এমন
        সব active redemption rules।
        """
        try:
            from ...models.redemption import RedemptionRule
            from django.db.models import Q

            lp = customer.loyalty_points.first()
            balance = lp.balance if lp else Decimal('0')

            qs = RedemptionRule.objects.filter(
                is_active=True,
                points_required__lte=balance,
            ).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=timezone.now())
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now())
            )

            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            elif hasattr(customer, 'tenant') and customer.tenant:
                qs = qs.filter(Q(tenant=customer.tenant) | Q(tenant__isnull=True))

            # Check tier requirements
            user_tier = customer.current_tier
            tier_name = user_tier.tier.name if user_tier and user_tier.tier else 'bronze'
            from ...choices import TIER_RANK
            customer_tier_rank = TIER_RANK.get(tier_name, 1)

            filtered = []
            for rule in qs.order_by('points_required'):
                if rule.min_tier:
                    required_rank = TIER_RANK.get(rule.min_tier.name, 1)
                    if customer_tier_rank < required_rank:
                        continue
                filtered.append(rule)

            return filtered
        except Exception as e:
            logger.error('RewardCatalogService.get_available_rewards error: %s', e)
            return []

    @staticmethod
    def get_all_rewards(tenant=None):
        """
        Tenant এর সব active rewards — admin catalog view।
        """
        try:
            from ...models.redemption import RedemptionRule
            from django.db.models import Q
            qs = RedemptionRule.objects.filter(is_active=True).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=timezone.now())
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now())
            )
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            return qs.order_by('points_required')
        except Exception as e:
            logger.error('RewardCatalogService.get_all_rewards error: %s', e)
            return []

    @staticmethod
    def get_reward_summary(customer, tenant=None) -> dict:
        """
        Customer কে সংক্ষেপে reward catalog summary দাও।
        """
        try:
            available = RewardCatalogService.get_available_rewards(customer, tenant=tenant)
            all_rewards = RewardCatalogService.get_all_rewards(tenant=tenant)
            lp = customer.loyalty_points.first()
            balance = lp.balance if lp else Decimal('0')

            return {
                'current_balance': str(balance),
                'available_rewards_count': len(available),
                'total_rewards_count': all_rewards.count() if hasattr(all_rewards, 'count') else len(all_rewards),
                'cheapest_available': str(available[0].points_required) if available else None,
                'most_expensive_available': str(available[-1].points_required) if available else None,
            }
        except Exception as e:
            logger.error('RewardCatalogService.get_reward_summary error: %s', e)
            return {}
