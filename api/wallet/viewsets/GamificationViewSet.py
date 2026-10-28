# api/wallet/viewsets/GamificationViewSet.py
"""
Gamification API — Scratchcard & Spin Wheel endpoints.

Endpoints:
  GET  /api/wallet/scratchcard/status/   → check if available + cooldown
  POST /api/wallet/scratchcard/claim/    → claim daily scratchcard
  GET  /api/wallet/spinwheel/config/     → get wheel segments for frontend
  GET  /api/wallet/spinwheel/status/     → check if spin available
  POST /api/wallet/spinwheel/spin/       → spin the wheel
  GET  /api/wallet/gamification/history/ → user's win history
"""
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from ..gamification import (
    GamificationLog,
    ScratchcardService,
    SpinWheelService,
)


# ── Serializers ───────────────────────────────────────────────────

class GamificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamificationLog
        fields = ["id", "event_type", "prize_name", "prize_type",
                  "amount_won", "created_at"]
        read_only_fields = fields


# ── Views ─────────────────────────────────────────────────────────

class ScratchcardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """GET /scratchcard/status/"""
        status_data = ScratchcardService.get_status(request.user)
        return Response(status_data)

    def post(self, request):
        """POST /scratchcard/claim/"""
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() \
             or request.META.get("REMOTE_ADDR", "")
        ua = request.META.get("HTTP_USER_AGENT", "")
        result = ScratchcardService.claim(request.user, ip_address=ip, user_agent=ua)
        http_status = status.HTTP_200_OK if result.get("success") else status.HTTP_429_TOO_MANY_REQUESTS
        return Response(result, status=http_status)


class SpinWheelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, action_name=None):
        if action_name == "config":
            return Response(SpinWheelService.get_wheel_config())
        # default: status
        return Response(SpinWheelService.get_status(request.user))

    def post(self, request):
        """POST /spinwheel/spin/"""
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() \
             or request.META.get("REMOTE_ADDR", "")
        ua = request.META.get("HTTP_USER_AGENT", "")
        result = SpinWheelService.spin(request.user, ip_address=ip, user_agent=ua)
        http_status = status.HTTP_200_OK if result.get("success") else status.HTTP_429_TOO_MANY_REQUESTS
        return Response(result, status=http_status)


class GamificationHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """GET /gamification/history/?limit=20"""
        limit = min(int(request.query_params.get("limit", 20)), 100)
        logs = GamificationLog.objects.filter(user=request.user)[:limit]
        serializer = GamificationLogSerializer(logs, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})


# ── URL additions (append to urls.py) ────────────────────────────
"""
Add to wallet/urls.py:

from .viewsets.GamificationViewSet import (
    ScratchcardView, SpinWheelView, GamificationHistoryView
)

urlpatterns += [
    path("scratchcard/status/",   ScratchcardView.as_view(),  name="wallet-scratchcard-status"),
    path("scratchcard/claim/",    ScratchcardView.as_view(),  name="wallet-scratchcard-claim"),
    path("spinwheel/config/",     SpinWheelView.as_view(), {"action_name": "config"}, name="wallet-spinwheel-config"),
    path("spinwheel/status/",     SpinWheelView.as_view(),    name="wallet-spinwheel-status"),
    path("spinwheel/spin/",       SpinWheelView.as_view(),    name="wallet-spinwheel-spin"),
    path("gamification/history/", GamificationHistoryView.as_view(), name="wallet-gamification-history"),
]
"""
