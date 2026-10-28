# djoyalty/viewsets/advanced/PendingPointsViewSet.py
"""
Pending Points ViewSet -- exposes pending_points.py PendingPointsManager।
Pending points = held points that activate after delivery confirmation।
Previously: full hold/activate/cancel flow built, zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers as drf_serializers
from ...serializers.AnalyticsSerializer import (
    PendingPointsHoldInputSerializer, PendingBucketSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet


class PendingPointsViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /pending-points/my-total/        -- customer's pending balance
    GET  /pending-points/my-buckets/      -- customer's pending buckets
    POST /pending-points/admin/hold/      -- hold points for customer
    POST /pending-points/admin/activate/  -- activate a pending bucket
    POST /pending-points/admin/cancel/    -- cancel a pending bucket
    POST /pending-points/admin/activate-due/ -- batch activate all due
    """
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        c = getattr(request, 'loyalty_customer', None)
        if c:
            return c
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    @action(detail=False, methods=['get'], url_path='my-total')
    def my_total(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'pending_total': '0'})
        try:
            from ...pending_points import PendingPointsManager
            total = PendingPointsManager.get_pending_total(customer)
            return Response({'pending_total': str(total)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='my-buckets')
    def my_buckets(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response({'buckets': []})
        try:
            from ...pending_points import PendingPointsManager
            buckets = PendingPointsManager.get_customer_pending_buckets(customer)
            return Response({'buckets': buckets})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], url_path='admin/hold',
            permission_classes=[IsLoyaltyAdmin])
    def hold(self, request):
        customer_id = request.data.get('customer_id')
        points      = request.data.get('points')
        reason      = request.data.get('reason', '')
        activate_at = request.data.get('activate_at')
        if not customer_id or not points:
            return self.err('customer_id and points required')
        from ...models.core import Customer
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self.not_found('Customer not found')
        try:
            from ...pending_points import PendingPointsManager
            from decimal import Decimal
            bucket = PendingPointsManager.hold(
                customer=customer,
                points=Decimal(str(points)),
                reason=reason,
                activate_at=activate_at,
            )
            return Response({'status': 'held', 'bucket_id': bucket.id,
                             'points': str(bucket.points)}, status=201)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='admin/activate',
            permission_classes=[IsLoyaltyAdmin])
    def activate(self, request):
        bucket_id = request.data.get('bucket_id')
        if not bucket_id:
            return self.err('bucket_id required')
        try:
            from ...pending_points import PendingPointsBucket, PendingPointsManager
            from django.shortcuts import get_object_or_404
            bucket = get_object_or_404(PendingPointsBucket, pk=bucket_id)
            success = PendingPointsManager.activate(bucket)
            return Response({'status': 'activated' if success else 'failed'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='admin/cancel',
            permission_classes=[IsLoyaltyAdmin])
    def cancel(self, request):
        bucket_id = request.data.get('bucket_id')
        reason    = request.data.get('reason', '')
        if not bucket_id:
            return self.err('bucket_id required')
        try:
            from ...pending_points import PendingPointsBucket, PendingPointsManager
            from django.shortcuts import get_object_or_404
            bucket = get_object_or_404(PendingPointsBucket, pk=bucket_id)
            PendingPointsManager.cancel(bucket, reason=reason)
            return Response({'status': 'cancelled'})
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['post'], url_path='admin/activate-due',
            permission_classes=[IsLoyaltyAdmin])
    def activate_due(self, request):
        try:
            from ...pending_points import PendingPointsManager
            count = PendingPointsManager.activate_due()
            return Response({'status': 'ok', 'activated': count})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
