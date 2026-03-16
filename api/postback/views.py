"""views.py – Non-viewset views for the postback module (admin portal)."""
import logging
from django.utils import timezone
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class PostbackDashboardView(APIView):
    """
    GET /api/postback/admin/dashboard/
    Real-time stats for the admin dashboard.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.db.models import Count, Q
        from .models import PostbackLog, NetworkPostbackConfig
        from .choices import PostbackStatus

        since = timezone.now() - timezone.timedelta(hours=24)

        stats = PostbackLog.objects.filter(received_at__gte=since).aggregate(
            total=Count("id"),
            rewarded=Count("id", filter=Q(status=PostbackStatus.REWARDED)),
            validated=Count("id", filter=Q(status=PostbackStatus.VALIDATED)),
            rejected=Count("id", filter=Q(status=PostbackStatus.REJECTED)),
            duplicate=Count("id", filter=Q(status=PostbackStatus.DUPLICATE)),
            failed=Count("id", filter=Q(status=PostbackStatus.FAILED)),
            pending=Count("id", filter=Q(status__in=[
                PostbackStatus.RECEIVED, PostbackStatus.PROCESSING
            ])),
        )

        per_network = (
            PostbackLog.objects.filter(received_at__gte=since)
            .values("network__name", "network__network_key")
            .annotate(
                total=Count("id"),
                rewarded=Count("id", filter=Q(status=PostbackStatus.REWARDED)),
                rejected=Count("id", filter=Q(status=PostbackStatus.REJECTED)),
            )
            .order_by("-total")[:10]
        )

        return Response({
            "period_hours": 24,
            "summary": stats,
            "per_network": list(per_network),
            "active_networks": NetworkPostbackConfig.objects.active().count(),
        })


class PostbackRetryView(APIView):
    """
    POST /api/postback/admin/logs/{id}/retry/
    Manually re-queue a failed postback for processing.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk=None):
        from .models import PostbackLog
        from .choices import PostbackStatus
        from .tasks import process_postback

        try:
            log = PostbackLog.objects.get(pk=pk)
        except PostbackLog.DoesNotExist:
            return Response({"detail": "PostbackLog not found."}, status=404)

        if log.status not in (PostbackStatus.FAILED, PostbackStatus.REJECTED):
            return Response(
                {"detail": f"Only FAILED or REJECTED logs can be retried. Current status: {log.status}."},
                status=400,
            )

        process_postback.delay(
            str(log.pk),
            signature="",
            timestamp_str="",
            nonce="",
            body_bytes_hex="",
            path="",
            query_params={},
        )
        logger.info("Admin %s manually retried postback log %s", request.user.pk, pk)
        return Response({"status": "queued", "log_id": str(log.pk)})