# api/djoyalty/services/LoyaltyAnalyticsService.py
"""
LoyaltyAnalyticsService -- aggregate analytics and insights।
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class LoyaltyAnalyticsService:

    @staticmethod
    def get_dashboard_summary(tenant=None) -> dict:
        """Admin dashboard summary।"""
        try:
            from ..models.core import Customer, Txn
            from ..models.points import LoyaltyPoints, PointsLedger
            from ..models.redemption import RedemptionRequest
            from ..models.tiers import UserTier

            base_q = Q(tenant=tenant) if tenant else Q()

            customers = Customer.objects.filter(base_q)
            lp_qs = LoyaltyPoints.objects.filter(base_q)
            ledger_qs = PointsLedger.objects.filter(base_q)
            redemption_qs = RedemptionRequest.objects.filter(base_q)

            total_customers = customers.count()
            active_customers = customers.filter(is_active=True).count()
            new_today = customers.filter(created_at__date=timezone.now().date()).count()
            new_this_month = customers.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()

            total_balance = lp_qs.aggregate(s=Sum('balance'))['s'] or Decimal('0')
            total_issued = ledger_qs.filter(txn_type='credit').aggregate(s=Sum('points'))['s'] or Decimal('0')
            total_redeemed = ledger_qs.filter(txn_type='debit', source='redemption').aggregate(s=Sum('points'))['s'] or Decimal('0')
            total_expired = ledger_qs.filter(txn_type='debit', source='expiry').aggregate(s=Sum('points'))['s'] or Decimal('0')

            pending_redemptions = redemption_qs.filter(status='pending').count()
            pending_points = redemption_qs.filter(status='pending').aggregate(s=Sum('points_used'))['s'] or Decimal('0')

            tier_distribution = {}
            for ut in UserTier.objects.filter(is_current=True).select_related('tier'):
                name = ut.tier.name if ut.tier else 'unknown'
                tier_distribution[name] = tier_distribution.get(name, 0) + 1

            redemption_rate = float(total_redeemed / total_issued * 100) if total_issued > 0 else 0.0

            return {
                'customers': {
                    'total': total_customers,
                    'active': active_customers,
                    'new_today': new_today,
                    'new_this_month': new_this_month,
                },
                'points': {
                    'total_balance': str(total_balance),
                    'total_issued': str(total_issued),
                    'total_redeemed': str(total_redeemed),
                    'total_expired': str(total_expired),
                    'redemption_rate_pct': round(redemption_rate, 2),
                },
                'redemptions': {
                    'pending_count': pending_redemptions,
                    'pending_points': str(pending_points),
                },
                'tier_distribution': tier_distribution,
                'generated_at': timezone.now().isoformat(),
            }
        except Exception as e:
            logger.error('LoyaltyAnalyticsService.get_dashboard_summary error: %s', e)
            return {}

    @staticmethod
    def get_top_earners(tenant=None, limit: int = 10, days: int = 30) -> list:
        """Recent top earners।"""
        try:
            from ..models.points import LoyaltyPoints
            cutoff = timezone.now() - timedelta(days=days)
            qs = LoyaltyPoints.objects.select_related('customer')
            if tenant:
                qs = qs.filter(tenant=tenant)
            return list(qs.order_by('-lifetime_earned')[:limit].values(
                'customer__code', 'customer__firstname', 'customer__lastname',
                'balance', 'lifetime_earned', 'lifetime_redeemed',
            ))
        except Exception as e:
            logger.error('LoyaltyAnalyticsService.get_top_earners error: %s', e)
            return []

    @staticmethod
    def get_redemption_stats(tenant=None, days: int = 30) -> dict:
        """Redemption analytics।"""
        try:
            from ..models.redemption import RedemptionRequest
            from django.db.models import Avg
            cutoff = timezone.now() - timedelta(days=days)
            qs = RedemptionRequest.objects.filter(created_at__gte=cutoff)
            if tenant:
                qs = qs.filter(tenant=tenant)
            stats = qs.aggregate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected')),
                pending=Count('id', filter=Q(status='pending')),
                avg_points=Avg('points_used'),
                total_points=Sum('points_used'),
            )
            return {
                'period_days': days,
                'total_requests': stats['total'] or 0,
                'approved': stats['approved'] or 0,
                'rejected': stats['rejected'] or 0,
                'pending': stats['pending'] or 0,
                'avg_points_per_request': str(round(stats['avg_points'] or 0, 2)),
                'total_points_redeemed': str(stats['total_points'] or 0),
            }
        except Exception as e:
            logger.error('LoyaltyAnalyticsService.get_redemption_stats error: %s', e)
            return {}

    @staticmethod
    def get_tier_upgrade_velocity(tenant=None, days: int = 30) -> dict:
        """Recent tier upgrade count।"""
        try:
            from ..models.tiers import TierHistory
            cutoff = timezone.now() - timedelta(days=days)
            qs = TierHistory.objects.filter(changed_at__gte=cutoff, change_type='upgrade')
            if tenant:
                qs = qs.filter(customer__tenant=tenant)
            return {
                'period_days': days,
                'total_upgrades': qs.count(),
                'total_downgrades': TierHistory.objects.filter(
                    changed_at__gte=cutoff, change_type='downgrade',
                    **(({'customer__tenant': tenant}) if tenant else {}),
                ).count(),
            }
        except Exception as e:
            logger.error('LoyaltyAnalyticsService.get_tier_upgrade_velocity error: %s', e)
            return {}
