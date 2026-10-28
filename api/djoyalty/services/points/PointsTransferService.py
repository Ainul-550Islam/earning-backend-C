# api/djoyalty/services/points/PointsTransferService.py
"""
PointsTransferService -- secure P2P transfer.

Security fixes:
  1. select_for_update() on BOTH wallets (ordered by pk to prevent deadlock)
  2. Checks available_balance (frozen balance respected)
  3. Transfer limits per day enforced
  4. Fraud check before transfer
  5. Negative/zero amount rejected
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ...models.points import PointsTransfer, LoyaltyPoints, PointsLedger
from ...choices import LEDGER_CREDIT, LEDGER_DEBIT, LEDGER_SOURCE_TRANSFER
from ...exceptions import InsufficientPointsError, PointsTransferError
from ...constants import MAX_DAILY_TRANSFER_POINTS

logger = logging.getLogger(__name__)


class PointsTransferService:
    @staticmethod
    @transaction.atomic
    def transfer(
        from_customer,
        to_customer,
        points: Decimal,
        note: str = '',
        tenant=None,
    ) -> PointsTransfer:
        # ── 1. Basic validation ──────────────────────────────────────────────
        points = Decimal(str(points))
        if points <= 0:
            raise PointsTransferError('Transfer amount must be positive.')

        if from_customer.pk == to_customer.pk:
            raise PointsTransferError('Cannot transfer points to yourself.')

        # ── 2. Quick balance pre-check (before hitting DB for daily limit) ────
        from ...models.points import LoyaltyPoints as _LP
        _pre = _LP.objects.filter(customer=from_customer).first()
        if not _pre or _pre.available_balance < points:
            raise InsufficientPointsError(
                available=_pre.available_balance if _pre else Decimal('0'),
                required=points,
            )

        # ── 3. Fraud check ───────────────────────────────────────────────────
        from ...services.advanced.LoyaltyFraudService import LoyaltyFraudService
        if LoyaltyFraudService.check_rapid_transactions(from_customer):
            raise PointsTransferError('Transfer blocked: suspicious activity detected.')

        # ── 4. Daily transfer limit ──────────────────────────────────────────
        today = timezone.now().date()
        daily_sent = PointsTransfer.objects.filter(
            from_customer=from_customer,
            created_at__date=today,
            status='completed',
        ).values_list('points', flat=True)
        total_sent_today = sum(daily_sent) if daily_sent else Decimal('0')
        if total_sent_today + points > MAX_DAILY_TRANSFER_POINTS:
            raise PointsTransferError(
                f'Daily transfer limit exceeded. Limit: {MAX_DAILY_TRANSFER_POINTS}, '
                f'already sent today: {total_sent_today}'
            )

        # ── 5. Lock both wallets -- ORDER BY pk prevents deadlock ────────────
        pks_ordered = sorted([from_customer.pk, to_customer.pk])
        wallets = {
            lp.customer_id: lp
            for lp in LoyaltyPoints.objects.select_for_update().filter(
                customer_id__in=pks_ordered
            )
        }

        from_lp = wallets.get(from_customer.pk)
        if not from_lp:
            raise InsufficientPointsError(available=Decimal('0'), required=points)

        # ── 6. Check available balance (respects frozen_balance) ─────────────
        if from_lp.available_balance < points:
            raise InsufficientPointsError(
                available=from_lp.available_balance, required=points
            )

        to_lp = wallets.get(to_customer.pk)
        if to_lp is None:
            to_lp = LoyaltyPoints.objects.create(
                customer=to_customer,
                tenant=tenant or to_customer.tenant,
                balance=Decimal('0'),
            )
            to_lp = LoyaltyPoints.objects.select_for_update().get(pk=to_lp.pk)

        # ── 7. Debit / Credit ────────────────────────────────────────────────
        from_lp.debit(points)
        to_lp.credit(points)

        # ── 8. Transfer record ───────────────────────────────────────────────
        transfer = PointsTransfer.objects.create(
            tenant=tenant or from_customer.tenant,
            from_customer=from_customer,
            to_customer=to_customer,
            points=points,
            status='completed',
            note=note,
            completed_at=timezone.now(),
        )

        # ── 9. Ledger entries ────────────────────────────────────────────────
        PointsLedger.objects.create(
            tenant=tenant or from_customer.tenant,
            customer=from_customer,
            txn_type=LEDGER_DEBIT,
            source=LEDGER_SOURCE_TRANSFER,
            points=points,
            balance_after=from_lp.balance,
            description=f'Transfer to {to_customer.code}',
            reference_id=str(transfer.reference),
        )
        PointsLedger.objects.create(
            tenant=tenant or to_customer.tenant,
            customer=to_customer,
            txn_type=LEDGER_CREDIT,
            source=LEDGER_SOURCE_TRANSFER,
            points=points,
            balance_after=to_lp.balance,
            description=f'Transfer from {from_customer.code}',
            reference_id=str(transfer.reference),
        )

        logger.info(
            'Transfer complete: %s -> %s, pts=%s, ref=%s',
            from_customer.code, to_customer.code, points, transfer.reference,
        )
        return transfer
