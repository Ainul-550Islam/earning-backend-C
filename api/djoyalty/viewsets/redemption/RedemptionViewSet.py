# api/djoyalty/viewsets/redemption/RedemptionViewSet.py
"""
RedemptionViewSet -- secure redemption.

Security fixes:
  1. /redeem: ownership check -- only your own customer account
  2. Throttle on redeem endpoint
  3. Numeric validation on points
  4. Query isolation: non-admins see only their own redemptions
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation

from ...models.redemption import RedemptionRequest
from ...models.core import Customer
from ...serializers.RedemptionSerializer import RedemptionRequestSerializer
from ...services.redemption.RedemptionService import RedemptionService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin
from ...throttles import DjoyaltyBurstThrottle, DjoyaltyUserThrottle
from ...mixins import DjoyaltyBaseViewSet


class RedemptionViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RedemptionRequest.objects.all().select_related('customer').order_by('-created_at')
    serializer_class = RedemptionRequestSerializer
    pagination_class = DjoyaltyPagePagination
    throttle_classes = [DjoyaltyUserThrottle]

    # Block direct create/update/delete -- use /redeem action only
    http_method_names = ['get', 'head', 'options', 'post']

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            # Users see only their own redemption requests
            qs = qs.filter(customer__user=self.request.user)
        else:
            customer_id = self.request.query_params.get('customer')
            req_status = self.request.query_params.get('status')
            if customer_id:
                qs = qs.filter(customer_id=customer_id)
            if req_status:
                qs = qs.filter(status=req_status)
        return qs

    # Disable direct ModelViewSet create (use /redeem instead)
    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use /redeem/ endpoint.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(
        detail=False,
        methods=['post'],
        throttle_classes=[DjoyaltyBurstThrottle],
    )
    def redeem(self, request):
        customer_id = request.data.get('customer_id')
        points_raw = request.data.get('points')
        redemption_type = request.data.get('redemption_type', 'cashback')

        # ── Validate points ──────────────────────────────────────────────────
        try:
            points = Decimal(str(points_raw))
            if points <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'error': 'points must be a positive number.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer = get_object_or_404(Customer, pk=customer_id)

        # ── Ownership check ──────────────────────────────────────────────────
        is_admin = request.user.is_staff or request.user.is_superuser
        owns_customer = getattr(customer, 'user', None) == request.user
        if not is_admin and not owns_customer:
            return Response(
                {'error': 'You can only redeem points from your own account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            req = RedemptionService.create_request(
                customer, points, redemption_type, tenant=customer.tenant,
            )
            return Response(
                RedemptionRequestSerializer(req).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def approve(self, request, pk=None):
        try:
            req = RedemptionService.approve(int(pk), reviewed_by=str(request.user))
            return Response(RedemptionRequestSerializer(req).data)
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        if not reason:
            return self.err('reason is required.')
        try:
            req = RedemptionService.reject(int(pk), reason=reason, reviewed_by=str(request.user))
            return Response(RedemptionRequestSerializer(req).data)
        except Exception as e:
            return self.err(str(e))
    @action(detail=False, methods=['get', 'post'], url_path='rules', permission_classes=[IsLoyaltyAdmin])
    def rules(self, request):
        """
        FIXED: RedemptionRule had NO API endpoint -- rules only editable in admin.
        GET: list all rules. POST: create new rule.
        """
        from ...models.redemption import RedemptionRule
        if request.method == 'GET':
            qs = RedemptionRule.objects.all().order_by('min_points')
            return Response({'results': [{
                'id': r.id, 'name': r.name if hasattr(r,'name') else '',
                'min_points': str(r.min_points), 'max_points': str(r.max_points) if r.max_points else None,
                'reward_type': r.reward_type, 'is_active': r.is_active,
            } for r in qs]})
        rule = RedemptionRule.objects.create(
            min_points=request.data.get('min_points', 0),
            max_points=request.data.get('max_points'),
            reward_type=request.data.get('reward_type', 'cash'),
            is_active=request.data.get('is_active', True),
        )
        return Response({'id': rule.id, 'reward_type': rule.reward_type},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='history', permission_classes=[IsLoyaltyAdmin])
    def history(self, request):
        """
        FIXED: RedemptionHistory had NO API endpoint.
        Full redemption history query with customer/date filters.
        """
        from ...models.redemption import RedemptionHistory
        qs = RedemptionHistory.objects.select_related('customer').order_by('-created_at')
        cid = request.query_params.get('customer_id')
        if cid: qs = qs.filter(customer_id=cid)
        qs = qs[:100]
        return Response({'count': qs.count(), 'results': [{
            'id': h.id, 'customer_code': h.customer.code if h.customer else '',
            'points_used': str(h.points_used), 'reward_type': h.reward_type,
            'status': h.status, 'created_at': str(h.created_at),
        } for h in qs]})

    @action(detail=False, methods=['get'], url_path='voucher-redemptions')
    def voucher_redemptions(self, request):
        """
        FIXED: VoucherRedemption had NO API endpoint.
        Customer or admin can query voucher redemption log.
        """
        from ...models.redemption import VoucherRedemption
        cid = request.query_params.get('customer_id')
        qs  = VoucherRedemption.objects.select_related('customer', 'voucher').order_by('-redeemed_at')
        if cid: qs = qs.filter(customer_id=cid)
        qs = qs[:50]
        return Response({'results': [{
            'id': r.id, 'customer_code': r.customer.code if r.customer else '',
            'voucher_code': r.voucher.code if r.voucher else '',
            'points_cost': str(getattr(r, 'points_cost', 0)),
            'redeemed_at': str(r.redeemed_at),
        } for r in qs]})
