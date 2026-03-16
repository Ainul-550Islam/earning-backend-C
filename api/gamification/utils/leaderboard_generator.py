"""
Leaderboard Generator — Builds ranked leaderboard entries from DB aggregations.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from ..choices import LeaderboardScope
from ..constants import DEFAULT_LEADERBOARD_TOP_N, MAX_RANK_VALUE
from ..exceptions import LeaderboardGenerationError

logger = logging.getLogger(__name__)
User = get_user_model()


class LeaderboardGenerator:
    """
    Generates a ranked list of leaderboard entries for a ContestCycle.

    The generator aggregates ``UserAchievement.points_awarded`` per user,
    sorts descending, and assigns dense ranks. Users with equal points
    receive the same rank.

    Usage:
        gen = LeaderboardGenerator(cycle=cycle, scope="GLOBAL")
        entries = gen.generate(top_n=100)
    """

    def __init__(
        self,
        cycle: Any,
        scope: str = LeaderboardScope.GLOBAL,
        scope_ref: str = "",
    ) -> None:
        """
        Args:
            cycle:     ContestCycle instance.
            scope:     Leaderboard scope (GLOBAL, REGIONAL, CATEGORY).
            scope_ref: Optional qualifier (e.g. region code).

        Raises:
            ValueError: If cycle is None.
            LeaderboardGenerationError: If scope is invalid.
        """
        if cycle is None:
            raise ValueError("cycle must not be None.")
        if scope not in LeaderboardScope.values:
            raise LeaderboardGenerationError(
                f"Invalid scope '{scope}'. Valid choices: {LeaderboardScope.values}"
            )
        self._cycle = cycle
        self._scope = scope
        self._scope_ref = scope_ref or ""

    def generate(self, top_n: int = DEFAULT_LEADERBOARD_TOP_N) -> list[dict]:
        """
        Build and return sorted leaderboard entries.

        Each entry dict has:
            rank          (int, 1-based, dense ranking)
            user_id       (str)
            display_name  (str)
            points        (int)
            delta_rank    (None — populated by caller from previous snapshot if needed)

        Args:
            top_n: Maximum number of entries to return (1–1000).

        Returns:
            Ordered list of entry dicts (rank ascending).

        Raises:
            LeaderboardGenerationError: On invalid top_n or unexpected DB errors.
        """
        from ..models import UserAchievement

        if not isinstance(top_n, int) or top_n < 1 or top_n > 1000:
            raise LeaderboardGenerationError(
                f"top_n must be an integer between 1 and 1000, got {top_n!r}."
            )

        logger.info(
            "LeaderboardGenerator.generate: cycle=%s scope=%s top_n=%s",
            getattr(self._cycle, "id", "?"),
            self._scope,
            top_n,
        )

        try:
            qs = (
                UserAchievement.objects
                .filter(
                    contest_cycle=self._cycle,
                    is_awarded=True,
                )
                .values("user_id")
                .annotate(
                    total_points=Coalesce(Sum("points_awarded"), Value(0))
                )
                .order_by("-total_points")
            )
        except Exception as exc:
            raise LeaderboardGenerationError(
                f"Database error during leaderboard aggregation: {exc}"
            ) from exc

        if not qs.exists():
            logger.info(
                "LeaderboardGenerator.generate: no awarded achievements for cycle=%s; "
                "returning empty leaderboard.",
                getattr(self._cycle, "id", "?"),
            )
            return []

        # Build user display name map in one query to avoid N+1
        user_ids = [row["user_id"] for row in qs[:top_n + 100]]  # slight over-fetch
        try:
            users = {
                u.pk: self._get_display_name(u)
                for u in User.objects.filter(pk__in=user_ids).only(
                    "pk", "username", "first_name", "last_name"
                )
            }
        except Exception as exc:
            logger.warning(
                "LeaderboardGenerator: failed to fetch user display names: %s. "
                "Falling back to user_id strings.",
                exc,
            )
            users = {}

        entries: list[dict] = []
        current_rank = 0
        previous_points: int | None = None
        rank_counter = 0  # counts how many entries have been processed

        for row in qs:
            rank_counter += 1
            points = row["total_points"] or 0

            # Dense ranking: same points = same rank
            if points != previous_points:
                current_rank = rank_counter
                previous_points = points

            if current_rank > MAX_RANK_VALUE:
                logger.warning(
                    "LeaderboardGenerator: rank %d exceeds MAX_RANK_VALUE=%d; truncating.",
                    current_rank,
                    MAX_RANK_VALUE,
                )
                break

            user_id = row["user_id"]
            entries.append(
                {
                    "rank": current_rank,
                    "user_id": str(user_id),
                    "display_name": users.get(user_id, str(user_id)),
                    "points": int(points),
                    "delta_rank": None,
                }
            )

            if len(entries) >= top_n:
                break

        logger.info(
            "LeaderboardGenerator.generate: produced %d entries for cycle=%s.",
            len(entries),
            getattr(self._cycle, "id", "?"),
        )
        return entries

    @staticmethod
    def _get_display_name(user: Any) -> str:
        """
        Build a display name from the user model.
        Falls back gracefully if fields are missing or empty.
        """
        try:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if full_name:
                return full_name
            username = getattr(user, "username", None)
            if username:
                return str(username)
            return str(user.pk)
        except Exception:
            return str(getattr(user, "pk", "unknown"))
