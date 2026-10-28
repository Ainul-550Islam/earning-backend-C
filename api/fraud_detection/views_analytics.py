# =============================================================================
# fraud_detection/views_analytics.py  — AUTO-GENERATED  (was missing entirely)
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

class FraudAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        return Response({"success": True, "data": FraudAnalyticsEngine().get_real_time_stats()})

class GeographicAnalysisAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        return Response({"success": True, "data": FraudAnalyticsEngine().get_geographic_breakdown()})

class RiskTimelineAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        period = request.query_params.get("period", "24h")
        return Response({"success": True, "data": FraudAnalyticsEngine().get_risk_timeline(period)})

class AnalyticsDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        return Response({"success": True, "data": FraudAnalyticsEngine().get_dashboard_data()})

class ExportAnalyticsAPIView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        export_format = request.data.get("format", "csv")
        result = FraudAnalyticsEngine().export(export_format, request.data)
        return Response({"success": True, "data": result})
