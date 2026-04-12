from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from ..models import SmartLink, SmartLinkDailyStat
from ..serializers.SmartLinkStatSerializer import SmartLinkStatSerializer
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from ..filters import SmartLinkDailyStatFilter
from ..pagination import StatsPagination
from ..permissions import IsPublisher


class SmartLinkStatViewSet(viewsets.ReadOnlyModelViewSet):
    """Analytics stats for a SmartLink."""
    serializer_class = SmartLinkStatSerializer
    permission_classes = [IsAuthenticated, IsPublisher]
    pagination_class = StatsPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = SmartLinkDailyStatFilter

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.analytics_service = SmartLinkAnalyticsService()

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return SmartLinkDailyStat.objects.filter(smartlink_id=sl_pk).order_by('-date')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request, smartlink_pk=None):
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response(self.analytics_service.get_summary(sl, days=days))

    @action(detail=False, methods=['get'], url_path='geo')
    def geo(self, request, smartlink_pk=None):
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response(self.analytics_service.get_geo_breakdown(sl, days=days))

    @action(detail=False, methods=['get'], url_path='device')
    def device(self, request, smartlink_pk=None):
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response(self.analytics_service.get_device_breakdown(sl, days=days))
