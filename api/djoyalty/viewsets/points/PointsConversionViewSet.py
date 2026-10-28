# api/djoyalty/viewsets/points/PointsConversionViewSet.py
"""
PointsConversionViewSet — DRY refactored (v3)。

DRY FIX (v3):
  Before:
    return Response({'error': 'reference_id is required...'}, status=400)
    return Response({'error': 'points must be a positive number.'}, status=400)
    return Response({'error': 'customer_id required.'}, status=400)
    return Response({'error': 'Customer not found.'}, status=404)
    customer = getattr(request, 'loyalty_customer', None)
    if not customer: ...  [repeated block]

  After:
    return self.err(...)           — via DjoyaltyBaseViewSet
    return self.not_found(...)     — via DjoyaltyBaseViewSet
    customer, err = self.require_customer(request)
    if err: return err             — one line
"""
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal, InvalidOperation

from ...mixins import DjoyaltyBaseViewSet
from ...services.points.PointsConversionService import PointsConversionService

logger = logging.getLogger(__name__)


class PointsConversionViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def calculate(self, request):
        """Points ↔ currency conversion calculator (no auth needed for calculation)।"""
        points = request.query_params.get('points', 0)
        amount = request.query_params.get('amount', 0)
        if not points and not amount:
            return self.err('Provide points or amount.')
        try:
            if points:
                pts_dec = Decimal(str(points))
                if pts_dec <= 0:
                    raise ValueError('non-positive')
                value = PointsConversionService.points_to_currency(pts_dec)
                return self.ok({'points': str(pts_dec), 'currency_value': str(value)})
            amt_dec = Decimal(str(amount))
            if amt_dec <= 0:
                raise ValueError('non-positive')
            pts = PointsConversionService.currency_to_points(amt_dec)
            return self.ok({'amount': str(amt_dec), 'points': str(pts)})
        except (InvalidOperation, ValueError):
            return self.err('Invalid numeric value provided.')
        except Exception as e:
            logger.error('PointsConversionViewSet.calculate error: %s', e)
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """
        Customer এর points → currency convert করো (actual deduction)।

        Required: points (Decimal), reference_id (str)
        Optional: customer_id (for service-to-service calls)
        """
        # ── 1. Validate inputs ────────────────────────────────────────────
        reference_id = request.data.get('reference_id', '').strip()
        if not reference_id:
            return self.err('reference_id is required for conversion requests.')

        try:
            points = Decimal(str(request.data.get('points', 0)))
            if points <= 0:
                raise ValueError('non-positive')
        except (InvalidOperation, ValueError, TypeError):
            return self.err('points must be a positive number.')

        # ── 2. Resolve customer ───────────────────────────────────────────
        customer, err = self.require_customer(request)
        if err: return err

        # ── 3. Idempotency check ─────────────────────────────────────────
        cache_key = f'convert:{customer.pk}:{reference_id}'
        try:
            from ...idempotency import IdempotencyGuard
            cached = IdempotencyGuard.get(cache_key)
            if cached is not None:
                logger.info('PointsConversionViewSet: idempotent hit ref=%s customer=%s',
                            reference_id, customer.code)
                return self.ok(cached)
        except ImportError:
            logger.warning('PointsConversionViewSet: IdempotencyGuard not available for ref=%s',
                           reference_id)
        except Exception as e:
            logger.warning('PointsConversionViewSet: IdempotencyGuard check failed: %s', e)

        # ── 4. Execute conversion ─────────────────────────────────────────
        try:
            result = PointsConversionService.convert(
                customer, points,
                tenant=getattr(request, 'tenant', None),
                reference_id=reference_id,
            )
        except Exception as e:
            logger.error('PointsConversionViewSet.convert error: %s', e)
            return self.err(str(e), http_status=500)

        if not result.get('success'):
            return self.err(result.get('error', 'Conversion failed.'))

        # ── 5. Cache result ───────────────────────────────────────────────
        try:
            from ...idempotency import IdempotencyGuard
            IdempotencyGuard.set(cache_key, result)
        except Exception:
            pass

        return self.ok(result)
