# =============================================================================
# behavior_analytics/services.py
# =============================================================================
"""
Service layer for the behavior_analytics application.

All business logic lives here.  Views and tasks call services; services call
managers/models.  Services never import from views, serializers, or tasks.

Design rules:
  - Every public method is a plain function or a class method.
  - DB operations that must be atomic use transaction.atomic().
  - External failures (cache, Celery) are caught and logged; they never
    propagate as unhandled exceptions to callers unless the caller needs to
    know (e.g., critical write failures).
  - Functions are fully type-annotated.
  - We log using structured key=value style for easy parsing.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .choices import EngagementTier, SessionStatus
from .constants import (
    CACHE_KEY_ENGAGEMENT_SCORE,
    CACHE_TTL_ENGAGEMENT,
    ENGAGEMENT_SCORE_MAX,
    ENGAGEMENT_SCORE_MIN,
    ENGAGEMENT_TIER_HIGH,
    ENGAGEMENT_TIER_LOW,
    ENGAGEMENT_TIER_MEDIUM,
    MAX_CLICK_METRICS_PER_SESSION,
    WEIGHT_CLICK_COUNT,
    WEIGHT_PATH_DEPTH,
    WEIGHT_RETURN_VISITS,
    WEIGHT_STAY_TIME,
)
from .exceptions import (
    AnalyticsStorageError,
    DuplicateSessionError,
    EngagementCalculationError,
    InvalidClickMetricError,
    InvalidPathDataError,
    SessionNotFoundError,
)
from .models import ClickMetric, EngagementScore, StayTime, UserPath

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# UserPath Service
# =============================================================================

class UserPathService:
    """Handles creation, update, and closure of UserPath sessions."""

    @staticmethod
    @transaction.atomic
    def create_path(
        *,
        user: Any,
        session_id: str,
        device_type: str,
        entry_url: str = "",
        nodes: list | None = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> UserPath:
        """
        Create a new UserPath for a user-session.

        Raises:
            DuplicateSessionError: if (user, session_id) already exists.
            AnalyticsStorageError: on unexpected DB failure.
        """
        nodes = nodes or []
        try:
            path = UserPath(
                user=user,
                session_id=session_id,
                device_type=device_type,
                entry_url=entry_url,
                nodes=nodes,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            path.full_clean()
            path.save()
            logger.info(
                "user_path.created session_id=%s user_id=%s",
                session_id, user.pk,
            )
            return path
        except IntegrityError as exc:
            if "unique_user_session_path" in str(exc):
                raise DuplicateSessionError() from exc
            logger.exception("user_path.create_db_error user_id=%s", user.pk)
            raise AnalyticsStorageError() from exc

    @staticmethod
    @transaction.atomic
    def append_nodes(
        *,
        path: UserPath,
        new_nodes: list[dict],
    ) -> UserPath:
        """
        Append multiple nodes to an existing path atomically.

        Raises:
            InvalidPathDataError: if the combined node count would exceed limit.
        """
        for node in new_nodes:
            if not isinstance(node, dict):
                raise InvalidPathDataError("Each node must be a JSON object.")
            path.add_node(
                url=node.get("url", ""),
                node_type=node.get("type", "navigation"),
                ts=node.get("ts"),
            )
        path.full_clean()
        path.save(update_fields=["nodes", "updated_at"])
        logger.debug(
            "user_path.nodes_appended session_id=%s count=%d",
            path.session_id, len(new_nodes),
        )
        return path

    @staticmethod
    @transaction.atomic
    def close_path(
        *,
        path: UserPath,
        exit_url: str = "",
        status: str = SessionStatus.COMPLETED,
    ) -> UserPath:
        """Mark a path as closed with the given final status."""
        path.exit_url = exit_url
        path.status   = status
        path.full_clean()
        path.save(update_fields=["exit_url", "status", "updated_at"])
        logger.info(
            "user_path.closed session_id=%s status=%s",
            path.session_id, status,
        )
        return path

    @staticmethod
    def get_or_404(*, user: Any, session_id: str) -> UserPath:
        """
        Retrieve a UserPath by user + session_id.

        Raises:
            SessionNotFoundError: if not found.
        """
        try:
            return UserPath.objects.select_full().get(
                user=user, session_id=session_id
            )
        except UserPath.DoesNotExist:
            raise SessionNotFoundError()


# =============================================================================
# ClickMetric Service
# =============================================================================

class ClickMetricService:
    """Handles recording and batch-processing of click events."""

    @staticmethod
    @transaction.atomic
    def record_click(
        *,
        path: UserPath,
        page_url: str,
        element_selector: str = "",
        element_text: str = "",
        category: str = "other",
        clicked_at: Any = None,
        x_position: int | None = None,
        y_position: int | None = None,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        metadata: dict | None = None,
    ) -> ClickMetric:
        """
        Record a single click event.

        Raises:
            InvalidClickMetricError: if the per-session click limit is hit.
            AnalyticsStorageError: on unexpected DB failure.
        """
        current_count = ClickMetric.objects.for_path(path).count()
        if current_count >= MAX_CLICK_METRICS_PER_SESSION:
            raise InvalidClickMetricError(
                f"Click limit ({MAX_CLICK_METRICS_PER_SESSION}) reached for session."
            )

        if clicked_at is None:
            clicked_at = timezone.now()

        try:
            metric = ClickMetric.objects.create(
                path=path,
                page_url=page_url,
                element_selector=element_selector,
                element_text=element_text,
                category=category,
                clicked_at=clicked_at,
                x_position=x_position,
                y_position=y_position,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                metadata=metadata or {},
            )
            logger.debug(
                "click_metric.recorded path_id=%s category=%s",
                path.pk, category,
            )
            return metric
        except Exception as exc:
            logger.exception("click_metric.record_error path_id=%s", path.pk)
            raise AnalyticsStorageError() from exc

    @staticmethod
    @transaction.atomic
    def bulk_record(
        *,
        path: UserPath,
        events: list[dict],
    ) -> list[ClickMetric]:
        """
        Bulk-insert a list of click event dicts.

        Returns the list of created ClickMetric instances.
        Raises:
            InvalidClickMetricError: if the combined count would exceed limit.
        """
        if not events:
            return []

        current_count = ClickMetric.objects.for_path(path).count()
        if current_count + len(events) > MAX_CLICK_METRICS_PER_SESSION:
            raise InvalidClickMetricError(
                f"Bulk insert would exceed click limit "
                f"({MAX_CLICK_METRICS_PER_SESSION}) for session."
            )

        now = timezone.now()
        instances = [
            ClickMetric(
                path=path,
                page_url=ev.get("page_url", ""),
                element_selector=ev.get("element_selector", ""),
                element_text=ev.get("element_text", ""),
                category=ev.get("category", "other"),
                clicked_at=ev.get("clicked_at") or now,
                x_position=ev.get("x_position"),
                y_position=ev.get("y_position"),
                viewport_width=ev.get("viewport_width"),
                viewport_height=ev.get("viewport_height"),
                metadata=ev.get("metadata") or {},
            )
            for ev in events
        ]
        try:
            created = ClickMetric.objects.bulk_create(instances, batch_size=500)
            logger.info(
                "click_metric.bulk_created path_id=%s count=%d",
                path.pk, len(created),
            )
            return created
        except Exception as exc:
            logger.exception("click_metric.bulk_create_error path_id=%s", path.pk)
            raise AnalyticsStorageError() from exc


# =============================================================================
# StayTime Service
# =============================================================================

class StayTimeService:
    """Records and queries page-level dwell times."""

    @staticmethod
    @transaction.atomic
    def record(
        *,
        path: UserPath,
        page_url: str,
        duration_seconds: int,
        is_active_time: bool = True,
        scroll_depth_percent: int | None = None,
    ) -> StayTime:
        """
        Persist a single StayTime record.

        Raises:
            AnalyticsStorageError: on unexpected DB failure.
        """
        try:
            st = StayTime(
                path=path,
                page_url=page_url,
                duration_seconds=duration_seconds,
                is_active_time=is_active_time,
                scroll_depth_percent=scroll_depth_percent,
            )
            st.full_clean()
            st.save()
            logger.debug(
                "stay_time.recorded path_id=%s duration=%ds",
                path.pk, duration_seconds,
            )
            return st
        except Exception as exc:
            if isinstance(exc, (StayTime.DoesNotExist,)):
                raise
            logger.exception("stay_time.record_error path_id=%s", path.pk)
            raise AnalyticsStorageError() from exc


# =============================================================================
# Engagement Score Service
# =============================================================================

def _determine_tier(score: Decimal) -> str:
    """Map a numeric score to its EngagementTier choice value."""
    if score >= ENGAGEMENT_TIER_HIGH:
        return EngagementTier.ELITE
    if score >= ENGAGEMENT_TIER_MEDIUM:
        return EngagementTier.HIGH
    if score >= ENGAGEMENT_TIER_LOW:
        return EngagementTier.MEDIUM
    return EngagementTier.LOW


class EngagementScoreService:
    """Calculates and persists daily engagement scores for users."""

    @staticmethod
    def calculate_for_user(
        *,
        user: Any,
        target_date: date | None = None,
    ) -> EngagementScore:
        """
        Calculate (or recalculate) the engagement score for `user` on
        `target_date` (defaults to today).

        The score is computed from raw analytics data, persisted via
        update_or_create, and the result cached.

        Raises:
            EngagementCalculationError: if there is insufficient data.
            AnalyticsStorageError: on DB failure.
        """
        if target_date is None:
            target_date = timezone.localdate()

        start_dt = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        end_dt = start_dt + timedelta(days=1)

        # ------------------------------------------------------------------
        # Gather raw metrics
        # ------------------------------------------------------------------
        paths = UserPath.objects.for_user(user).filter(
            created_at__range=(start_dt, end_dt)
        )

        click_count = ClickMetric.objects.filter(
            path__in=paths,
            clicked_at__range=(start_dt, end_dt),
        ).count()

        stay_agg = StayTime.objects.filter(
            path__in=paths,
        ).active_only().aggregate_stats()
        total_stay_sec: int = stay_agg["total_duration"] or 0

        path_depth: int = max(
            (p.depth for p in paths),
            default=0,
        )

        return_visits: int = paths.count()

        # ------------------------------------------------------------------
        # Compute weighted score
        # ------------------------------------------------------------------
        try:
            score, breakdown = _compute_score(
                click_count=click_count,
                total_stay_sec=total_stay_sec,
                path_depth=path_depth,
                return_visits=return_visits,
            )
        except Exception as exc:
            logger.exception(
                "engagement_score.calculation_error user_id=%s date=%s",
                user.pk, target_date,
            )
            raise EngagementCalculationError() from exc

        tier = _determine_tier(score)

        # ------------------------------------------------------------------
        # Persist
        # ------------------------------------------------------------------
        try:
            eng_score, created = EngagementScore.objects.update_or_create(
                user=user,
                date=target_date,
                defaults=dict(
                    score=score,
                    tier=tier,
                    click_count=click_count,
                    total_stay_sec=total_stay_sec,
                    path_depth=path_depth,
                    return_visits=return_visits,
                    breakdown_json=breakdown,
                ),
            )
        except Exception as exc:
            logger.exception(
                "engagement_score.persist_error user_id=%s date=%s",
                user.pk, target_date,
            )
            raise AnalyticsStorageError() from exc

        # ------------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------------
        cache_key = CACHE_KEY_ENGAGEMENT_SCORE.format(user_id=user.pk)
        try:
            cache.set(cache_key, float(score), CACHE_TTL_ENGAGEMENT)
        except Exception:  # cache failure is non-critical
            logger.warning(
                "engagement_score.cache_set_failed user_id=%s", user.pk
            )

        action = "created" if created else "updated"
        logger.info(
            "engagement_score.%s user_id=%s date=%s score=%s tier=%s",
            action, user.pk, target_date, score, tier,
        )
        return eng_score


def _compute_score(
    *,
    click_count: int,
    total_stay_sec: int,
    path_depth: int,
    return_visits: int,
) -> tuple[Decimal, dict]:
    """
    Pure function: maps raw metrics to a [0, 100] Decimal score.
    Returns (score, breakdown_dict).

    Normalisation strategy (simple linear caps):
      - clicks:      100 clicks  → full contribution
      - stay:        3600 s      → full contribution
      - depth:       20 pages    → full contribution
      - return:      10 visits   → full contribution
    """
    TWO_DP = Decimal("0.01")

    click_norm   = Decimal(min(click_count,   100)) / 100
    stay_norm    = Decimal(min(total_stay_sec, 3600)) / 3600
    depth_norm   = Decimal(min(path_depth,    20)) / 20
    return_norm  = Decimal(min(return_visits, 10)) / 10

    raw = (
        click_norm  * WEIGHT_CLICK_COUNT
        + stay_norm   * WEIGHT_STAY_TIME
        + depth_norm  * WEIGHT_PATH_DEPTH
        + return_norm * WEIGHT_RETURN_VISITS
    ) * 100

    score = max(
        Decimal(str(ENGAGEMENT_SCORE_MIN)),
        min(Decimal(str(ENGAGEMENT_SCORE_MAX)), raw.quantize(TWO_DP, ROUND_HALF_UP)),
    )

    breakdown = {
        "click_contribution":   float((click_norm  * WEIGHT_CLICK_COUNT  * 100).quantize(TWO_DP)),
        "stay_contribution":    float((stay_norm    * WEIGHT_STAY_TIME    * 100).quantize(TWO_DP)),
        "depth_contribution":   float((depth_norm   * WEIGHT_PATH_DEPTH   * 100).quantize(TWO_DP)),
        "return_contribution":  float((return_norm  * WEIGHT_RETURN_VISITS * 100).quantize(TWO_DP)),
    }

    return score, breakdown
