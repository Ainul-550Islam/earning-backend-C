# fraud_detection/views_feedback.py — Feedback API Views
# DRY: all logic in feedback.py
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)
def _ok(d, st=200):  return Response({"success": True, "data": d}, status=st)
def _err(m, st=400): return Response({"success": False, "error": str(m)}, status=st)


class FeedbackSubmitAPIView(APIView):
    """POST /feedback/submit/ — analyst submits verdict on a fraud alert."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        alert_id   = request.data.get("alert_id")
        verdict    = request.data.get("verdict")
        confidence = int(request.data.get("confidence", 80))
        if not alert_id or not verdict:
            return _err("alert_id and verdict are required")
        try:
            from api.fraud_detection.feedback import get_feedback_service
            rec = get_feedback_service().submit_feedback(
                alert_id   = alert_id,
                analyst_id = request.user.pk,
                verdict    = verdict,
                confidence = confidence,
                notes      = request.data.get("notes"),
            )
            return _ok({"feedback_id": rec.feedback_id, "verdict": rec.verdict.value,
                        "model_impact": rec.model_impact}, 201)
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            logger.error("FeedbackSubmitAPIView: %s", exc, exc_info=True)
            return _err(str(exc), 500)


class FeedbackBulkAPIView(APIView):
    """POST /feedback/bulk/ — submit feedback for multiple alerts."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        items = request.data.get("items", [])
        if not items:
            return _err("items list is required")
        try:
            from api.fraud_detection.feedback import get_feedback_service
            result = get_feedback_service().bulk_submit(items, request.user.pk)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)


class FeedbackAnalystStatsAPIView(APIView):
    """GET /feedback/analysts/me/stats/ — my accuracy stats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.fraud_detection.feedback import get_feedback_service
        return _ok(get_feedback_service().get_analyst_stats(request.user.pk))


class FeedbackTeamStatsAPIView(APIView):
    """GET /feedback/analysts/team-stats/ — admin: stats for all analysts."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        analyst_ids = request.query_params.getlist("analyst_id")
        if not analyst_ids:
            return _err("analyst_id[] param required")
        from api.fraud_detection.feedback import get_feedback_service
        return _ok(get_feedback_service().get_team_stats(analyst_ids))


class FeedbackFPRateAPIView(APIView):
    """GET /feedback/fp-rate/ — false positive rate dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period   = int(request.query_params.get("period_days", 7))
        detector = request.query_params.get("detector")
        from api.fraud_detection.feedback import get_feedback_service
        return _ok(get_feedback_service().get_false_positive_rate(period, detector))


class FeedbackAdaptiveThresholdAPIView(APIView):
    """GET /feedback/adaptive-threshold/<detector>/ — current adaptive threshold."""
    permission_classes = [IsAuthenticated]

    def get(self, request, detector: str):
        base = int(request.query_params.get("base", 70))
        from api.fraud_detection.feedback import get_feedback_service
        threshold = get_feedback_service().get_adaptive_threshold(detector, base)
        return _ok({"detector": detector, "threshold": threshold, "base": base})
