"""
Gamification Celery Tasks — Async leaderboard updates and reward distribution.

All tasks follow the Celery best-practice of:
- bind=True for self access (retry, request id)
- max_retries with exponential back-off
- Explicit exception handling (never raise unexpected exceptions silently)
- Structured logging with task_id for correlation
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from .choices import LeaderboardScope
from .constants import DEFAULT_LEADERBOARD_TOP_N
from .exceptions import (
    GamificationServiceError,
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)
from . import services

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RETRY_DELAY: int = 60          # seconds
DEFAULT_MAX_RETRIES: int = 3
BACKOFF_MULTIPLIER: int = 2            # exponential back-off


# ---------------------------------------------------------------------------
# Leaderboard Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=DEFAULT_MAX_RETRIES,
    default_retry_delay=DEFAULT_RETRY_DELAY,
    name="gamification.update_leaderboard_snapshot",
    acks_late=True,
    reject_on_worker_lost=True,
)
def update_leaderboard_snapshot(
    self,
    cycle_id: Any,
    scope: str = LeaderboardScope.GLOBAL,
    scope_ref: str = "",
    top_n: int = DEFAULT_LEADERBOARD_TOP_N,
) -> dict:
    """
    Celery task: generate or refresh a leaderboard snapshot for a ContestCycle.

    Args:
        cycle_id:  PK of the ContestCycle to snapshot.
        scope:     Leaderboard scope.
        scope_ref: Optional scope qualifier.
        top_n:     Number of top entries to include.

    Returns:
        Dict with snapshot_id and entry_count on success.

    Retries on transient errors with exponential back-off.
    Does NOT retry on ContestCycleNotFoundError (permanent failure).
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] update_leaderboard_snapshot started: cycle=%s scope=%s top_n=%s",
        task_id,
        cycle_id,
        scope,
        top_n,
    )

    if not cycle_id:
        logger.error("[task=%s] update_leaderboard_snapshot: cycle_id is required.", task_id)
        return {"error": "cycle_id is required.", "task_id": task_id}

    try:
        snapshot = services.generate_leaderboard_snapshot(
            cycle_id=cycle_id,
            scope=scope,
            scope_ref=scope_ref or "",
            top_n=int(top_n),
        )
    except ContestCycleNotFoundError as exc:
        # Permanent failure — do not retry
        logger.error(
            "[task=%s] update_leaderboard_snapshot: cycle not found: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except LeaderboardGenerationError as exc:
        # Transient failure — retry with back-off
        retry_count = self.request.retries
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] update_leaderboard_snapshot: generation error (attempt %d/%d): %s. "
            "Retrying in %ds.",
            task_id,
            retry_count + 1,
            DEFAULT_MAX_RETRIES,
            exc,
            delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            logger.error(
                "[task=%s] update_leaderboard_snapshot: max retries exceeded for cycle=%s: %s",
                task_id,
                cycle_id,
                exc,
            )
            return {"error": str(exc), "retryable": False, "max_retries_exceeded": True, "task_id": task_id}
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] update_leaderboard_snapshot: service error: %s", task_id, exc
        )
        return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] update_leaderboard_snapshot: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=DEFAULT_RETRY_DELAY)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected error: {exc}", "task_id": task_id}

    result = {
        "snapshot_id": str(snapshot.id),
        "cycle_id": str(cycle_id),
        "scope": scope,
        "entry_count": snapshot.entry_count,
        "status": snapshot.status,
        "task_id": task_id,
    }
    logger.info("[task=%s] update_leaderboard_snapshot completed: %s", task_id, result)
    return result


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="gamification.distribute_cycle_rewards_async",
    acks_late=True,
    reject_on_worker_lost=True,
)
def distribute_cycle_rewards_async(self, cycle_id: Any) -> dict:
    """
    Celery task: distribute rewards for a completed ContestCycle.

    Intended to be enqueued automatically when a cycle transitions to COMPLETED.

    Args:
        cycle_id: PK of the COMPLETED ContestCycle.

    Returns:
        Dict with awarded_count, skipped_count, and errors.
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] distribute_cycle_rewards_async started: cycle=%s",
        task_id,
        cycle_id,
    )

    if not cycle_id:
        logger.error("[task=%s] distribute_cycle_rewards_async: cycle_id is required.", task_id)
        return {"error": "cycle_id is required.", "task_id": task_id}

    try:
        result = services.distribute_cycle_rewards(cycle_id=cycle_id)
    except ContestCycleNotFoundError as exc:
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: cycle not found: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except ContestCycleStateError as exc:
        # Permanent failure — cycle is in wrong state
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: state error: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except LeaderboardGenerationError as exc:
        retry_count = self.request.retries
        delay = 120 * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] distribute_cycle_rewards_async: leaderboard error: %s. Retrying in %ds.",
            task_id, exc, delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id, "max_retries_exceeded": True}
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: service error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=120)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id, "max_retries_exceeded": True}
    except Exception as exc:
        logger.exception(
            "[task=%s] distribute_cycle_rewards_async: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=120)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    result["cycle_id"] = str(cycle_id)
    logger.info(
        "[task=%s] distribute_cycle_rewards_async completed: awarded=%d skipped=%d errors=%d",
        task_id,
        result.get("awarded_count", 0),
        result.get("skipped_count", 0),
        len(result.get("errors", [])),
    )
    return result


@shared_task(
    bind=True,
    max_retries=1,
    name="gamification.batch_award_achievements_async",
    acks_late=True,
)
def batch_award_achievements_async(
    self,
    awards: list[dict],
    cycle_id: Optional[Any] = None,
    stop_on_first_error: bool = False,
) -> dict:
    """
    Celery task: batch award achievements asynchronously.

    Args:
        awards:              List of award spec dicts.
        cycle_id:            Optional cycle scope.
        stop_on_first_error: Stop processing on first failure.

    Returns:
        Dict with succeeded count, failed list, and total.
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] batch_award_achievements_async started: %d awards cycle=%s",
        task_id,
        len(awards) if isinstance(awards, list) else "?",
        cycle_id,
    )

    if not isinstance(awards, list):
        logger.error("[task=%s] awards must be a list.", task_id)
        return {"error": "awards must be a list.", "task_id": task_id}

    if not awards:
        return {"succeeded": [], "failed": [], "total": 0, "task_id": task_id}

    try:
        result = services.batch_award_achievements(
            awards,
            cycle_id=cycle_id,
            stop_on_first_error=stop_on_first_error,
        )
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] batch_award_achievements_async: service error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] batch_award_achievements_async: unexpected error: %s", task_id, exc
        )
        return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    logger.info(
        "[task=%s] batch_award_achievements_async: succeeded=%d failed=%d",
        task_id,
        len(result.get("succeeded", [])),
        len(result.get("failed", [])),
    )
    return result
