# api/djoyalty/services/points/PointsLedgerService.py
import logging
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from ...models.points import PointsLedger

logger = logging.getLogger(__name__)

class PointsLedgerService:
    @staticmethod
    def get_balance_from_ledger(customer) -> Decimal:
        result = PointsLedger.objects.filter(customer=customer).aggregate(
            total=Sum('points', filter=Q(txn_type='credit')) - Sum('points', filter=Q(txn_type='debit'))
        )
        return result.get('total') or Decimal('0')

    @staticmethod
    def get_expiring_points(customer, days=30) -> Decimal:
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(days=days)
        result = PointsLedger.objects.filter(
            customer=customer, txn_type='credit',
            expires_at__isnull=False, expires_at__lte=cutoff, expires_at__gt=timezone.now(),
            remaining_points__gt=0,
        ).aggregate(total=Sum('remaining_points'))
        return result.get('total') or Decimal('0')

    @staticmethod
    def get_ledger_history(customer, limit=50):
        return PointsLedger.objects.filter(customer=customer).order_by('-created_at')[:limit]
