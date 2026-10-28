# =============================================================================
# fraud_detection/views_interactors.py — NEW FILE
#
# Exposes interactors.py and repositories.py via DRF APIViews.
# WAS FLOATING: Both files had complete business logic with zero API access.
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTORS
# ─────────────────────────────────────────────────────────────────────────────

class FraudDetectionInteractorView(APIView):
    """POST /interactors/fraud-detection/execute/ — run full fraud detection interactor."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from api.fraud_detection.interactors import FraudDetectionInteractor
            result = FraudDetectionInteractor().execute(request.data, user=request.user)
            return Response({"success": True, "result": result})
        except Exception as exc:
            logger.error("FraudDetectionInteractor: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseInteractorView(APIView):
    """POST /interactors/fraud-case/execute/ — create or update case via interactor."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from api.fraud_detection.interactors import FraudCaseManagementInteractor
            result = FraudCaseManagementInteractor().execute(request.data, user=request.user)
            return Response({"success": True, "result": result})
        except Exception as exc:
            logger.error("FraudCaseInteractor: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RiskProfileInteractorView(APIView):
    """POST /interactors/risk-profile/update/ — update risk profile via interactor."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from api.fraud_detection.interactors import RiskProfileUpdateInteractor
            result = RiskProfileUpdateInteractor().execute(request.data, user=request.user)
            return Response({"success": True, "result": result})
        except Exception as exc:
            logger.error("RiskProfileInteractor: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# REPOSITORIES — admin-only diagnostic/stats views
# ─────────────────────────────────────────────────────────────────────────────

class RepositoryStatsView(APIView):
    """GET /repositories/stats/ — counts + cache stats per repository."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.repositories import (
                FraudRuleRepository, FraudCaseRepository,
                FraudAlertRepository, FraudRiskProfileRepository,
                DeviceFingerprintRepository, FraudSuspiciousIPRepository,
            )
            stats = {
                "fraud_rules":          FraudRuleRepository().count(),
                "fraud_cases":          FraudCaseRepository().count(),
                "fraud_alerts":         FraudAlertRepository().count(),
                "risk_profiles":        FraudRiskProfileRepository().count(),
                "device_fingerprints":  DeviceFingerprintRepository().count(),
                "suspicious_ips":       FraudSuspiciousIPRepository().count(),
            }
            return Response({"success": True, "repository_stats": stats})
        except Exception as exc:
            logger.error("RepositoryStatsView: %s", exc, exc_info=True)
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RepositoryQueryView(APIView):
    """POST /repositories/<repo>/query/ — run a named query on a repository."""
    permission_classes = [IsAdminUser]

    def post(self, request, repo_name: str):
        REPO_MAP = {
            "fraud-rules":    "FraudRuleRepository",
            "fraud-cases":    "FraudCaseRepository",
            "fraud-alerts":   "FraudAlertRepository",
            "risk-profiles":  "FraudRiskProfileRepository",
            "devices":        "DeviceFingerprintRepository",
            "suspicious-ips": "FraudSuspiciousIPRepository",
        }
        try:
            cls_name = REPO_MAP.get(repo_name)
            if not cls_name:
                return Response({"error": f"Unknown repo: {repo_name}"},
                                status=status.HTTP_404_NOT_FOUND)
            from api.fraud_detection import repositories as _repos
            repo   = getattr(_repos, cls_name)()
            method = request.data.get("method", "all")
            params = request.data.get("params", {})
            result = getattr(repo, method)(**params)
            # Serialize queryset to list of pks for safety
            if hasattr(result, "values_list"):
                result = list(result.values_list("pk", flat=True)[:100])
            return Response({"success": True, "result": result})
        except Exception as exc:
            logger.error("RepositoryQueryView %s: %s", repo_name, exc, exc_info=True)
            return Response({"success": False, "error": str(exc)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
