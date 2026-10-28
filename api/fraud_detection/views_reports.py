# fraud_detection/views_reports.py — Scheduled Report API Views
# DRY: all logic in report_scheduler.py
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)
def _ok(d, st=200):  return Response({"success": True, "data": d}, status=st)
def _err(m, st=400): return Response({"success": False, "error": str(m)}, status=st)


class ReportRequestAPIView(APIView):
    """POST /reports/request/ — request an on-demand report."""
    permission_classes = [IsAdminUser]
    def post(self, request):
        report_type = request.data.get("report_type")
        if not report_type:
            return _err("report_type is required")
        try:
            from api.fraud_detection.report_scheduler import get_report_scheduler
            job = get_report_scheduler().request_report(
                report_type = report_type,
                format      = request.data.get("format", "pdf"),
                period_days = int(request.data.get("period_days", 7)),
                recipients  = request.data.get("recipients", []),
                filters     = request.data.get("filters", {}),
            )
            return _ok({"report_id": job.report_id, "status": job.status.value}, 202)
        except Exception as exc:
            return _err(str(exc), 500)


class ReportStatusAPIView(APIView):
    """GET /reports/<report_id>/status/ — check report generation status."""
    permission_classes = [IsAuthenticated]
    def get(self, request, report_id: str):
        from api.fraud_detection.report_scheduler import get_report_scheduler
        status_data = get_report_scheduler().get_status(report_id)
        if not status_data:
            return _err("Report not found", 404)
        return _ok(status_data)


class ReportDownloadAPIView(APIView):
    """GET /reports/<report_id>/download/ — download report data."""
    permission_classes = [IsAuthenticated]
    def get(self, request, report_id: str):
        import json
        from django.core.cache import cache
        data = cache.get(f"report_data:{report_id}")
        if not data:
            return _err("Report data not found or expired", 404)
        return _ok(json.loads(data))


class ReportListAPIView(APIView):
    """GET /reports/ — list recent report jobs."""
    permission_classes = [IsAdminUser]
    def get(self, request):
        from api.fraud_detection.report_scheduler import get_report_scheduler
        limit = int(request.query_params.get("limit", 50))
        jobs  = get_report_scheduler().list_jobs(limit)
        return _ok({"reports": jobs, "total": len(jobs)})


class ReportScheduleRunAPIView(APIView):
    """POST /reports/schedule/run/ — manually trigger a scheduled report type."""
    permission_classes = [IsAdminUser]
    def post(self, request):
        schedule_type = request.data.get("schedule_type")
        if not schedule_type:
            return _err("schedule_type is required")
        try:
            from api.fraud_detection.report_scheduler import get_report_scheduler
            result = get_report_scheduler().run_scheduled(schedule_type)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)
