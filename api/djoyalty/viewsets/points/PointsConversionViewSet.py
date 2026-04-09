# api/djoyalty/viewsets/points/PointsConversionViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from ...services.points.PointsConversionService import PointsConversionService

class PointsConversionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def calculate(self, request):
        points = request.query_params.get('points', 0)
        amount = request.query_params.get('amount', 0)
        if points:
            value = PointsConversionService.points_to_currency(Decimal(str(points)))
            return Response({'points': points, 'currency_value': str(value)})
        if amount:
            pts = PointsConversionService.currency_to_points(Decimal(str(amount)))
            return Response({'amount': amount, 'points': str(pts)})
        return Response({'error': 'Provide points or amount'}, status=400)
