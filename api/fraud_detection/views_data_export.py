# =============================================================================
# fraud_detection/views_data_export.py  — AUTO-GENERATED  (was missing entirely)
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

class DataExportCreateAPIView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request):
        from api.fraud_detection.data_export import DataExportService
        job = DataExportService().create_export(request.data)
        return Response({"success": True, "data": job}, status=status.HTTP_201_CREATED)

class DataExportDownloadAPIView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request, pk: int):
        from api.fraud_detection.data_export import DataExportService
        result = DataExportService().get_export_file(pk)
        return Response({"success": True, "data": result})

class DataExportListAPIView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        from api.fraud_detection.data_export import DataExportService
        exports = DataExportService().list_exports()
        return Response({"success": True, "data": exports})
