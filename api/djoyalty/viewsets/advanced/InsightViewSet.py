import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/advanced/InsightViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.advanced import LoyaltyInsight
from ...serializers.InsightSerializer import LoyaltyInsightSerializer
from ...services.advanced.InsightService import InsightService
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet

class InsightViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsLoyaltyAdmin]
    queryset = LoyaltyInsight.objects.all().order_by('-report_date')
    serializer_class = LoyaltyInsightSerializer
    pagination_class = DjoyaltyPagePagination

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Daily loyalty insight generate করো (admin)।"""
        try:
            tenant = getattr(request, 'tenant', None)
            insight = InsightService.generate_daily_insight(tenant=tenant)
            return Response(LoyaltyInsightSerializer(insight).data)
        except Exception as e:
            logger.error('InsightViewSet.generate error: %s', e)
            return Response({'error': str(e)}, status=500)
