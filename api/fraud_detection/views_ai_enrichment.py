# =============================================================================
# fraud_detection/views_ai_enrichment.py — NEW FILE
#
# Exposes openai.py AI fraud analysis via API endpoints.
# WAS FLOATING: OpenAIFraudAnalyzer + AIEnrichmentService had no URL access.
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)


class AIFraudAnalysisView(APIView):
    """POST /ai/analyze-transaction/ — OpenAI-powered fraud analysis."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from api.fraud_detection.openai import analyze_transaction_with_ai
            result = analyze_transaction_with_ai(request.data)
            return Response({"success": True, "analysis": result.__dict__ if hasattr(result, '__dict__') else result})
        except Exception as exc:
            logger.error("AIFraudAnalysisView: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AIBulkEnrichmentView(APIView):
    """POST /ai/bulk-enrich/ — AI enrichment for batch of fraud records."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from api.fraud_detection.openai import enrich_fraud_data_with_ai
            data_list = request.data.get("records", [])
            results   = enrich_fraud_data_with_ai(data_list)
            return Response({"success": True, "enriched": len(results), "results": results})
        except Exception as exc:
            logger.error("AIBulkEnrichmentView: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
