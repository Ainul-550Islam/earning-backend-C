# api/djoyalty/viewsets/points/PointsViewSet.py
"""
PointsViewSet -- secure earn, balance, adjust, reserve, release endpoints।
FIXED: PointsReservationService (services/points/PointsReservationService.py)
was fully built but no viewset called reserve() or release()।
Added /reserve/ and /release/ actions -- needed for checkout pre-hold flows
(hold points during payment, release if cancelled, confirm on success)。
"""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models.core import Customer
from ...models.points import LoyaltyPoints
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin
from ...serializers.PointsSerializer import LoyaltyPointsSerializer
from ...services.points.PointsAdjustmentService import PointsAdjustmentService
from ...services.points.PointsEngine import PointsEngine
from ...throttles import DjoyaltyBurstThrottle, DjoyaltyUserThrottle
from ...mixins import DjoyaltyBaseViewSet


class PointsViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset           = LoyaltyPoints.objects.all().select_related('customer')
    serializer_class   = LoyaltyPointsSerializer
    pagination_class   = DjoyaltyPagePagination
    throttle_classes   = [DjoyaltyUserThrottle, DjoyaltyBurstThrottle]

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            qs = qs.filter(customer__user=self.request.user)
        else:
            cid = self.request.query_params.get('customer')
            if cid:
                qs = qs.filter(customer_id=cid)
        return qs

    # ── Earn ──────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'],
            permission_classes=[IsLoyaltyAdmin],
            throttle_classes=[DjoyaltyBurstThrottle])
    def earn(self, request):
        """Trigger points earn -- admin/internal only। IdempotencyGuard prevents double-award。"""
        customer_id  = request.data.get('customer_id')
        spend_amount = request.data.get('spend_amount', 0)
        reference_id = request.data.get('reference_id')

        if not customer_id:
            return self.err('customer_id required')
        if not reference_id:
            return self.err('reference_id required for idempotent earn')

        # Idempotency guard
        guard = None
        try:
            from ...idempotency import IdempotencyGuard
            guard = IdempotencyGuard('earn_points', customer_id=str(customer_id),
                                     reference_id=str(reference_id))
            if guard.already_processed():
                return Response({**guard.get_cached_result(), 'idempotent': True,
                                 'message': 'Duplicate -- returning cached result'})
        except Exception:
            pass

        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            points = PointsEngine.process_earn(
                customer, Decimal(str(spend_amount)),
                tenant=customer.tenant, reference_id=reference_id,
            )
            result = {'points_earned': str(points), 'message': f'Earned {points} points'}
            if guard:
                try: guard.mark_processed(result)
                except Exception: pass
            return Response(result)
        except Exception as e:
            return self.err(str(e))

    # ── Adjust ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def adjust(self, request):
        """Manual admin adjustment -- requires reason for audit trail。"""
        customer_id = request.data.get('customer_id')
        points      = request.data.get('points')
        reason      = request.data.get('reason', '')
        if not reason:
            return self.err('reason required for adjustment')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            lp = PointsAdjustmentService.adjust(
                customer, Decimal(str(points)), reason,
                adjusted_by=str(request.user), tenant=customer.tenant,
            )
            return Response({'balance': str(lp.balance), 'message': 'Adjustment successful'})
        except Exception as e:
            return self.err(str(e))

    # ── Balance ───────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Customer points balance -- ownership enforced。"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        customer = get_object_or_404(Customer, pk=customer_id)
        is_admin      = request.user.is_staff or request.user.is_superuser
        owns_customer = getattr(customer, 'user', None) == request.user
        if not is_admin and not owns_customer:
            return Response({'error': 'Forbidden'}, status=403)
        lp = customer.loyalty_points.first()
        return Response({
            'customer':           str(customer),
            'balance':            str(lp.balance           if lp else 0),
            'available_balance':  str(lp.available_balance if lp else 0),
            'frozen_balance':     str(lp.frozen_balance    if lp else 0),
            'lifetime_earned':    str(lp.lifetime_earned   if lp else 0),
            'lifetime_redeemed':  str(lp.lifetime_redeemed if lp else 0),
            'lifetime_expired':   str(lp.lifetime_expired  if lp else 0),
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Full points summary with tier + upcoming expiry。"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        customer = get_object_or_404(Customer, pk=customer_id)
        is_admin      = request.user.is_staff or request.user.is_superuser
        owns_customer = getattr(customer, 'user', None) == request.user
        if not is_admin and not owns_customer:
            return Response({'error': 'Forbidden'}, status=403)
        lp = customer.loyalty_points.first()
        tier_name, tier_rank = '', 0
        try:
            ut = customer.user_tiers.filter(is_current=True).first()
            if ut:
                tier_name = ut.tier.name
                tier_rank = ut.tier.rank
        except Exception:
            pass
        expiring_soon = None
        try:
            from django.utils import timezone
            from datetime import timedelta
            from ...models.points import PointsExpiry
            exp = PointsExpiry.objects.filter(
                customer=customer, is_expired=False,
                expiry_date__lte=timezone.now() + timedelta(days=30),
                points_remaining__gt=0,
            ).order_by('expiry_date').first()
            if exp:
                expiring_soon = {'points': str(exp.points_remaining),
                                 'expiry_date': str(exp.expiry_date.date())}
        except Exception:
            pass
        return Response({
            'customer':           str(customer),
            'balance':            str(lp.balance           if lp else 0),
            'available_balance':  str(lp.available_balance if lp else 0),
            'frozen_balance':     str(lp.frozen_balance    if lp else 0),
            'lifetime_earned':    str(lp.lifetime_earned   if lp else 0),
            'lifetime_redeemed':  str(lp.lifetime_redeemed if lp else 0),
            'lifetime_expired':   str(lp.lifetime_expired  if lp else 0),
            'tier':               tier_name,
            'tier_rank':          tier_rank,
            'expiring_soon':      expiring_soon,
        })

    # ── Reserve (NEW) ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def reserve(self, request):
        """
        Pre-hold points for pending payment / checkout।
        FIXED: PointsReservationService.reserve() was defined but
        no API called it -- checkout pre-hold flows were impossible।

        Use case:
          1. Customer starts checkout -> POST /points/reserve/ (hold 500 pts)
          2a. Payment succeeds -> POST /redemptions/request/ (use reserved pts)
          2b. Payment fails   -> POST /points/release/ (release back to balance)

        Body: { "customer_id": 1, "points": 500, "reference": "order-789",
                "hold_minutes": 30 }
        """
        from ...services.points.PointsReservationService import PointsReservationService
        from ...exceptions import InsufficientPointsError

        customer_id  = request.data.get('customer_id')
        points       = request.data.get('points')
        reference    = request.data.get('reference', '')
        hold_minutes = int(request.data.get('hold_minutes', 30))

        if not customer_id or not points or not reference:
            return Response(
                {'error': 'customer_id, points and reference required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            reservation = PointsReservationService.reserve(
                customer=customer,
                points=Decimal(str(points)),
                reference=reference,
                hold_minutes=hold_minutes,
                tenant=customer.tenant,
            )
            return Response({
                'status':      'reserved',
                'reservation_id': reservation.id,
                'points':      str(reservation.points),
                'reference':   reference,
                'expires_at':  str(reservation.expires_at),
            }, status=status.HTTP_201_CREATED)
        except InsufficientPointsError as e:
            return self.err(str(e))
        except Exception as e:
            return self.err(str(e), http_status=500)

    # ── Release (NEW) ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def release(self, request):
        """
        Release a points reservation back to customer balance।
        FIXED: PointsReservationService.release() was defined but
        no API called it。
        Body: { "reference": "order-789" }
        """
        from ...services.points.PointsReservationService import PointsReservationService

        reference = request.data.get('reference', '')
        if not reference:
            return self.err('reference required')
        try:
            released = PointsReservationService.release(reference=reference)
            if released:
                return Response({'status': 'released', 'reference': reference})
            return Response(
                {'error': 'No active reservation found for this reference'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.err(str(e), http_status=500)

    # ── Active reservations ────────────────────────────────────────────────────
    @action(detail=False, methods=['get'],
            url_path='reservations', permission_classes=[IsLoyaltyAdmin])
    def reservations(self, request):
        """List active points reservations -- for debugging checkout holds。"""
        from ...models.points import PointsReservation
        from django.utils import timezone

        customer_id = request.query_params.get('customer_id')
        qs = PointsReservation.objects.filter(
            is_released=False, expires_at__gt=timezone.now()
        ).select_related('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        qs = qs.order_by('-created_at')[:50]
        return Response({'reservations': [
            {
                'id':         r.id,
                'customer':   r.customer.code,
                'points':     str(r.points),
                'reference':  r.reference,
                'expires_at': str(r.expires_at),
            } for r in qs
        ]})
    @action(detail=False, methods=['get'], permission_classes=[IsLoyaltyAdmin], url_path='rates-config')
    def rates_config(self, request):
        """
        FIXED: PointsRate had NO API endpoint.
        Points earn rate configuration -- how many points per currency unit.
        """
        from ...models.points import PointsRate
        qs = PointsRate.objects.filter(is_active=True).order_by('effective_from')
        return Response({'rates': [{
            'id': r.id, 'points_per_unit': str(r.points_per_unit),
            'currency': r.currency, 'channel': r.channel,
            'effective_from': str(r.effective_from),
            'effective_until': str(r.effective_until) if r.effective_until else None,
        } for r in qs]})
