"""
Gamification Signal Receivers — Connected in GamificationConfig.ready().

All receivers are defensive: they never let an exception bubble up and kill
the calling thread. Failures are logged at ERROR level.
"""

from __future__ import annotations

import logging
from typing import Any

from django.dispatch import receiver

from .signals import (
    contest_cycle_status_changed,
    achievement_awarded,
    leaderboard_snapshot_finalized,
)

logger = logging.getLogger(__name__)


@receiver(contest_cycle_status_changed)
def on_contest_cycle_status_changed(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a ContestCycle transitions to a new status.

    On COMPLETED transition: enqueues the async reward distribution task.
    """
    from .choices import ContestCycleStatus

    cycle = kwargs.get("cycle")
    new_status = kwargs.get("new_status")
    old_status = kwargs.get("old_status")

    if cycle is None or new_status is None:
        logger.error(
            "on_contest_cycle_status_changed: received signal without 'cycle' or 'new_status'. "
            "kwargs=%r",
            kwargs,
        )
        return

    logger.info(
        "on_contest_cycle_status_changed: cycle=%s %s → %s",
        getattr(cycle, "id", "?"),
        old_status,
        new_status,
    )

    if new_status == ContestCycleStatus.COMPLETED:
        try:
            from .tasks import distribute_cycle_rewards_async
            task = distribute_cycle_rewards_async.delay(str(cycle.id))
            logger.info(
                "Enqueued distribute_cycle_rewards_async for cycle=%s task_id=%s",
                cycle.id,
                task.id,
            )
        except Exception as exc:
            # Never crash the caller — log and move on
            logger.exception(
                "Failed to enqueue distribute_cycle_rewards_async for cycle=%s: %s",
                getattr(cycle, "id", "?"),
                exc,
            )


@receiver(achievement_awarded)
def on_achievement_awarded(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a UserAchievement is formally awarded.

    Responsibilities:
    - Enqueue user notification (e.g. push notification / email).
    - Could trigger downstream point-balance update if not handled in service.
    """
    achievement = kwargs.get("achievement")
    if achievement is None:
        logger.error(
            "on_achievement_awarded: received signal without 'achievement'. kwargs=%r", kwargs
        )
        return

    logger.info(
        "on_achievement_awarded: user=%s type=%s points=%s achievement=%s",
        getattr(achievement, "user_id", "?"),
        getattr(achievement, "achievement_type", "?"),
        getattr(achievement, "points_awarded", 0),
        getattr(achievement, "id", "?"),
    )

    # Example: enqueue notification task
    # try:
    #     from notifications.tasks import send_achievement_notification
    #     send_achievement_notification.delay(str(achievement.id))
    # except Exception as exc:
    #     logger.exception("Failed to enqueue achievement notification: %s", exc)


@receiver(leaderboard_snapshot_finalized)
def on_leaderboard_snapshot_finalized(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a LeaderboardSnapshot is finalized.

    Could be used to invalidate leaderboard caches, push real-time updates, etc.
    """
    snapshot = kwargs.get("snapshot")
    if snapshot is None:
        logger.error(
            "on_leaderboard_snapshot_finalized: missing 'snapshot'. kwargs=%r", kwargs
        )
        return

    logger.info(
        "on_leaderboard_snapshot_finalized: snapshot=%s cycle=%s entries=%d",
        getattr(snapshot, "id", "?"),
        getattr(snapshot, "contest_cycle_id", "?"),
        getattr(snapshot, "entry_count", 0),
    )

    # Example: invalidate cached leaderboard
    # try:
    #     from django.core.cache import cache
    #     cache_key = f"leaderboard:{snapshot.contest_cycle_id}:{snapshot.scope}"
    #     cache.delete(cache_key)
    # except Exception as exc:
    #     logger.exception("Failed to invalidate leaderboard cache: %s", exc)
