"""
views.py – API views for Postback Engine.
"""
import logging
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    AdNetworkConfig, ClickLog, Conversion,
    PostbackRawLog, HourlyStat,
)
from .serializers import (
    PostbackRawLogSerializer, ConversionSerializer,
    ClickLogSerializer, AdNetworkConfigSerializer,
    HourlyStatSerializer, NetworkStatsSerializer,
)
from .services import receive_postback, generate_click
from .exceptions import PostbackEngineError

logger = logging.getLogger(__name__)


# ── Postback Reception ────────────────────────────────────────────────────────

class PostbackReceiveView(APIView):
    """
    Receives S2S postbacks from CPA networks.
    Always returns 200 OK to prevent enumeration via status codes.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def get(self, request, network_key: str):
        return self._handle(request, network_key)

    def post(self, request, network_key: str):
        return self._handle(request, network_key)

    def _handle(self, request, network_key: str):
        try:
            raw_log = receive_postback(
                network_key=network_key,
                raw_payload=dict(request.query_params) if request.method == "GET"
                            else {**dict(request.query_params), **(request.data or {})},
                method=request.method,
                query_string=request.META.get("QUERY_STRING", ""),
                request_headers=dict(request.headers),
                source_ip=self._get_client_ip(request),
                signature=request.headers.get("X-Postback-Signature", "")
                          or request.query_params.get("sig", ""),
                timestamp_str=request.headers.get("X-Postback-Timestamp", "")
                              or request.query_params.get("ts", ""),
                nonce=request.headers.get("X-Postback-Nonce", "")
                      or request.query_params.get("nonce", ""),
                body_bytes=request.body,
            )
            return Response({
                "status": "ok",
                "ref": str(raw_log.id),
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("PostbackReceiveView unexpected error for network=%s", network_key)
            return Response({"status": "ok", "ref": None}, status=status.HTTP_200_OK)

    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class ImpressionTrackView(APIView):
    """Track ad impressions (1x1 pixel or JSON)."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, network_key: str):
        from .models import Impression, AdNetworkConfig
        try:
            network = AdNetworkConfig.objects.get_by_key(network_key)
            if network:
                Impression.objects.create(
                    tenant=network.tenant,
                    network=network,
                    offer_id=request.query_params.get("offer_id", ""),
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    placement=request.query_params.get("placement", ""),
                )
        except Exception:
            pass
        # Return 1x1 transparent GIF
        pixel = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!"
            b"\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        from django.http import HttpResponse
        return HttpResponse(pixel, content_type="image/gif")


# ── Click Tracking ─────────────────────────────────────────────────────────────

class ClickTrackView(APIView):
    """Generate a click tracking ID and redirect to offer URL."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        network_key = request.query_params.get("network")
        offer_id = request.query_params.get("offer_id", "")

        network = get_object_or_404(AdNetworkConfig, network_key=network_key)

        click_log = generate_click(
            user=request.user,
            network=network,
            offer_id=offer_id,
            offer_name=request.query_params.get("offer_name", ""),
            ip_address=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            country=request.query_params.get("country", ""),
            sub_id=request.query_params.get("sub_id", ""),
            referrer=request.META.get("HTTP_REFERER", ""),
        )

        return Response({
            "click_id": click_log.click_id,
            "expires_at": click_log.expires_at,
        })


# ── Admin Views ────────────────────────────────────────────────────────────────

class PostbackLogListView(generics.ListAPIView):
    serializer_class = PostbackRawLogSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = PostbackRawLog.objects.select_related("network", "resolved_user")
        network_key = self.request.query_params.get("network")
        if network_key:
            qs = qs.filter(network__network_key=network_key)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-received_at")[:500]


class PostbackLogDetailView(generics.RetrieveAPIView):
    serializer_class = PostbackRawLogSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = PostbackRawLog.objects.select_related("network", "resolved_user")


class ConversionListView(generics.ListAPIView):
    serializer_class = ConversionSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = Conversion.objects.select_related("user", "network")
        user_id = self.request.query_params.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs.order_by("-converted_at")[:500]


class ConversionDetailView(generics.RetrieveAPIView):
    serializer_class = ConversionSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Conversion.objects.select_related("user", "network", "raw_log")


class ClickLogListView(generics.ListAPIView):
    serializer_class = ClickLogSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return ClickLog.objects.select_related("user", "network").order_by("-clicked_at")[:500]


class AdNetworkConfigViewSet(viewsets.ModelViewSet):
    serializer_class = AdNetworkConfigSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = AdNetworkConfig.objects.all()


class NetworkStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, network_id):
        from .services import get_network_stats
        network = get_object_or_404(AdNetworkConfig, pk=network_id)
        date_str = request.query_params.get("date")
        date = None
        if date_str:
            from datetime import date as date_cls
            try:
                date = date_cls.fromisoformat(date_str)
            except ValueError:
                pass
        data = get_network_stats(network, date=date)
        return Response(data)


class HourlyStatsView(generics.ListAPIView):
    serializer_class = HourlyStatSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = HourlyStat.objects.select_related("network")
        network_key = self.request.query_params.get("network")
        if network_key:
            qs = qs.filter(network__network_key=network_key)
        return qs.order_by("-date", "-hour")[:168]  # last 7 days x 24h


class ReplayPostbackView(APIView):
    """Re-process a failed/rejected postback."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        raw_log = get_object_or_404(PostbackRawLog, pk=pk)
        from .tasks import process_postback_task
        process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
        return Response({"status": "queued", "raw_log_id": str(pk)})


class TestPostbackView(APIView):
    """Send a test postback to verify network config (test mode only)."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, network_key: str):
        network = get_object_or_404(AdNetworkConfig, network_key=network_key)
        if not network.is_test_mode:
            return Response(
                {"error": "Enable test_mode on the network config first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        test_payload = {
            "lead_id": f"TEST_{timezone.now().timestamp():.0f}",
            "offer_id": request.data.get("offer_id", "test_offer"),
            "payout": "0.10",
            "currency": "USD",
            **(request.data or {}),
        }
        raw_log = receive_postback(
            network_key=network_key,
            raw_payload=test_payload,
            method="POST",
            query_string="",
            request_headers={},
            source_ip="127.0.0.1",
            signature="",
            timestamp_str="",
            nonce="",
            body_bytes=b"",
        )
        return Response({"status": "ok", "raw_log_id": str(raw_log.id)})


class HealthCheckView(APIView):
    """Postback engine health check."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .models import AdNetworkConfig, PostbackRawLog
        return Response({
            "status": "healthy",
            "active_networks": AdNetworkConfig.objects.active().count(),
            "pending_logs": PostbackRawLog.objects.filter(
                status="received"
            ).count(),
            "timestamp": timezone.now().isoformat(),
        })
