# api/djoyalty/services/advanced/InsightService.py
import logging
from django.utils import timezone
from django.db.models import Sum, Count
from ...models.advanced import LoyaltyInsight
from ...models.points import LoyaltyPoints, PointsLedger
from ...models.core import Customer, Txn

logger = logging.getLogger(__name__)

class InsightService:
    @staticmethod
    def generate_daily_insight(tenant=None, date=None):
        report_date = date or timezone.now().date()
        qs_customers = Customer.objects.all()
        qs_lp = LoyaltyPoints.objects.all()
        qs_ledger = PointsLedger.objects.filter(created_at__date=report_date)
        qs_txn = Txn.objects.filter(timestamp__date=report_date)
        if tenant:
            qs_customers = qs_customers.filter(tenant=tenant)
            qs_lp = qs_lp.filter(tenant=tenant)
            qs_ledger = qs_ledger.filter(tenant=tenant)
            qs_txn = qs_txn.filter(tenant=tenant)
        issued = qs_ledger.filter(txn_type='credit').aggregate(t=Sum('points'))['t'] or 0
        redeemed = qs_ledger.filter(txn_type='debit', source='redemption').aggregate(t=Sum('points'))['t'] or 0
        expired = qs_ledger.filter(txn_type='debit', source='expiry').aggregate(t=Sum('points'))['t'] or 0
        new_customers = qs_customers.filter(created_at__date=report_date).count()
        total_txn = qs_txn.count()
        total_revenue = qs_txn.aggregate(t=Sum('value'))['t'] or 0
        insight, _ = LoyaltyInsight.objects.update_or_create(
            tenant=tenant, report_date=report_date, period='daily',
            defaults={
                'total_customers': qs_customers.count(),
                'active_customers': qs_customers.filter(is_active=True).count(),
                'new_customers': new_customers,
                'total_points_issued': issued,
                'total_points_redeemed': redeemed,
                'total_points_expired': expired,
                'total_transactions': total_txn,
                'total_revenue': total_revenue,
            },
        )
        return insight
