# api/djoyalty/services/points/PointsTransferService.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ...models.points import PointsTransfer, LoyaltyPoints, PointsLedger
from ...choices import LEDGER_CREDIT, LEDGER_DEBIT, LEDGER_SOURCE_TRANSFER
from ...exceptions import InsufficientPointsError, PointsTransferError

logger = logging.getLogger(__name__)

class PointsTransferService:
    @staticmethod
    @transaction.atomic
    def transfer(from_customer, to_customer, points: Decimal, note: str = '', tenant=None) -> PointsTransfer:
        if from_customer == to_customer:
            raise PointsTransferError('Cannot transfer to yourself.')
        from_lp = from_customer.loyalty_points.first()
        if not from_lp or from_lp.balance < points:
            raise InsufficientPointsError(
                available=from_lp.balance if from_lp else 0, required=points
            )
        to_lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=to_customer,
            defaults={'tenant': tenant or to_customer.tenant, 'balance': Decimal('0')},
        )
        from_lp.debit(points)
        to_lp.credit(points)
        transfer = PointsTransfer.objects.create(
            tenant=tenant, from_customer=from_customer,
            to_customer=to_customer, points=points, status='completed',
            note=note, completed_at=timezone.now(),
        )
        PointsLedger.objects.create(
            tenant=tenant, customer=from_customer,
            txn_type=LEDGER_DEBIT, source=LEDGER_SOURCE_TRANSFER,
            points=points, balance_after=from_lp.balance,
            description=f'Transfer to {to_customer.code}',
        )
        PointsLedger.objects.create(
            tenant=tenant, customer=to_customer,
            txn_type=LEDGER_CREDIT, source=LEDGER_SOURCE_TRANSFER,
            points=points, balance_after=to_lp.balance,
            description=f'Transfer from {from_customer.code}',
        )
        return transfer
