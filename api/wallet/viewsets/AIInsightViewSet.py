# api/wallet/viewsets/AIInsightViewSet.py
"""
AIInsightViewSet
════════════════
REST interface for the AIInsight model + AIInsightsService.

Endpoints
─────────
GET  /api/wallet/ai-insights/
    List persisted insights for the authenticated user (all types, all periods).

GET  /api/wallet/ai-insights/{id}/
    Retrieve a single persisted insight.

POST /api/wallet/ai-insights/spending/
    Return (and persist) a spending analysis for the requesting user.
    Query params: ?days=30

POST /api/wallet/ai-insights/forecast/
    Return (and persist) an earning forecast.
    Query params: ?days=30

POST /api/wallet/ai-insights/recommend/
    Return (and persist) an AI recommendation.
    Body (optional JSON): {"question": "..."}

POST /api/wallet/ai-insights/{id}/mark_stale/    [admin only]
    Force a re-compute next time the insight is accessed.

DELETE /api/wallet/ai-insights/{id}/             [admin only]
    Remove a persisted insight row.
"""
import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, CharField, IntegerField

from ..models.ai_insight import AIInsight, AIInsightType
from ..pagination import WalletPagePagination

logger = logging.getLogger("wallet.viewsets.ai_insight")


# ── Minimal inline serializer (no separate file needed) ───────────────────────

class AIInsightSerializer(ModelSerializer):
    wallet_id    = IntegerField(source="wallet.id",       read_only=True)
    user_id      = IntegerField(source="wallet.user_id",  read_only=True)
    insight_type = CharField(read_only=True)

    class Meta:
        model  = AIInsight
        fields = [
            "id", "wallet_id", "user_id",
            "insight_type", "period_days",
            "payload", "text_summary",
            "computed_at", "is_stale",
        ]
        read_only_fields = fields


# ── ViewSet ───────────────────────────────────────────────────────────────────

class AIInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for AIInsight model.

    Read-only base (list / retrieve).
    Write actions are provided via explicit @action decorators so that the
    compute endpoints have clear, self-documenting URLs.
    """
    serializer_class  = AIInsightSerializer
    pagination_class  = WalletPagePagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = AIInsight.objects.select_related("wallet__user").order_by("-computed_at")
        if u.is_staff:
            return qs
        return qs.filter(wallet__user=u)

    # ── /spending/ ────────────────────────────────────────────────────

    @action(detail=False, methods=["get", "post"], url_path="spending")
    def spending(self, request):
        """
        GET/POST /api/wallet/ai-insights/spending/?days=30

        Returns a fresh spending analysis and persists it in AIInsight.
        """
        days = self._parse_days(request)
        try:
            wallet  = request.user.wallet
            insight = AIInsight.refresh(wallet, AIInsightType.SPENDING, days)
            return Response({
                "success": True,
                "data":    AIInsightSerializer(insight).data,
            })
        except Exception as exc:
            logger.warning(f"AIInsightViewSet.spending error: {exc}", exc_info=True)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ── /forecast/ ───────────────────────────────────────────────────

    @action(detail=False, methods=["get", "post"], url_path="forecast")
    def forecast(self, request):
        """
        GET/POST /api/wallet/ai-insights/forecast/?days=30

        Returns an earning forecast and persists it.
        """
        days = self._parse_days(request)
        try:
            wallet  = request.user.wallet
            insight = AIInsight.refresh(wallet, AIInsightType.FORECAST, days)
            return Response({
                "success": True,
                "data":    AIInsightSerializer(insight).data,
            })
        except Exception as exc:
            logger.warning(f"AIInsightViewSet.forecast error: {exc}", exc_info=True)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ── /recommend/ ──────────────────────────────────────────────────

    @action(detail=False, methods=["get", "post"], url_path="recommend")
    def recommend(self, request):
        """
        GET/POST /api/wallet/ai-insights/recommend/

        Optional body: {"question": "How can I earn more?"}
        Returns an AI recommendation and persists it.
        """
        days = self._parse_days(request, default=30)
        try:
            wallet = request.user.wallet

            # If a custom question was provided, call the service directly
            # (don't cache per-question; cache only the default recommendation)
            question = request.data.get("question") if request.method == "POST" else None
            if question:
                from ..ai_insights import AIInsightsService
                text = AIInsightsService.get_ai_recommendation(wallet.user_id, question)
                return Response({
                    "success": True,
                    "data": {
                        "insight_type":  "recommend",
                        "text_summary":  text,
                        "question":      question,
                        "is_persisted":  False,
                    },
                })

            insight = AIInsight.refresh(wallet, AIInsightType.RECOMMEND, days)
            return Response({
                "success": True,
                "data":    AIInsightSerializer(insight).data,
            })
        except Exception as exc:
            logger.warning(f"AIInsightViewSet.recommend error: {exc}", exc_info=True)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ── /mark_stale/ (admin) ─────────────────────────────────────────

    @action(
        detail=True,
        methods=["post"],
        url_path="mark_stale",
        permission_classes=[IsAdminUser],
    )
    def mark_stale(self, request, pk=None):
        """POST /api/wallet/ai-insights/{id}/mark_stale/ — admin only."""
        insight = self.get_object()
        insight.is_stale = True
        insight.save(update_fields=["is_stale"])
        return Response({"success": True, "id": insight.id, "is_stale": True})

    # ── DELETE (admin) ────────────────────────────────────────────────

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {"success": False, "error": "Admin required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_days(request, default: int = 30) -> int:
        try:
            days = int(
                request.query_params.get("days")
                or (request.data.get("days") if hasattr(request, "data") else None)
                or default
            )
            return max(1, min(days, 365))
        except (TypeError, ValueError):
            return default
