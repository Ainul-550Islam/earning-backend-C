from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import SmartLink
from ..serializers.InsightSerializer import InsightSerializer
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from ..services.analytics.EPCCalculatorService import EPCCalculatorService
from ..services.analytics.ConversionRateService import ConversionRateService
from ..services.analytics.RevenueAttributionService import RevenueAttributionService
from ..permissions import IsPublisher


class InsightViewSet(viewsets.GenericViewSet):
    """
    Publisher insights and performance recommendations.
    Read-only computed analytics — not a standard CRUD viewset.
    """
    serializer_class = InsightSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.analytics = SmartLinkAnalyticsService()
        self.epc_calc = EPCCalculatorService()
        self.cr_calc = ConversionRateService()
        self.revenue_svc = RevenueAttributionService()

    def get_queryset(self):
        return SmartLink.objects.filter(
            id=self.kwargs.get('smartlink_pk')
        )

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request, smartlink_pk=None):
        """Full performance overview: clicks, conversions, EPC, CR, revenue."""
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response({
            'summary': self.analytics.get_summary(sl, days=days),
            'daily': self.analytics.get_daily_breakdown(sl, days=days),
            'geo': self.analytics.get_geo_breakdown(sl, days=days),
            'device': self.analytics.get_device_breakdown(sl, days=days),
        })

    @action(detail=False, methods=['get'], url_path='epc')
    def epc(self, request, smartlink_pk=None):
        """EPC breakdown by geo and device."""
        days = int(request.query_params.get('days', 7))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response({
            'overall_epc': self.epc_calc.calculate_for_smartlink(sl, days=days),
            'by_country': self.epc_calc.calculate_geo_epc(sl, days=days),
        })

    @action(detail=False, methods=['get'], url_path='conversion-rate')
    def conversion_rate(self, request, smartlink_pk=None):
        """Conversion rate breakdown."""
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response({
            'overall_cr': self.cr_calc.calculate_for_smartlink(sl, days=days),
            'by_country': self.cr_calc.calculate_by_country(sl, days=days),
            'by_device': self.cr_calc.calculate_by_device(sl, days=days),
        })

    @action(detail=False, methods=['get'], url_path='revenue')
    def revenue(self, request, smartlink_pk=None):
        """Revenue attribution breakdown."""
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        return Response({
            'totals': self.revenue_svc.get_smartlink_revenue(sl, days=days),
            'by_offer': self.revenue_svc.get_revenue_by_offer(sl, days=days),
            'by_country': self.revenue_svc.get_revenue_by_country(sl, days=days),
        })
