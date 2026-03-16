# =============================================================================
# behavior_analytics/viewsets.py
# =============================================================================
"""
DRF ViewSets for the behavior_analytics application.

Design rules:
  - ViewSets are thin: they validate input (via serializers), delegate to
    services, and return responses.  No business logic in views.
  - get_queryset() always filters to the authenticated user's own data
    (or allows staff/admin to see all).
  - perform_create / custom actions call service methods.
  - All actions have explicit permission_classes and serializer_class.
  - Pagination is applied globally via DEFAULT_PAGINATION_CLASS; custom
    page-size allowed up to MAX_PAGE_SIZE.
  - HTTP method guards: unsafe methods (POST/PUT/PATCH/DELETE) check
    object-level permissions via check_object_permissions.
"""

from __future__ import annotations

import logging
from datetime import date

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .choices import SessionStatus
from .constants import MAX_PAGE_SIZE
from .exceptions import (
    AnalyticsStorageError,
    DuplicateSessionError,
    EngagementCalculationError,
    InvalidClickMetricError,
    SessionNotFoundError,
)
from .filters import ClickMetricFilter, EngagementScoreFilter, StayTimeFilter, UserPathFilter
from .models import ClickMetric, EngagementScore, StayTime, UserPath
from .permissions import IsOwnerOrStaff
from .serializers import (
    ClickMetricBulkSerializer,
    ClickMetricSerializer,
    EngagementScoreSerializer,
    EngagementScoreSummarySerializer,
    StayTimeSerializer,
    UserPathCreateSerializer,
    UserPathSerializer,
)
from .services import (
    ClickMetricService,
    EngagementScoreService,
    StayTimeService,
    UserPathService,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user_or_all(request: Request):
    """Return a user filter kwarg dict respecting staff visibility."""
    if request.user.is_staff:
        return {}
    return {"user": request.user}


# =============================================================================
# UserPathViewSet
# =============================================================================

class UserPathViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    CRUD-lite ViewSet for UserPath.

    Endpoints:
        GET    /paths/                  → list (own paths; staff sees all)
        POST   /paths/                  → create new path
        GET    /paths/{id}/             → retrieve
        POST   /paths/{id}/close/       → close a session
        POST   /paths/{id}/add_nodes/   → append path nodes
    """

    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    filterset_class    = UserPathFilter
    ordering_fields    = ["created_at", "updated_at", "status"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = UserPath.objects.select_full()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return UserPathCreateSerializer
        return UserPathSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        path = UserPathService.create_path(
            user=request.user,
            **serializer.validated_data,
        )
        out = UserPathSerializer(path, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request: Request, pk=None) -> Response:
        """
        Mark this session as completed (or bounced/expired).
        Body: { "exit_url": "...", "status": "completed" }
        """
        path = self.get_object()
        exit_url    = request.data.get("exit_url", "")
        new_status  = request.data.get("status", SessionStatus.COMPLETED)

        if new_status not in SessionStatus.values:
            return Response(
                {"detail": f"Invalid status '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        path = UserPathService.close_path(
            path=path, exit_url=exit_url, status=new_status
        )
        return Response(UserPathSerializer(path, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="add_nodes")
    def add_nodes(self, request: Request, pk=None) -> Response:
        """
        Append one or more nodes to an existing path.
        Body: { "nodes": [ { "url": "...", "type": "navigation" }, ... ] }
        """
        path  = self.get_object()
        nodes = request.data.get("nodes", [])
        if not isinstance(nodes, list) or not nodes:
            return Response(
                {"detail": "nodes must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        path = UserPathService.append_nodes(path=path, new_nodes=nodes)
        return Response(UserPathSerializer(path, context={"request": request}).data)


# =============================================================================
# ClickMetricViewSet
# =============================================================================

class ClickMetricViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Endpoints:
        GET    /clicks/              → list
        POST   /clicks/              → record single click
        GET    /clicks/{id}/         → retrieve
        POST   /clicks/bulk/         → record multiple clicks
        GET    /clicks/top_elements/ → top clicked elements
    """

    serializer_class   = ClickMetricSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    filterset_class    = ClickMetricFilter
    ordering_fields    = ["clicked_at", "created_at", "category"]
    ordering           = ["-clicked_at"]

    def get_queryset(self):
        qs = ClickMetric.objects.select_full()
        if not self.request.user.is_staff:
            qs = qs.filter(path__user=self.request.user)
        return qs

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        path = vd.pop("path")
        self.check_object_permissions(request, path)

        metric = ClickMetricService.record_click(path=path, **vd)
        return Response(
            ClickMetricSerializer(metric, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request: Request) -> Response:
        """Batch-insert up to MAX_CLICK_METRICS_PER_SESSION events."""
        serializer = ClickMetricBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            path = UserPath.objects.get(
                pk=serializer.validated_data["path_id"],
                user=request.user,
            )
        except UserPath.DoesNotExist:
            return Response({"detail": "Path not found."}, status=status.HTTP_404_NOT_FOUND)

        events  = [dict(e) for e in serializer.validated_data["events"]]
        created = ClickMetricService.bulk_record(path=path, events=events)
        return Response({"created": len(created)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="top_elements")
    def top_elements(self, request: Request) -> Response:
        """Return the top-N most clicked CSS selectors."""
        limit = min(int(request.query_params.get("limit", 10)), 50)
        data  = self.get_queryset().top_elements(limit=limit)
        return Response(list(data))


# =============================================================================
# StayTimeViewSet
# =============================================================================

class StayTimeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Endpoints:
        GET  /stay-times/        → list
        POST /stay-times/        → record
        GET  /stay-times/{id}/   → retrieve
        GET  /stay-times/stats/  → aggregate statistics
    """

    serializer_class   = StayTimeSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    filterset_class    = StayTimeFilter
    ordering_fields    = ["duration_seconds", "created_at"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = StayTime.objects.all().select_related("path", "path__user")
        if not self.request.user.is_staff:
            qs = qs.filter(path__user=self.request.user)
        return qs

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd   = serializer.validated_data
        path = vd.pop("path")
        self.check_object_permissions(request, path)

        stay = StayTimeService.record(path=path, **vd)
        return Response(
            StayTimeSerializer(stay, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        """Return aggregate statistics for the filtered queryset."""
        data = self.filter_queryset(self.get_queryset()).aggregate_stats()
        return Response(data)


# =============================================================================
# EngagementScoreViewSet
# =============================================================================

class EngagementScoreViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Endpoints:
        GET  /engagement-scores/              → list
        GET  /engagement-scores/{id}/         → retrieve
        POST /engagement-scores/recalculate/  → trigger recalculation
        GET  /engagement-scores/summary/      → user summary for date range
    """

    serializer_class   = EngagementScoreSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
    filterset_class    = EngagementScoreFilter
    ordering_fields    = ["date", "score"]
    ordering           = ["-date"]

    def get_queryset(self):
        qs = EngagementScore.objects.select_full()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=["post"], url_path="recalculate")
    def recalculate(self, request: Request) -> Response:
        """
        Trigger an immediate (synchronous) recalculation of the
        engagement score for the requesting user on the given date.

        Body (optional): { "date": "YYYY-MM-DD" }
        """
        raw_date = request.data.get("date")
        target   = None
        if raw_date:
            try:
                target = date.fromisoformat(str(raw_date))
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Expected YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        eng = EngagementScoreService.calculate_for_user(
            user=request.user, target_date=target
        )
        return Response(
            EngagementScoreSummarySerializer(eng).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request: Request) -> Response:
        """
        Aggregate summary (avg, max, min score) for a given date range.
        Query params: start_date, end_date (YYYY-MM-DD).
        """
        start_str = request.query_params.get("start_date")
        end_str   = request.query_params.get("end_date")

        qs = self.get_queryset()
        try:
            if start_str:
                qs = qs.filter(date__gte=date.fromisoformat(start_str))
            if end_str:
                qs = qs.filter(date__lte=date.fromisoformat(end_str))
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Expected YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stats = qs.aggregate_stats()
        return Response(stats)
