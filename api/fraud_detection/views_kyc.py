# =============================================================================
# fraud_detection/views_kyc.py  — KYC API VIEWS
# DRY: All business logic in kyc_service.py; views are thin HTTP adapters.
# =============================================================================
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

def _ok(data, st=200):  return Response({"success": True, "data": data}, status=st)
def _err(msg, st=400):  return Response({"success": False, "error": str(msg)}, status=st)


class KYCSubmitAPIView(APIView):
    """POST /kyc/submit/ — submit identity document for verification."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        doc_type = request.data.get("document_type")
        doc_data = request.data.get("document_data", {})
        if not doc_type:
            return _err("document_type is required")
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            result = get_kyc_service().submit_document(
                user_id       = request.user.pk,
                document_type = doc_type,
                document_data = doc_data,
                metadata      = {"ip": request.META.get("REMOTE_ADDR"),
                                 "user_agent": request.META.get("HTTP_USER_AGENT", "")},
            )
            return _ok({
                "submission_id":  result.submission_id,
                "status":         result.status.value,
                "document_type":  result.document_type,
                "risk_score_delta": result.risk_score_delta,
            }, 201)
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            logger.error("KYCSubmitAPIView: %s", exc, exc_info=True)
            return _err("Submission failed — please retry", 500)


class KYCStatusAPIView(APIView):
    """GET /kyc/status/ — get current user's KYC status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            return _ok(get_kyc_service().get_status(request.user.pk))
        except Exception as exc:
            return _err(str(exc), 500)


class KYCUserStatusAPIView(APIView):
    """GET /kyc/users/<user_id>/status/ — admin: get KYC status for any user."""
    permission_classes = [IsAdminUser]

    def get(self, request, user_id: int):
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            return _ok(get_kyc_service().get_status(user_id))
        except Exception as exc:
            return _err(str(exc), 500)


class KYCBulkStatusAPIView(APIView):
    """POST /kyc/bulk-status/ — admin: get KYC status for a list of users."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_ids = request.data.get("user_ids", [])
        if not user_ids:
            return _err("user_ids required")
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            return _ok(get_kyc_service().get_all_statuses(user_ids))
        except Exception as exc:
            return _err(str(exc), 500)


class KYCDecisionAPIView(APIView):
    """POST /kyc/submissions/<id>/decide/ — analyst manual approve/reject."""
    permission_classes = [IsAdminUser]

    def post(self, request, submission_id: str):
        decision = request.data.get("decision")
        reason   = request.data.get("reason")
        if not decision:
            return _err("decision is required (approved | rejected)")
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            result = get_kyc_service().manual_decision(
                submission_id = submission_id,
                decision      = decision,
                reason        = reason,
                reviewer_id   = request.user.pk,
            )
            return _ok(result)
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            logger.error("KYCDecisionAPIView: %s", exc, exc_info=True)
            return _err(str(exc), 500)


class KYCUnverifiedHighRiskAPIView(APIView):
    """GET /kyc/unverified-high-risk/ — users not KYC-verified with high risk score."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        threshold = int(request.query_params.get("threshold", 60))
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            users = get_kyc_service().get_unverified_high_risk_users(threshold)
            return _ok({"users": users, "total": len(users), "threshold": threshold})
        except Exception as exc:
            return _err(str(exc), 500)


class KYCVerifyCheckAPIView(APIView):
    """GET /kyc/verify/<user_id>/ — boolean: is user KYC-verified?"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: int):
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            is_verified = get_kyc_service().is_user_kyc_verified(user_id)
            return _ok({"user_id": user_id, "is_verified": is_verified})
        except Exception as exc:
            return _err(str(exc), 500)
