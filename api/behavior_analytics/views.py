# =============================================================================
# behavior_analytics/views.py  — FIXED
# =============================================================================
from __future__ import annotations

import logging
from datetime import date, timedelta  # ✅ FIXED: timedelta imported from datetime, not timezone

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import CACHE_TTL_DAILY_REPORT
from .exceptions import (
    EngagementCalculationError,
    SessionNotFoundError,
)
from .models import ClickMetric, EngagementScore, StayTime, UserPath
from .permissions import IsOwnerOrStaff, IsStaffOnly
from .serializers import (
    EngagementScoreSerializer,
    EngagementScoreSummarySerializer,
    UserPathSerializer,
)
from .services import EngagementScoreService

logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard: User behaviour summary
# =============================================================================

class UserBehaviourDashboardView(APIView):
    """
    GET /analytics/dashboard/
    Returns a combined snapshot of the authenticated user's analytics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user     = request.user
        today    = timezone.localdate()
        week_ago = today - timedelta(days=7)  # ✅ FIXED: was timezone.timedelta

        latest_score = (
            EngagementScore.objects
            .for_user(user)
            .order_by("-date")
            .first()
        )

        session_count = (
            UserPath.objects
            .for_user(user)
            .in_date_range(week_ago, today)
            .count()
        )

        click_count = (
            ClickMetric.objects
            .filter(path__user=user, clicked_at__date__gte=week_ago)
            .count()
        )

        stay_agg = (
            StayTime.objects
            .filter(path__user=user, created_at__date__gte=week_ago)
            .aggregate_stats()
        )

        data = {
            "user_id":             str(user.pk),
            "period_days":         7,
            "latest_score":        (
                EngagementScoreSerializer(latest_score).data
                if latest_score else None
            ),
            "session_count":       session_count,
            "click_count":         click_count,
            "avg_stay_time_sec":   round(float(stay_agg["avg_duration"] or 0), 1),
            "total_stay_time_sec": stay_agg["total_duration"] or 0,
            "generated_at":        timezone.now().isoformat(),
        }
        return Response(data)


# =============================================================================
# Engagement: Recalculate for authenticated user
# =============================================================================

class RecalculateMyEngagementView(APIView):
    """
    POST /analytics/engagement/recalculate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        raw_date = request.data.get("date")
        target: date | None = None

        if raw_date:
            try:
                target = date.fromisoformat(str(raw_date))
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Expected YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            score = EngagementScoreService.calculate_for_user(
                user=request.user,
                target_date=target,
            )
        except EngagementCalculationError as exc:
            return Response(
                {"detail": str(exc.detail)},
                status=exc.status_code,
            )

        return Response(
            EngagementScoreSummarySerializer(score).data,
            status=status.HTTP_200_OK,
        )


# =============================================================================
# Path: Session lookup by session_id
# =============================================================================

class SessionPathDetailView(APIView):
    """
    GET /analytics/sessions/<session_id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, session_id: str) -> Response:
        user = request.user

        if user.is_staff:
            override_uid = request.query_params.get("user_id")
            if override_uid:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(pk=override_uid)
                except User.DoesNotExist:
                    return Response(
                        {"detail": "User not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

        try:
            path = UserPath.objects.select_full().get(
                user=user, session_id=session_id
            )
        except UserPath.DoesNotExist:
            raise SessionNotFoundError()

        return Response(
            UserPathSerializer(path, context={"request": request}).data
        )


# =============================================================================
# Admin: Global analytics stats (staff only)
# =============================================================================

class GlobalAnalyticsStatsView(APIView):
    """
    GET /analytics/admin/stats/
    Staff only.
    """
    permission_classes = [IsStaffOnly]

    @method_decorator(cache_page(60 * 5))
    def get(self, request: Request) -> Response:
        today    = timezone.localdate()
        start_dt = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        end_dt = start_dt + timedelta(days=1)  # ✅ FIXED: was timezone.timedelta

        from django.db.models import Avg, Count, Sum

        total_sessions = UserPath.objects.filter(created_at__range=(start_dt, end_dt)).count()
        total_clicks   = ClickMetric.objects.filter(clicked_at__range=(start_dt, end_dt)).count()
        avg_stay       = (
            StayTime.objects
            .filter(created_at__range=(start_dt, end_dt))
            .aggregate(avg=Avg("duration_seconds"))["avg"] or 0
        )
        scores_today = EngagementScore.objects.filter(date=today)
        avg_score    = scores_today.aggregate(avg=Avg("score"))["avg"] or 0

        data = {
            "date":           str(today),
            "total_sessions": total_sessions,
            "total_clicks":   total_clicks,
            "avg_stay_sec":   round(float(avg_stay), 1),
            "avg_score":      round(float(avg_score), 2),
            "scored_users":   scores_today.count(),
            "generated_at":   timezone.now().isoformat(),
        }
        return Response(data)


# =============================================================================
# Webhook: Receive batch analytics events from frontend SDK
# =============================================================================

class AnalyticsEventWebhookView(APIView):
    """
    POST /analytics/events/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        data       = request.data
        session_id = data.get("session_id", "").strip()
        events     = data.get("events", [])

        if not session_id:
            return Response(
                {"detail": "session_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(events, list) or not events:
            return Response(
                {"detail": "events must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(events) > 500:
            return Response(
                {"detail": "Batch exceeds maximum of 500 events."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            click_events = [e for e in events if e.get("type") == "click"]
            nav_nodes    = [e for e in events if e.get("type") == "nav"]

            if click_events or nav_nodes:
                _enqueue_webhook_events.delay(  # noqa: F821 — defined below
                    user_id=str(request.user.pk),
                    session_id=session_id,
                    click_events=click_events,
                    nav_nodes=nav_nodes,
                )
        except Exception:
            logger.exception(
                "analytics_webhook.enqueue_failed user_id=%s session_id=%s",
                request.user.pk, session_id,
            )

        return Response(
            {"accepted": len(events)},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# Internal Celery task
# ---------------------------------------------------------------------------

from celery import shared_task  # noqa: E402


@shared_task(
    name="behavior_analytics.views._enqueue_webhook_events",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    ignore_result=True,
)
def _enqueue_webhook_events(
    user_id: str,
    session_id: str,
    click_events: list[dict],
    nav_nodes: list[dict],
) -> None:
    from django.contrib.auth import get_user_model
    from .models import UserPath
    from .services import ClickMetricService, UserPathService
    from .exceptions import DuplicateSessionError

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("_enqueue_webhook_events.user_not_found user_id=%s", user_id)
        return

    try:
        path = UserPath.objects.get(user=user, session_id=session_id)
    except UserPath.DoesNotExist:
        try:
            path = UserPathService.create_path(
                user=user, session_id=session_id, device_type="web"
            )
        except DuplicateSessionError:
            path = UserPath.objects.get(user=user, session_id=session_id)

    if nav_nodes:
        try:
            UserPathService.append_nodes(path=path, new_nodes=nav_nodes)
        except Exception:
            logger.exception("_enqueue_webhook_events.nav_append_failed")

    if click_events:
        try:
            ClickMetricService.bulk_record(path=path, events=click_events)
        except Exception:
            logger.exception("_enqueue_webhook_events.click_insert_failed")