# api/publisher_tools/api_endpoints/reporting_api.py
"""Reporting API — Custom report builder and scheduled reports."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
import io


class CustomReportAPIView(APIView):
    """
    Custom report builder API।
    Dimensions ও metrics choose করে custom report তৈরি করে।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        start_date  = request.data.get("start_date")
        end_date    = request.data.get("end_date")
        dimensions  = request.data.get("dimensions", ["date"])
        metrics     = request.data.get("metrics", ["revenue", "impressions", "ecpm"])
        filters     = request.data.get("filters", {})
        export_fmt  = request.data.get("format", "json")
        limit       = int(request.data.get("limit", 1000))

        if not start_date or not end_date:
            return Response({"success": False, "message": "start_date and end_date required."}, status=400)

        from datetime import date
        from api.publisher_tools.performance_analytics.custom_report import build_custom_report, export_report_to_csv

        try:
            start = date.fromisoformat(start_date)
            end   = date.fromisoformat(end_date)
        except ValueError:
            return Response({"success": False, "message": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        report = build_custom_report(publisher, start, end, dimensions, metrics, filters, limit)
        if "error" in report:
            return Response({"success": False, "message": report["error"]}, status=400)

        if export_fmt == "csv":
            csv_content = export_report_to_csv(report)
            return Response({"success": True, "data": {"csv": csv_content, "row_count": report["row_count"]}})

        return Response({"success": True, "data": report})


class ScheduledReportAPIView(APIView):
    """Scheduled report management — create, list, delete scheduled reports。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List publisher-এর scheduled reports।"""
        from api.publisher_tools.database_models.report_model import ReportRecord
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        reports = ReportRecord.objects.filter(publisher=publisher, is_processed=False).order_by("-created_at")[:20]
        return Response({"success": True, "data": [
            {"id": str(r.id), "date": str(r.record_date), "source": r.source, "processed": r.is_processed}
            for r in reports
        ]})

    def post(self, request):
        """Schedule a new report।"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        report_type = request.data.get("report_type", "daily")
        schedule    = request.data.get("schedule", "daily")
        email       = request.data.get("email_to", publisher.contact_email)
        from django.utils import timezone
        from api.publisher_tools.database_models.report_model import ReportRecord
        record = ReportRecord.objects.create(
            publisher=publisher,
            record_date=timezone.now().date(),
            data={"report_type": report_type, "schedule": schedule, "email_to": email},
            source="api",
        )
        return Response({"success": True, "data": {"id": str(record.id), "scheduled": True}}, status=201)


class ReportExportAPIView(APIView):
    """Export reports to CSV/Excel。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        report_data = request.data.get("report_data", {})
        export_format = request.data.get("format", "csv")
        if not report_data:
            return Response({"success": False, "message": "report_data required."}, status=400)
        if export_format == "csv":
            from api.publisher_tools.performance_analytics.custom_report import export_report_to_csv
            csv_content = export_report_to_csv(report_data)
            return Response({"success": True, "data": {"csv": csv_content, "format": "csv"}})
        return Response({"success": False, "message": f"Format '{export_format}' not supported."}, status=400)
