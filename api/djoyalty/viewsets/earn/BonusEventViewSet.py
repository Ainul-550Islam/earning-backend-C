# api/djoyalty/viewsets/earn/BonusEventViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.earn_rules import BonusEvent
from ...models.core import Customer
from ...serializers.EarnRuleSerializer import BonusEventSerializer
from ...services.earn.BonusEventService import BonusEventService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin

class BonusEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = BonusEvent.objects.all().select_related('customer').order_by('-created_at')
    serializer_class = BonusEventSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def award(self, request):
        customer_id = request.data.get('customer_id')
        points = request.data.get('points')
        reason = request.data.get('reason', 'Manual bonus')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            bonus = BonusEventService.award_bonus(
                customer, Decimal(str(points)), reason,
                triggered_by=str(request.user), tenant=customer.tenant,
            )
            return Response(BonusEventSerializer(bonus).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
