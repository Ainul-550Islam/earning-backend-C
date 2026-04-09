# api/djoyalty/viewsets/redemption/RedemptionViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.redemption import RedemptionRequest
from ...models.core import Customer
from ...serializers.RedemptionSerializer import RedemptionRequestSerializer
from ...services.redemption.RedemptionService import RedemptionService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin

class RedemptionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RedemptionRequest.objects.all().select_related('customer').order_by('-created_at')
    serializer_class = RedemptionRequestSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        req_status = self.request.query_params.get('status')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if req_status:
            qs = qs.filter(status=req_status)
        return qs

    @action(detail=False, methods=['post'])
    def redeem(self, request):
        customer_id = request.data.get('customer_id')
        points = request.data.get('points')
        redemption_type = request.data.get('redemption_type', 'cashback')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            req = RedemptionService.create_request(
                customer, Decimal(str(points)), redemption_type, tenant=customer.tenant,
            )
            return Response(RedemptionRequestSerializer(req).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def approve(self, request, pk=None):
        try:
            req = RedemptionService.approve(int(pk), reviewed_by=str(request.user))
            return Response(RedemptionRequestSerializer(req).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        try:
            req = RedemptionService.reject(int(pk), reason=reason, reviewed_by=str(request.user))
            return Response(RedemptionRequestSerializer(req).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
