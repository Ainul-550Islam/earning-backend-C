# api/djoyalty/services/redemption/RedemptionService.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ...models.redemption import RedemptionRequest, RedemptionHistory
from ...models.points import LoyaltyPoints, PointsLedger
from ...choices import LEDGER_DEBIT, LEDGER_SOURCE_REDEMPTION
from ...exceptions import InsufficientPointsError, RedemptionMinimumNotMetError
from ...constants import MIN_REDEMPTION_POINTS

logger = logging.getLogger(__name__)

class RedemptionService:
    @staticmethod
    @transaction.atomic
    def create_request(customer, points: Decimal, redemption_type: str = 'cashback', tenant=None) -> RedemptionRequest:
        if points < MIN_REDEMPTION_POINTS:
            raise RedemptionMinimumNotMetError()
        lp = customer.loyalty_points.first()
        if not lp or lp.balance < points:
            raise InsufficientPointsError(available=lp.balance if lp else 0, required=points)
        lp.debit(points)
        from ...models.points import PointsRate
        from ...constants import DEFAULT_POINT_VALUE
        rate_obj = None
        try:
            rate_obj = PointsRate.objects.filter(tenant=tenant or customer.tenant, is_active=True).first()
        except Exception:
            pass
        point_value = rate_obj.point_value if rate_obj else DEFAULT_POINT_VALUE
        reward_value = (points * point_value).quantize(Decimal('0.01'))
        req = RedemptionRequest.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer, points_used=points,
            redemption_type=redemption_type, reward_value=reward_value,
            status='pending',
        )
        PointsLedger.objects.create(
            tenant=tenant or customer.tenant, customer=customer,
            txn_type=LEDGER_DEBIT, source=LEDGER_SOURCE_REDEMPTION,
            points=points, balance_after=lp.balance,
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
        RedemptionHistory.objects.create(request=req, from_status=old_status, to_status='approved', changed_by=reviewed_by)
        return req

    @staticmethod
    @transaction.atomic
    def reject(request_id: int, reason: str = '', reviewed_by: str = None) -> RedemptionRequest:
        req = RedemptionRequest.objects.select_for_update().get(id=request_id)
        if req.status != 'pending':
            from ...exceptions import RedemptionAlreadyProcessedError
            raise RedemptionAlreadyProcessedError()
        old_status = req.status
        lp = req.customer.loyalty_points.first()
        if lp:
            lp.credit(req.points_used)
            lp.lifetime_redeemed -= req.points_used
            lp.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])
        req.status = 'rejected'
        req.reviewed_by = reviewed_by
        req.reviewed_at = timezone.now()
        req.note = reason
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'note'])
        RedemptionHistory.objects.create(request=req, from_status=old_status, to_status='rejected', changed_by=reviewed_by, note=reason)
        return req
