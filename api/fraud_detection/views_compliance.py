# =============================================================================
# fraud_detection/views_compliance.py  — AUTO-GENERATED  (was missing entirely)
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

class ComplianceReportAPIView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request):
        from api.fraud_detection.compliance import ComplianceReportGenerator
        result = ComplianceReportGenerator().generate(
            report_type=request.data.get("report_type", "monthly"),
            period_days=int(request.data.get("period_days", 30)))
        return Response({"success": True, "data": result})

class ComplianceStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.compliance import ComplianceReportGenerator
        return Response({"success": True, "data": ComplianceReportGenerator().get_status()})

class SanctionsCheckAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        from api.fraud_detection.sanctions import SanctionsChecker
        result = SanctionsChecker().screen(request.data)
        return Response({"success": True, "data": result})

class SanctionsScreeningAPIView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request):
        from api.fraud_detection.sanctions import SanctionsChecker
        result = SanctionsChecker().screen_terrorist_financing(request.data)
        return Response({"success": True, "data": result})
