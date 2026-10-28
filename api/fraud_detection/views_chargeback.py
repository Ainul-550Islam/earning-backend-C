# fraud_detection/views_chargeback.py — Chargeback API Views
# DRY: All logic in services/ChargebackService.py
from __future__ import annotations
import logging
from decimal import Decimal, InvalidOperation
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

def _ok(d, st=200):  return Response({"success": True, "data": d}, status=st)
def _err(m, st=400): return Response({"success": False, "error": str(m)}, status=st)


class ChargebackOpenAPIView(APIView):
    """POST /chargebacks/open/ — file a new chargeback dispute."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            amount = Decimal(str(request.data.get("amount", 0)))
        except InvalidOperation:
            return _err("Invalid amount")
        tx_id  = request.data.get("transaction_id", "")
        reason = request.data.get("reason", "other")
        if not tx_id:
            return _err("transaction_id is required")
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            result = get_chargeback_service().open_dispute(
                user_id=request.user.pk, transaction_id=tx_id,
                amount=amount, reason=reason,
                metadata=request.data.get("metadata", {}),
            )
            return _ok(result, 201)
        except Exception as exc:
            logger.error("ChargebackOpenAPIView: %s", exc)
            return _err(str(exc), 500)


class ChargebackUpdateAPIView(APIView):
    """PATCH /chargebacks/<dispute_id>/status/ — update dispute status."""
    permission_classes = [IsAdminUser]

    def patch(self, request, dispute_id: str):
        new_status = request.data.get("status")
        if not new_status:
            return _err("status is required")
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            result = get_chargeback_service().update_status(
                dispute_id, new_status, request.data.get("notes")
            )
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)


class ChargebackEvidenceAPIView(APIView):
    """POST /chargebacks/<dispute_id>/evidence/ — add evidence."""
    permission_classes = [IsAdminUser]

    def post(self, request, dispute_id: str):
        ev_type = request.data.get("evidence_type")
        ev_data = request.data.get("evidence_data", {})
        if not ev_type:
            return _err("evidence_type is required")
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            result = get_chargeback_service().add_evidence(dispute_id, ev_type, ev_data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)


class ChargebackUserRateAPIView(APIView):
    """GET /chargebacks/users/<user_id>/rate/ — chargeback rate for a user."""
    permission_classes = [IsAdminUser]

    def get(self, request, user_id: int):
        period = int(request.query_params.get("period_days", 30))
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            return _ok(get_chargeback_service().get_user_chargeback_rate(user_id, period))
        except Exception as exc:
            return _err(str(exc), 500)


class ChargebackStatsAPIView(APIView):
    """GET /chargebacks/stats/ — platform-wide chargeback KPIs."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        period = int(request.query_params.get("period_days", 30))
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            return _ok(get_chargeback_service().get_platform_chargeback_stats(period))
        except Exception as exc:
            return _err(str(exc), 500)


class ChargebackHighRiskAPIView(APIView):
    """GET /chargebacks/high-risk/ — users with suspicious chargeback counts."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        min_d  = int(request.query_params.get("min_disputes", 3))
        period = int(request.query_params.get("period_days", 30))
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            users = get_chargeback_service().get_high_risk_users(min_d, period)
            return _ok({"users": users, "total": len(users)})
        except Exception as exc:
            return _err(str(exc), 500)
