# api/djoyalty/viewsets/points/PointsTransferViewSet.py
"""
PointsTransferViewSet — DRY refactored (v3)。

DRY FIX (v3):
  Before: 9 inline Response({'error': ...}) calls in transfer()
  After:  self.err() / self.created() / self.forbidden() via DjoyaltyBaseViewSet

  Before: admin check block repeated inline
  After:  is_admin = request.user.is_staff or request.user.is_superuser (one line)
"""
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation

from ...mixins import DjoyaltyBaseViewSet
from ...models.points import PointsTransfer
from ...models.core import Customer
from ...serializers.PointsSerializer import PointsTransferSerializer
from ...services.points.PointsTransferService import PointsTransferService
from ...pagination import DjoyaltyPagePagination
from ...throttles import DjoyaltyBurstThrottle

logger = logging.getLogger(__name__)


class PointsTransferViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset           = PointsTransfer.objects.all().select_related('from_customer', 'to_customer')
    serializer_class   = PointsTransferSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        qs     = super().get_queryset()
        user   = self.request.user
        is_adm = user.is_staff or user.is_superuser
        if not is_adm:
            from django.db.models import Q
            qs = qs.filter(
                Q(from_customer__user=user) | Q(to_customer__user=user)
            )
        else:
            cid = self.request.query_params.get('customer')
            if cid:
                from django.db.models import Q
                qs = qs.filter(Q(from_customer_id=cid) | Q(to_customer_id=cid))
        return qs.order_by('-created_at')

    @action(detail=False, methods=['post'],
            throttle_classes=[DjoyaltyBurstThrottle])
    def transfer(self, request):
        """
        P2P points transfer。
        Required: from_customer_id, to_customer_id, points, reference_id
        Optional: note
        """
        from_id      = request.data.get('from_customer_id')
        to_id        = request.data.get('to_customer_id')
        points_raw   = request.data.get('points')
        note         = request.data.get('note', '')
        reference_id = request.data.get('reference_id', '').strip()

        # ── Validate reference_id ─────────────────────────────────────────
        if not reference_id:
            return self.err('reference_id is required for transfer requests.')

        # ── Validate points ───────────────────────────────────────────────
        try:
            points = Decimal(str(points_raw))
            if points <= 0:
                raise ValueError('non-positive')
        except (InvalidOperation, ValueError, TypeError):
            return self.err('points must be a positive number.')

        # ── Resolve customers ─────────────────────────────────────────────
        from_customer = get_object_or_404(Customer, pk=from_id)
        to_customer   = get_object_or_404(Customer, pk=to_id)

        # ── Ownership guard ───────────────────────────────────────────────
        is_admin = request.user.is_staff or request.user.is_superuser
        if not is_admin and getattr(from_customer, 'user', None) != request.user:
            return self.forbidden('You can only transfer points from your own account.')

        # ── Idempotency check ─────────────────────────────────────────────
        cache_key = f'transfer:{from_customer.pk}:{to_customer.pk}:{reference_id}'
        try:
            from ...idempotency import IdempotencyGuard
            cached = IdempotencyGuard.get(cache_key)
            if cached is not None:
                logger.info('PointsTransferViewSet: idempotent hit ref=%s from=%s to=%s',
                            reference_id, from_customer.code, to_customer.code)
                try:
                    existing = PointsTransfer.objects.get(
                        reference=reference_id, from_customer=from_customer,
                    )
                    return self.ok(PointsTransferSerializer(existing).data)
                except PointsTransfer.DoesNotExist:
                    pass
        except ImportError:
            logger.warning('PointsTransferViewSet: IdempotencyGuard not available for ref=%s',
                           reference_id)
        except Exception as e:
            logger.warning('PointsTransferViewSet: IdempotencyGuard check failed: %s', e)

        # ── Execute transfer ──────────────────────────────────────────────
        try:
            transfer_obj = PointsTransferService.transfer(
                from_customer, to_customer, points,
                note=note, reference_id=reference_id,
            )
        except Exception as e:
            return self.err(str(e))

        # ── Cache result ──────────────────────────────────────────────────
        try:
            from ...idempotency import IdempotencyGuard
            IdempotencyGuard.set(cache_key, {'transfer_id': transfer_obj.pk})
        except Exception:
            pass

        return self.created(PointsTransferSerializer(transfer_obj).data)
