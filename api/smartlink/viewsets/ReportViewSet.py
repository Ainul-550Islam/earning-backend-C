"""
SmartLink Report ViewSet
Advanced drill-down reporting for publishers.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..permissions import IsPublisher
from ..reports.PublisherReportService import PublisherReportService
from ..services.billing.PublisherPayoutService import PublisherPayoutService
from ..services.antifraud.ClickQualityScore import ClickQualityScore


class ReportViewSet(viewsets.GenericViewSet):
    """
    Publisher performance reporting endpoints.
    GET /api/smartlink/reports/performance/
    GET /api/smartlink/reports/quality/
    GET /api/smartlink/reports/payout/
    GET /api/smartlink/reports/top-performers/
    GET /api/smartlink/reports/hourly-heatmap/
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.report_svc  = PublisherReportService()
        self.payout_svc  = PublisherPayoutService()
        self.quality_svc = ClickQualityScore()

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        GET /api/smartlink/reports/performance/
        Params: date_from, date_to, group_by, smartlink, include_fraud
        """
        params = {
            'date_from':     request.query_params.get('date_from'),
            'date_to':       request.query_params.get('date_to'),
            'group_by':      request.query_params.get('group_by', 'date'),
            'smartlink':     request.query_params.get('smartlink'),
            'include_fraud': request.query_params.get('include_fraud', 'false') == 'true',
        }
        data = self.report_svc.performance_report(
            publisher_id=request.user.pk,
            params=params,
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='quality')
    def quality(self, request):
        """GET traffic quality report for publisher."""
        days = int(request.query_params.get('days', 30))
        data = self.report_svc.quality_report(request.user.pk, days=days)
        pub_quality = self.quality_svc.get_publisher_quality_report(
            request.user.pk, days=days
        )
        return Response({**data, **pub_quality})

    @action(detail=False, methods=['get'], url_path='payout')
    def payout(self, request):
        """GET publisher payout calculation for date range."""
        import datetime
        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')
        if not date_from or not date_to:
            today      = datetime.date.today()
            date_from  = today.replace(day=1)
            date_to    = today
        else:
            date_from = datetime.date.fromisoformat(date_from)
            date_to   = datetime.date.fromisoformat(date_to)

        data = self.payout_svc.calculate_period_payout(
            publisher_id=request.user.pk,
            date_from=date_from,
            date_to=date_to,
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='top-performers')
    def top_performers(self, request):
        """GET top SmartLinks by EPC, revenue, clicks."""
        days  = int(request.query_params.get('days', 7))
        limit = int(request.query_params.get('limit', 10))
        data  = self.report_svc.top_performers(
            publisher_id=request.user.pk,
            days=days,
            limit=limit,
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='hourly-heatmap')
    def hourly_heatmap(self, request):
        """GET 7×24 traffic heatmap (day of week × hour)."""
        days = int(request.query_params.get('days', 7))
        data = self.report_svc.hourly_heatmap(
            publisher_id=request.user.pk,
            days=days,
        )
        return Response({'days': days, 'heatmap': data})
