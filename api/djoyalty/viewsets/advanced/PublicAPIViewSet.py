# api/djoyalty/viewsets/advanced/PublicAPIViewSet.py
"""White-label public API for partner merchants।"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from decimal import Decimal
from django.shortcuts import get_object_or_404
from ...models.core import Customer
from ...services.points.PointsEngine import PointsEngine
from ...permissions import IsPublicAPIClient

class PublicAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsPublicAPIClient]

    @action(detail=False, methods=['get'])
    def balance(self, request):
        code = request.query_params.get('customer_code')
        customer = get_object_or_404(Customer, code=code.upper())
        lp = customer.loyalty_points.first()
        return Response({
            'customer_code': customer.code,
            'balance': str(lp.balance if lp else 0),
        })

    @action(detail=False, methods=['post'])
    def earn(self, request):
        code = request.data.get('customer_code')
        spend_amount = request.data.get('spend_amount', 0)
        customer = get_object_or_404(Customer, code=code.upper())
        try:
            points = PointsEngine.process_earn(customer, Decimal(str(spend_amount)))
            return Response({'points_earned': str(points)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
