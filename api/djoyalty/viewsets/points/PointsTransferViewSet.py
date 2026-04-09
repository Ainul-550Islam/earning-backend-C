# api/djoyalty/viewsets/points/PointsTransferViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.points import PointsTransfer
from ...models.core import Customer
from ...serializers.PointsSerializer import PointsTransferSerializer
from ...services.points.PointsTransferService import PointsTransferService
from ...pagination import DjoyaltyPagePagination

class PointsTransferViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PointsTransfer.objects.all().select_related('from_customer', 'to_customer')
    serializer_class = PointsTransferSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            from django.db.models import Q
            qs = qs.filter(Q(from_customer_id=customer_id) | Q(to_customer_id=customer_id))
        return qs.order_by('-created_at')

    @action(detail=False, methods=['post'])
    def transfer(self, request):
        from_id = request.data.get('from_customer_id')
        to_id = request.data.get('to_customer_id')
        points = request.data.get('points')
        note = request.data.get('note', '')
        from_customer = get_object_or_404(Customer, pk=from_id)
        to_customer = get_object_or_404(Customer, pk=to_id)
        try:
            transfer = PointsTransferService.transfer(
                from_customer, to_customer, Decimal(str(points)), note=note,
            )
            return Response(PointsTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
