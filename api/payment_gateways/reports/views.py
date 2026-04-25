# api/payment_gateways/reports/views.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from core.views import BaseViewSet
from .models import ReconciliationReport
from .serializers import (
    ReconciliationReportSerializer, DailyReportRequestSerializer,
    MonthlyReportRequestSerializer, GatewayReportRequestSerializer,
    ExportRequestSerializer,
)


class ReportViewSet(BaseViewSet):
    """Admin reporting endpoints."""
    queryset           = ReconciliationReport.objects.all().order_by('-report_date')
    serializer_class   = ReconciliationReportSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['report_date']

    @action(detail=False, methods=['get', 'post'])
    def daily(self, request):
        """Generate/retrieve daily report."""
        s = DailyReportRequestSerializer(data=request.data or request.query_params)
        s.is_valid(raise_exception=True)
        target = s.validated_data.get('date', (timezone.now() - timedelta(days=1)).date())
        from .DailyReport import DailyReport
        report = DailyReport(target)
        return self.success_response(data=report.generate())

    @action(detail=False, methods=['get', 'post'])
    def monthly(self, request):
        """Generate monthly report."""
        s = MonthlyReportRequestSerializer(data=request.data or request.query_params)
        s.is_valid(raise_exception=True)
        now   = timezone.now()
        year  = s.validated_data.get('year',  now.year)
        month = s.validated_data.get('month', now.month)
        from .MonthlyReport import MonthlyReport
        report = MonthlyReport(year, month)
        return self.success_response(data=report.generate())

    @action(detail=False, methods=['get', 'post'])
    def gateway(self, request):
        """Per-gateway breakdown report."""
        s = GatewayReportRequestSerializer(data=request.data or request.query_params)
        s.is_valid(raise_exception=True)
        from .GatewayReport import GatewayReport
        report = GatewayReport(s.validated_data['gateway'], s.validated_data.get('days', 30))
        return self.success_response(data=report.generate())

    @action(detail=False, methods=['get', 'post'], permission_classes=[IsAuthenticated])
    def my_report(self, request):
        """User's personal transaction summary."""
        from .UserReport import UserReport
        report = UserReport()
        return self.success_response(data=report.generate(request.user.id))

    @action(detail=False, methods=['post'])
    def export_csv(self, request):
        """Export transactions as CSV file."""
        s = ExportRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        from .ExportService import ExportService
        exporter  = ExportService()
        file_path = exporter.export_all_transactions_csv(
            s.validated_data.get('date_from'),
            s.validated_data.get('date_to'),
        )
        return self.success_response(data={'file_path': file_path}, message='CSV export ready')

    @action(detail=False, methods=['post'])
    def export_my_csv(self, request):
        """Export current user's transactions as CSV."""
        s = ExportRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        from .ExportService import ExportService
        exporter  = ExportService()
        file_path = exporter.export_user_transactions_csv(
            request.user.id,
            filters={
                'gateway':   s.validated_data.get('gateway'),
                'status':    s.validated_data.get('status'),
                'date_from': s.validated_data.get('date_from'),
                'date_to':   s.validated_data.get('date_to'),
            }
        )
        return self.success_response(data={'file_path': file_path}, message='Your CSV export is ready')

    @action(detail=False, methods=['get'])
    def reconciliation_history(self, request):
        """List past reconciliation reports."""
        qs = self.get_queryset()[:30]  # Last 30
        return self.success_response(data=ReconciliationReportSerializer(qs, many=True).data)
