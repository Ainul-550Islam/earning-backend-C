# api/djoyalty/viewsets/engagement/LeaderboardViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...services.engagement.LeaderboardService import LeaderboardService

class LeaderboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def top(self, request):
        limit = int(request.query_params.get('limit', 10))
        period = request.query_params.get('period', 'all')
        tenant = getattr(request, 'tenant', None)
        data = list(LeaderboardService.get_top_customers(tenant=tenant, limit=limit, period=period))
        for i, item in enumerate(data):
            item['rank'] = i + 1
        return Response({'count': len(data), 'results': data})
