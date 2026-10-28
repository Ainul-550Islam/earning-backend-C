# =============================================================================
# fraud_detection/views_monitoring.py  — AUTO-GENERATED  (was missing entirely)
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

class SystemHealthAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.monitoring import get_real_time_monitor
        return Response({"success": True, "data": get_real_time_monitor().get_system_health()})

class IntegrityVerificationAPIView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request, case_id=None):
        from api.fraud_detection.monitoring import get_real_time_monitor
        result = get_real_time_monitor().verify_integrity(str(case_id) if case_id else None)
        return Response({"success": True, "data": result})
    def post(self, request):
        return self.get(request)

class MonitoringMetricsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.monitoring import get_real_time_monitor
        return Response({"success": True, "data": get_real_time_monitor().get_metrics()})

class PerformanceSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.monitoring import get_real_time_monitor
        return Response({"success": True, "data": get_real_time_monitor().get_performance_summary()})
