# api/djoyalty/viewsets/redemption/GiftCardViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from ...models.redemption import GiftCard
from ...serializers.GiftCardSerializer import GiftCardSerializer
from ...services.redemption.GiftCardService import GiftCardService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin

class GiftCardViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = GiftCard.objects.all().select_related('issued_to').order_by('-created_at')
    serializer_class = GiftCardSerializer
    pagination_class = DjoyaltyPagePagination

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def issue(self, request):
        value = request.data.get('value')
        customer_id = request.data.get('customer_id')
        validity_days = request.data.get('validity_days', 365)
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id) if customer_id else None
        try:
            gc = GiftCardService.issue(
                Decimal(str(value)), issued_to=customer, validity_days=int(validity_days),
            )
            return Response(GiftCardSerializer(gc).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def redeem(self, request):
        code = request.data.get('code', '')
        amount = request.data.get('amount')
        try:
            gc = GiftCardService.redeem(code, Decimal(str(amount)))
            return Response({'message': f'Redeemed. Remaining: {gc.remaining_value}'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
