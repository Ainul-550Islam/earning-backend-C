from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from api.smartlink.models import SmartLink, SmartLinkDailyStat
from api.smartlink.serializers.SmartLinkStatSerializer import SmartLinkStatSerializer
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from api.smartlink.filters import SmartLinkDailyStatFilter
from api.smartlink.pagination import StatsPagination
from api.smartlink.permissions import IsPublisher


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

    @action(detail=False, methods=['get'], url_path='daily')
    def daily(self, request, smartlink_pk=None):
        """
        GET /api/smartlink/smartlinks/{sl_pk}/stats/daily/

        Daily rollup stats for a SmartLink.
        Returns pre-aggregated per-day metrics from SmartLinkDailyStat.

        Query params:
          ?days=30    — number of days to return (default 30, max 90)
          ?order=asc  — order ascending (default desc)
        """
        from api.smartlink.models.analytics import SmartLinkDailyStat
        from api.smartlink.serializers.MissingTargetingSerializers import SmartLinkDailyStatSerializer

        days  = min(int(request.query_params.get('days', 30)), 90)
        order = request.query_params.get('order', 'desc')
        ordering = 'date' if order == 'asc' else '-date'

        qs = SmartLinkDailyStat.objects.filter(
            smartlink_id=smartlink_pk,
            smartlink__publisher=request.user,
        ).order_by(ordering)[:days]

        serializer = SmartLinkDailyStatSerializer(qs, many=True)
        return Response({
            'days_requested': days,
            'count':          qs.count(),
            'results':        serializer.data,
        })

