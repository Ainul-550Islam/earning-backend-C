# api/djoyalty/viewsets/points/PointsViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.points import LoyaltyPoints
from ...models.core import Customer
from ...serializers.PointsSerializer import LoyaltyPointsSerializer
from ...services.points.PointsEngine import PointsEngine
from ...services.points.PointsAdjustmentService import PointsAdjustmentService
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination

class PointsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LoyaltyPoints.objects.all().select_related('customer')
    serializer_class = LoyaltyPointsSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def earn(self, request):
        customer_id = request.data.get('customer_id')
        spend_amount = request.data.get('spend_amount', 0)
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            points = PointsEngine.process_earn(customer, Decimal(str(spend_amount)), tenant=customer.tenant)
            return Response({'points_earned': str(points), 'message': f'Earned {points} points'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def adjust(self, request):
        customer_id = request.data.get('customer_id')
        points = request.data.get('points')
        reason = request.data.get('reason', '')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            lp = PointsAdjustmentService.adjust(
                customer, Decimal(str(points)), reason,
                adjusted_by=str(request.user), tenant=customer.tenant,
            )
            return Response({'balance': str(lp.balance), 'message': 'Adjustment successful'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        customer_id = request.query_params.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)
        lp = customer.loyalty_points.first()
        return Response({
            'customer': str(customer),
            'balance': str(lp.balance if lp else 0),
            'lifetime_earned': str(lp.lifetime_earned if lp else 0),
            'lifetime_redeemed': str(lp.lifetime_redeemed if lp else 0),
            'lifetime_expired': str(lp.lifetime_expired if lp else 0),
        })
