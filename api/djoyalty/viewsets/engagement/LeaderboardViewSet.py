import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/engagement/LeaderboardViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...services.engagement.LeaderboardService import LeaderboardService
from ...serializers.LeaderboardSerializer import LeaderboardEntrySerializer
from ...mixins import DjoyaltyBaseViewSet

class LeaderboardViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def top(self, request):
        """Top customers by points earned -- tenant scoped।"""
        try:
            limit = int(request.query_params.get('limit', 10))
            period = request.query_params.get('period', 'all')
            season = request.query_params.get('season')
            tenant = getattr(request, 'tenant', None)
            if season:
                data = LeaderboardService.get_top(season=season, limit=limit, tenant=tenant)
            else:
                data = list(LeaderboardService.get_top_customers(tenant=tenant, limit=limit, period=period))
                for i, item in enumerate(data):
                    item['rank'] = i + 1
            return Response({'count': len(data), 'results': data})
        except Exception as e:
            logger.error('LeaderboardViewSet.top error: %s', e)
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def my_rank(self, request):
        """Authenticated customer এর current rank।"""
        try:
            from ...models.core import Customer
            customer_id = request.query_params.get('customer_id')
            season = request.query_params.get('season')
            if not customer_id:
                return self.err('customer_id required')
            customer = Customer.objects.get(pk=customer_id)
            tenant = getattr(request, 'tenant', None)
            rank = LeaderboardService.get_customer_rank(customer, season=season, tenant=tenant)
            score = LeaderboardService.get_customer_score(customer, season=season, tenant=tenant)
            return Response({'rank': rank, 'score': score, 'customer_id': customer_id})
        except Exception as e:
            logger.error('LeaderboardViewSet.my_rank error: %s', e)
            return Response({'error': str(e)}, status=500)
