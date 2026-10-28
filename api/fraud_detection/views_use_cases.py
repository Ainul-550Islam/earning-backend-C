# =============================================================================
# fraud_detection/views_use_cases.py — NEW FILE
#
# Exposes use_cases.py via DRF APIViews.
# WAS FLOATING: use_cases.py defined 3 use cases + get_use_case() factory
# but had zero API routes.
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

logger = logging.getLogger(__name__)


class UseCaseRunAPIView(APIView):
    """POST /use-cases/<name>/run/ — execute a named use case."""
    permission_classes = [IsAuthenticated]

    def post(self, request, use_case_name: str):
        try:
            from api.fraud_detection.use_cases import get_use_case
            uc     = get_use_case(use_case_name)
            result = uc.execute(request.data, context={"user": request.user})
            return Response({"success": True, "result": result})
        except ValueError as exc:
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error("UseCaseRunAPIView %s: %s", use_case_name, exc, exc_info=True)
            return Response({"success": False, "error": "Internal error"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UseCaseListAPIView(APIView):
    """GET /use-cases/ — list available use cases."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_cases = [
            {"name": "multi_account_detection",       "description": "Detect multi-account fraud patterns"},
            {"name": "suspicious_pattern_detection",  "description": "Identify suspicious behaviour patterns"},
            {"name": "risk_assessment",               "description": "Comprehensive user risk assessment"},
        ]
        return Response({"use_cases": use_cases})
