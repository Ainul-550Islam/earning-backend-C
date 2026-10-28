# api/djoyalty/services/CustomerProfileService.py
"""
CustomerProfileService -- Customer CRUD + full stats।
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class CustomerProfileService:

    @staticmethod
    def get_or_create(code: str, tenant=None, **kwargs):
        """Customer get-or-create by code।"""
        from ..models.core import Customer
        code = code.strip().upper()
        customer, created = Customer.objects.get_or_create(
            code=code,
            defaults={
                'tenant': tenant,
                'is_active': True,
                **kwargs,
            },
        )
        if created:
            logger.info('CustomerProfileService: created customer %s', code)
        return customer, created

    @staticmethod
    def get_full_stats(customer) -> dict:
        """Customer এর complete stats একটি dict এ।"""
        try:
            from ..models.points import LoyaltyPoints
            lp = customer.loyalty_points.first()
            txns = customer.transactions.all()
            ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
            streak = customer.daily_streaks.filter(is_active=True).first()

            total_spend = txns.filter(value__gt=0).aggregate(s=Sum('value'))['s'] or Decimal('0')
            txn_count = txns.count()
            badge_count = customer.user_badges.count()
            milestone_count = customer.user_milestones.count()

            from ..utils import get_next_tier, get_points_needed_for_next_tier
            tier_name = ut.tier.name if ut and ut.tier else 'bronze'
            lifetime = lp.lifetime_earned if lp else Decimal('0')
            next_tier = get_next_tier(tier_name)
            pts_needed = get_points_needed_for_next_tier(lifetime, tier_name) if next_tier else None

            return {
                'customer_id': customer.id,
                'code': customer.code,
                'full_name': customer.full_name,
                'loyalty_number': customer.loyalty_number,
                'is_active': customer.is_active,
                'points_balance': str(lp.balance if lp else 0),
                'lifetime_earned': str(lifetime),
                'lifetime_redeemed': str(lp.lifetime_redeemed if lp else 0),
                'lifetime_expired': str(lp.lifetime_expired if lp else 0),
                'pending_balance': str(lp.pending_balance if lp else 0),
                'current_tier': tier_name,
                'tier_label': ut.tier.label if ut and ut.tier else tier_name.title(),
                'tier_icon': ut.tier.icon if ut and ut.tier else '⭐',
                'tier_color': ut.tier.color if ut and ut.tier else '#888888',
                'earn_multiplier': str(ut.tier.earn_multiplier if ut and ut.tier else '1.0'),
                'next_tier': next_tier,
                'points_needed_for_next_tier': str(pts_needed) if pts_needed is not None else None,
                'total_transactions': txn_count,
                'total_spend': str(total_spend),
                'badge_count': badge_count,
                'milestone_count': milestone_count,
                'current_streak': streak.current_streak if streak else 0,
                'longest_streak': streak.longest_streak if streak else 0,
                'member_since': customer.created_at.isoformat(),
                'last_activity': customer.last_activity_at.isoformat() if customer.last_activity_at else None,
            }
        except Exception as e:
            logger.error('CustomerProfileService.get_full_stats error for %s: %s', customer, e)
            return {}

    @staticmethod
    def update_last_activity(customer):
        """Customer এর last_activity_at update করো।"""
        try:
            customer.last_activity_at = timezone.now()
            customer.save(update_fields=['last_activity_at'])
        except Exception as e:
            logger.error('CustomerProfileService.update_last_activity error: %s', e)

    @staticmethod
    def deactivate(customer, reason: str = ''):
        """Customer soft-deactivate।"""
        from ..cache_backends import DjoyaltyCache
        customer.is_active = False
        customer.save(update_fields=['is_active'])
        DjoyaltyCache.flush_customer_cache(customer.id)
        logger.info('CustomerProfileService: deactivated %s -- %s', customer.code, reason)

    @staticmethod
    def reactivate(customer):
        """Customer reactivate।"""
        customer.is_active = True
        customer.save(update_fields=['is_active'])
        logger.info('CustomerProfileService: reactivated %s', customer.code)

    @staticmethod
    def search(query: str, tenant=None, limit: int = 20):
        """Customer search by code, name, email, phone।"""
        from ..models.core import Customer
        qs = Customer.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        qs = qs.filter(
            Q(code__icontains=query) |
            Q(firstname__icontains=query) |
            Q(lastname__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(loyalty_number__icontains=query)
        )
        return qs.select_related('tenant')[:limit]
