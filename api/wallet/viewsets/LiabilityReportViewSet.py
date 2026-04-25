# api/wallet/viewsets/LiabilityReportViewSet.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from ..models import LiabilityReport
from ..filters import LiabilityReportFilter
from ..pagination import WalletPagePagination


class LiabilityReportViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/wallet/liability-reports/ — daily financial liability snapshots."""
    permission_classes = [IsAdminUser]
    filterset_class    = LiabilityReportFilter
    pagination_class   = WalletPagePagination

    def get_serializer_class(self):
        from ..serializers.LiabilityReportSerializer import LiabilityReportSerializer
        return LiabilityReportSerializer

    def get_queryset(self):
        return LiabilityReport.objects.order_by("-report_date")

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """POST /api/wallet/liability-reports/generate/ — compute today's report."""
        from ..services import WalletAnalyticsService
        from datetime import date
        report = WalletAnalyticsService.compute_liability(date.today())
        return Response({"success": True, "report_date": str(report.report_date),
                         "total_liability": float(report.total_liability),
                         "total_wallets": report.total_wallets})
