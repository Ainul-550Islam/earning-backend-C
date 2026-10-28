# api/djoyalty/reports.py
"""
Djoyalty Reports -- Pre-built loyalty business reports।
Monthly summary, tier report, cashout report, fraud report।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class LoyaltyReports:
    """Pre-built monthly, quarterly, and annual reports।"""

    @staticmethod
    def monthly_summary(year: int = None, month: int = None, tenant=None) -> dict:
        """Generate monthly loyalty program summary।"""
        from django.db.models import Sum, Count
        from .models.core import Customer
        from .models.points import LoyaltyPoints, PointsLedger
        from .models.cashout import CashoutRequest
        from .models.redemption import RedemptionHistory

        now = timezone.now()
        if not year:
            year = now.year
        if not month:
            month = now.month

        # Month boundaries
        from django.utils import timezone as tz
        import calendar
        start = tz.datetime(year, month, 1, tzinfo=tz.utc)
        end_day = calendar.monthrange(year, month)[1]
        end = tz.datetime(year, month, end_day, 23, 59, 59, tzinfo=tz.utc)

        def q(qs):
            return qs.filter(tenant=tenant) if tenant else qs

        # New customers
        new_customers = q(Customer.objects.filter(
            created_at__range=(start, end)
        )).count()

        # Points issued
        points_issued = q(PointsLedger.objects.filter(
            txn_type='credit', is_reversed=False, created_at__range=(start, end)
        )).aggregate(total=Sum('points'))['total'] or Decimal('0')

        # Points redeemed
        points_redeemed = q(PointsLedger.objects.filter(
            txn_type='debit', is_reversed=False, created_at__range=(start, end)
        )).aggregate(total=Sum('points'))['total'] or Decimal('0')

        # Cashouts
        cashout_data = q(CashoutRequest.objects.filter(
            status='completed', created_at__range=(start, end)
        )).aggregate(count=Count('id'), total=Sum('cash_amount'))

        # Outstanding liability
        outstanding = q(LoyaltyPoints.objects.filter(balance__gt=0)).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0')

        return {
            'period': f'{year}-{month:02d}',
            'new_customers': new_customers,
            'points_issued': str(points_issued),
            'points_redeemed': str(points_redeemed),
            'redemption_rate': f'{float(points_redeemed) / max(float(points_issued), 1) * 100:.1f}%',
            'cashouts_completed': cashout_data.get('count') or 0,
            'cashout_total_bdt': str(cashout_data.get('total') or Decimal('0')),
            'outstanding_liability': str(outstanding),
            'generated_at': timezone.now().isoformat(),
        }

    @staticmethod
    def tier_distribution(tenant=None) -> dict:
        """Get customer distribution across tiers।"""
        from django.db.models import Count
        from .models.tiers import UserTier

        qs = UserTier.objects.filter(is_current=True).select_related('tier')
        if tenant:
            qs = qs.filter(tenant=tenant)

        dist = {}
        for ut in qs.values('tier__name').annotate(count=Count('id')):
            dist[ut['tier__name']] = ut['count']
        return dist

    @staticmethod
    def top_earners(n: int = 10, tenant=None) -> list:
        """Get top N customers by lifetime earned points।"""
        from .models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects.filter(lifetime_earned__gt=0)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.order_by('-lifetime_earned')
            .select_related('customer')[:n]
            .values('customer__code', 'customer__firstname', 'lifetime_earned', 'balance')
        )

    @staticmethod
    def fraud_report(days: int = 30, tenant=None) -> dict:
        """Get fraud statistics for last N days।"""
        from .models.advanced import PointsAbuseLog
        from django.db.models import Count
        cutoff = timezone.now() - timedelta(days=days)
        qs = PointsAbuseLog.objects.filter(created_at__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'period_days': days,
            'total_flags': qs.count(),
            'unresolved': qs.filter(is_resolved=False).count(),
            'by_risk_level': dict(
                qs.values('risk_level').annotate(count=Count('id')).values_list('risk_level', 'count')
            ),
            'by_type': dict(
                qs.values('abuse_type').annotate(count=Count('id')).values_list('abuse_type', 'count')
            ),
        }
