# api/djoyalty/services/points/PointsAdjustmentService.py
import logging
from decimal import Decimal
from django.db import transaction
from ...models.points import LoyaltyPoints, PointsLedger, PointsAdjustment
from ...choices import LEDGER_CREDIT, LEDGER_DEBIT, LEDGER_SOURCE_ADMIN

logger = logging.getLogger(__name__)

class PointsAdjustmentService:
    @staticmethod
    @transaction.atomic
    def adjust(customer, points: Decimal, reason: str, adjusted_by: str = None, tenant=None):
        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
        )
        if points > 0:
            lp.credit(points)
            txn_type = LEDGER_CREDIT
        else:
            lp.debit(abs(points))
            txn_type = LEDGER_DEBIT
        PointsAdjustment.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer, points=points, reason=reason, adjusted_by=adjusted_by,
        )
        PointsLedger.objects.create(
            tenant=tenant or customer.tenant, customer=customer,
            txn_type=txn_type, source=LEDGER_SOURCE_ADMIN,
            points=abs(points), balance_after=lp.balance,
            description=f'Admin adjustment: {reason}',
        )
        return lp
