# api/djoyalty/services/redemption/RedemptionService.py
"""
RedemptionService -- secure redemption flow.

Security fixes:
  1. select_for_update() on LoyaltyPoints in create_request (race condition fix)
  2. available_balance used instead of raw balance (frozen balance respected)
  3. Fraud check (daily limit) before debit
  4. Reject refund uses select_for_update
  5. Negative/zero amount rejected
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ...models.redemption import RedemptionRequest, RedemptionHistory
from ...models.points import LoyaltyPoints, PointsLedger
from ...choices import LEDGER_DEBIT, LEDGER_SOURCE_REDEMPTION, LEDGER_CREDIT
from ...exceptions import InsufficientPointsError, RedemptionMinimumNotMetError
from ...constants import MIN_REDEMPTION_POINTS, DEFAULT_POINT_VALUE

logger = logging.getLogger(__name__)


class RedemptionService:
    @staticmethod
    @transaction.atomic
    def create_request(
        customer,
        points: Decimal,
        redemption_type: str = 'cashback',
        tenant=None,
    ) -> RedemptionRequest:
        points = Decimal(str(points))

        # ── 1. Input validation ──────────────────────────────────────────────
        if points <= 0:
            raise ValueError('Redemption points must be positive.')

        if points < MIN_REDEMPTION_POINTS:
            raise RedemptionMinimumNotMetError()

        # ── 2. Fraud / daily limit check ─────────────────────────────────────
        from ...services.advanced.LoyaltyFraudService import LoyaltyFraudService
        if LoyaltyFraudService.check_daily_redemption(customer, points):
            raise ValueError('Daily redemption limit exceeded.')
        if LoyaltyFraudService.check_rapid_transactions(customer):
            raise ValueError('Redemption blocked: suspicious activity detected.')

        # ── 3. Lock wallet (prevents double-spend race condition) ────────────
        lp = (
            LoyaltyPoints.objects
            .select_for_update()
            .filter(customer=customer)
            .first()
        )
        if not lp or lp.available_balance < points:
            raise InsufficientPointsError(
                available=lp.available_balance if lp else Decimal('0'),
                required=points,
            )

        # ── 4. Debit ─────────────────────────────────────────────────────────
        lp.debit(points)

        # ── 5. Compute reward value ──────────────────────────────────────────
        try:
            from ...models.points import PointsRate
            rate_obj = PointsRate.objects.filter(
                tenant=tenant or customer.tenant, is_active=True
            ).first()
            point_value = rate_obj.point_value if rate_obj else DEFAULT_POINT_VALUE
        except Exception:
            point_value = DEFAULT_POINT_VALUE

        reward_value = (points * point_value).quantize(Decimal('0.01'))

        # ── 6. Create request ────────────────────────────────────────────────
        req = RedemptionRequest.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer,
            points_used=points,
            redemption_type=redemption_type,
            reward_value=reward_value,
            status='pending',
        )

        # ── 7. Ledger ────────────────────────────────────────────────────────
        PointsLedger.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer,
            txn_type=LEDGER_DEBIT,
            source=LEDGER_SOURCE_REDEMPTION,
            points=points,
            balance_after=lp.balance,
            description=f'Redemption request #{req.id}',
            reference_id=str(req.id),
        )
        return req

    @staticmethod
    @transaction.atomic
    def approve(request_id: int, reviewed_by: str = None) -> RedemptionRequest:
        req = RedemptionRequest.objects.select_for_update().get(id=request_id)
        if req.status != 'pending':
            from ...exceptions import RedemptionAlreadyProcessedError
            raise RedemptionAlreadyProcessedError()
        old_status = req.status
        req.status = 'approved'
        req.reviewed_by = reviewed_by
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        RedemptionHistory.objects.create(
            request=req, from_status=old_status,
            to_status='approved', changed_by=reviewed_by,
        )
        return req

    @staticmethod
    @transaction.atomic
    def reject(request_id: int, reason: str = '', reviewed_by: str = None) -> RedemptionRequest:
        req = RedemptionRequest.objects.select_for_update().get(id=request_id)
        if req.status != 'pending':
            from ...exceptions import RedemptionAlreadyProcessedError
            raise RedemptionAlreadyProcessedError()
        old_status = req.status

        # ── Refund: lock wallet before crediting back ────────────────────────
        lp = (
            LoyaltyPoints.objects
            .select_for_update()
            .filter(customer=req.customer)
            .first()
        )
        if lp:
            lp.credit(req.points_used)
            lp.lifetime_redeemed -= req.points_used
            lp.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])

            # Ledger for refund
            PointsLedger.objects.create(
                tenant=req.tenant,
                customer=req.customer,
                txn_type=LEDGER_CREDIT,
                source=LEDGER_SOURCE_REDEMPTION,
                points=req.points_used,
                balance_after=lp.balance,
                description=f'Refund for rejected redemption #{req.id}',
                reference_id=f'refund-{req.id}',
            )

        req.status = 'rejected'
        req.reviewed_by = reviewed_by
        req.reviewed_at = timezone.now()
        req.note = reason
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'note'])
        RedemptionHistory.objects.create(
            request=req, from_status=old_status,
            to_status='rejected', changed_by=reviewed_by, note=reason,
        )
        return req

    @staticmethod
    def redeem_points(
        customer, points, redemption_type: str = 'cashback',
        rule=None, tenant=None,
    ) -> dict:
        """Alias for create_request() -- matches RewardCatalogViewSet call."""
        try:
            req = RedemptionService.create_request(
                customer=customer,
                points=Decimal(str(points)),
                redemption_type=redemption_type,
                tenant=tenant,
            )
            return {'success': True, 'redemption_request_id': req.id, 'status': req.status}
        except Exception as e:
            logger.error('RedemptionService.redeem_points error: %s', e)
            return {'success': False, 'error': str(e)}
