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

class InsightViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsLoyaltyAdmin]
    queryset = LoyaltyInsight.objects.all().order_by('-report_date')
    serializer_class = LoyaltyInsightSerializer
    pagination_class = DjoyaltyPagePagination

    @action(detail=False, methods=['post'])
    def generate(self, request):
        tenant = getattr(request, 'tenant', None)
        insight = InsightService.generate_daily_insight(tenant=tenant)
        return Response(LoyaltyInsightSerializer(insight).data)
