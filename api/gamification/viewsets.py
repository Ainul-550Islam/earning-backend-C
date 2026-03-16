"""
Gamification ViewSets — DRF ViewSets wiring models to the REST API.
All mutations go through the service layer; viewsets handle HTTP concerns only.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .choices import ContestCycleStatus, LeaderboardScope
from .constants import DEFAULT_LEADERBOARD_TOP_N
from .exceptions import (
    GamificationServiceError,
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
    InvalidPointsError,
    DuplicateAchievementError,
    UserNotFoundError,
)
from .filters import ContestCycleFilter, ContestRewardFilter, UserAchievementFilter
from .models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
from .pagination import GamificationPagination
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from .serializers import (
    ContestCycleSerializer,
    ContestCycleListSerializer,
    LeaderboardSnapshotSerializer,
    ContestRewardSerializer,
    UserAchievementSerializer,
)
from . import services

logger = logging.getLogger(__name__)


def _service_error_response(exc: Exception, default_msg: str = "An error occurred.") -> Response:
    """Convert a service-layer exception to a structured DRF Response."""
    message = str(exc) if str(exc) else default_msg
    logger.warning("Gamification service error: %s: %s", type(exc).__name__, message)
    return Response(
        {"detail": message, "error_type": type(exc).__name__},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# ContestCycle ViewSet
# ---------------------------------------------------------------------------

class ContestCycleViewSet(viewsets.ModelViewSet):
    """
    CRUD + lifecycle actions for ContestCycle.

    List/Retrieve: public (read-only)
    Create/Update/Delete: admin only
    activate/complete/archive: admin only
    """

    queryset = ContestCycle.objects.all().order_by("-created_at")
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = GamificationPagination
    filterset_class = ContestCycleFilter

    def get_serializer_class(self):
        if self.action == "list":
            return ContestCycleListSerializer
        return ContestCycleSerializer

    def perform_create(self, serializer):
        validated = serializer.validated_data
        try:
            cycle = services.create_contest_cycle(
                name=validated["name"],
                slug=validated["slug"],
                start_date=validated["start_date"],
                end_date=validated["end_date"],
                description=validated.get("description", ""),
                points_multiplier=validated.get("points_multiplier"),
                is_featured=validated.get("is_featured", False),
                max_participants=validated.get("max_participants"),
                metadata=validated.get("metadata", {}),
                created_by_id=self.request.user.pk,
            )
        except GamificationServiceError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        serializer.instance = cycle

    @action(detail=True, methods=["post"], url_path="activate", permission_classes=[permissions.IsAdminUser])
    def activate(self, request: Request, pk: Any = None) -> Response:
        """Transition a DRAFT ContestCycle to ACTIVE."""
        try:
            cycle = services.activate_contest_cycle(cycle_id=pk, actor_id=request.user.pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        serializer = ContestCycleSerializer(cycle)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete", permission_classes=[permissions.IsAdminUser])
    def complete(self, request: Request, pk: Any = None) -> Response:
        """Transition an ACTIVE ContestCycle to COMPLETED and generate final snapshot."""
        try:
            cycle = services.complete_contest_cycle(cycle_id=pk, actor_id=request.user.pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        serializer = ContestCycleSerializer(cycle)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="distribute-rewards", permission_classes=[permissions.IsAdminUser])
    def distribute_rewards(self, request: Request, pk: Any = None) -> Response:
        """Distribute rewards for a COMPLETED cycle based on the latest leaderboard snapshot."""
        try:
            result = services.distribute_cycle_rewards(cycle_id=pk)
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (ContestCycleStateError, LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="leaderboard")
    def leaderboard(self, request: Request, pk: Any = None) -> Response:
        """Return the latest finalized leaderboard snapshot for this cycle."""
        scope = request.query_params.get("scope", LeaderboardScope.GLOBAL)
        scope_ref = request.query_params.get("scope_ref", "")

        if scope not in LeaderboardScope.values:
            return Response(
                {"detail": f"Invalid scope. Valid choices: {LeaderboardScope.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            snapshot = services.get_latest_snapshot(
                cycle_id=pk, scope=scope, scope_ref=scope_ref
            )
        except GamificationServiceError as exc:
            return _service_error_response(exc)

        if snapshot is None:
            return Response(
                {"detail": "No finalized leaderboard snapshot found for this cycle."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LeaderboardSnapshotSerializer(snapshot)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# LeaderboardSnapshot ViewSet
# ---------------------------------------------------------------------------

class LeaderboardSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to LeaderboardSnapshot records.
    Admin users may trigger manual snapshot generation.
    """

    queryset = LeaderboardSnapshot.objects.select_related("contest_cycle").order_by("-created_at")
    serializer_class = LeaderboardSnapshotSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = GamificationPagination

    def get_queryset(self):
        qs = super().get_queryset()
        cycle_id = self.request.query_params.get("cycle_id")
        if cycle_id:
            qs = qs.filter(contest_cycle_id=cycle_id)
        scope = self.request.query_params.get("scope")
        if scope:
            if scope not in LeaderboardScope.values:
                return qs.none()
            qs = qs.filter(scope=scope)
        return qs

    @action(
        detail=False,
        methods=["post"],
        url_path="generate",
        permission_classes=[permissions.IsAdminUser],
    )
    def generate(self, request: Request) -> Response:
        """
        Manually trigger leaderboard snapshot generation.

        Body params: cycle_id (required), scope, scope_ref, top_n.
        """
        cycle_id = request.data.get("cycle_id")
        if not cycle_id:
            return Response(
                {"detail": "cycle_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope = request.data.get("scope", LeaderboardScope.GLOBAL)
        scope_ref = request.data.get("scope_ref", "")
        top_n = request.data.get("top_n", DEFAULT_LEADERBOARD_TOP_N)

        try:
            top_n = int(top_n)
        except (TypeError, ValueError):
            return Response(
                {"detail": "top_n must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            snapshot = services.generate_leaderboard_snapshot(
                cycle_id=cycle_id,
                scope=scope,
                scope_ref=scope_ref,
                top_n=top_n,
            )
        except ContestCycleNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (LeaderboardGenerationError, GamificationServiceError) as exc:
            return _service_error_response(exc)

        serializer = LeaderboardSnapshotSerializer(snapshot)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# ContestReward ViewSet
# ---------------------------------------------------------------------------

class ContestRewardViewSet(viewsets.ModelViewSet):
    queryset = ContestReward.objects.select_related("contest_cycle").order_by("rank_from")
    serializer_class = ContestRewardSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = GamificationPagination
    filterset_class = ContestRewardFilter

    def perform_create(self, serializer):
        validated = serializer.validated_data
        try:
            reward = services.create_contest_reward(
                cycle_id=validated["contest_cycle"].pk,
                title=validated["title"],
                reward_type=validated["reward_type"],
                rank_from=validated["rank_from"],
                rank_to=validated["rank_to"],
                reward_value=validated.get("reward_value"),
                description=validated.get("description", ""),
                total_budget=validated.get("total_budget"),
                image_url=validated.get("image_url", ""),
                metadata=validated.get("metadata", {}),
            )
        except (GamificationServiceError, ContestCycleNotFoundError) as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        serializer.instance = reward


# ---------------------------------------------------------------------------
# UserAchievement ViewSet
# ---------------------------------------------------------------------------

class UserAchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only listing of UserAchievement records.
    Users see only their own achievements; admins see all.
    Achievement awarding is done via service layer / tasks.
    """

    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = GamificationPagination
    filterset_class = UserAchievementFilter

    def get_queryset(self):
        user = self.request.user
        qs = UserAchievement.objects.with_related().awarded().order_by("-awarded_at")
        if not user.is_staff:
            qs = qs.for_user(user.pk)
        return qs

    @action(detail=False, methods=["get"], url_path="my-points")
    def my_points(self, request: Request) -> Response:
        """Return the requesting user's total awarded points, optionally per cycle."""
        cycle_id = request.query_params.get("cycle_id")
        try:
            total = services.get_user_total_points(
                user_id=request.user.pk, cycle_id=cycle_id if cycle_id else None
            )
            rank = None
            if cycle_id:
                rank = services.get_user_rank_in_cycle(
                    user_id=request.user.pk, cycle_id=cycle_id
                )
        except (UserNotFoundError, ContestCycleNotFoundError, GamificationServiceError) as exc:
            return _service_error_response(exc)

        return Response(
            {
                "user_id": str(request.user.pk),
                "cycle_id": cycle_id,
                "total_points": total,
                "rank": rank,
            }
        )
