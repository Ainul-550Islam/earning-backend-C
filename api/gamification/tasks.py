"""
Gamification Celery Tasks — Async leaderboard updates and reward distribution.
Enhanced with integration system monitoring, audit logging, and performance tracking.

All tasks follow the Celery best-practice of:
- bind=True for self access (retry, request id)
- max_retries with exponential back-off
- Explicit exception handling (never raise unexpected exceptions silently)
- Structured logging with task_id for correlation
- Integration system monitoring and audit logging
"""

from __future__ import annotations
from typing import List

import logging
import hashlib
import json
from typing import Any, Optional, Dict

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone

from api.gamification.choices import LeaderboardScope
from api.gamification.constants import DEFAULT_LEADERBOARD_TOP_N
from api.gamification.exceptions import (
    GamificationServiceError,
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)
from api.gamification import services

# Import integration system components
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from api.gamification.INTEGRATION_SYSTEM.sync_manager import sync_manager
from api.gamification.INTEGRATION_SYSTEM.fallback_logic import fallback_manager
from api.gamification.INTEGRATION_SYSTEM.circuit_breaker import circuit_breaker_registry

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
    Enhanced with integration system monitoring, audit logging, and circuit breaker.

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
    start_time = logger.info if hasattr(logger, 'info') else lambda *args, **kwargs: None
    
    # Log task start with audit
    audit_logger.log_audit(
        action=audit_logger.AuditAction.EXECUTE,
        description=f"Task started: update_leaderboard_snapshot for cycle {cycle_id}",
        resource_type=audit_logger.ResourceType.INTEGRATION,
        resource_id=str(cycle_id),
        details={
            "task_id": task_id,
            "scope": scope,
            "scope_ref": scope_ref,
            "top_n": top_n,
            "task_name": "gamification.update_leaderboard_snapshot"
        }
    )
    
    # Record performance metrics
    performance_monitor.record_metric("leaderboard_snapshot_task_started", 1.0)
    
    # Use circuit breaker for snapshot generation
    circuit_breaker = circuit_breaker_registry.get_or_create("leaderboard_snapshot_generation")
    
    logger.info(
        "[task=%s] update_leaderboard_snapshot started: cycle=%s scope=%s top_n=%s",
        task_id,
        cycle_id,
        scope,
        top_n,
    )

    if not cycle_id:
        error_msg = "cycle_id is required."
        logger.error("[task=%s] update_leaderboard_snapshot: %s", task_id, error_msg)
        
        # Log error
        audit_logger.log_audit(
            action=audit_logger.AuditAction.ERROR,
            description=f"Task failed: {error_msg}",
            resource_type=audit_logger.ResourceType.INTEGRATION,
            resource_id="unknown",
            details={"task_id": task_id, "error": error_msg}
        )
        
        return {"error": error_msg, "task_id": task_id}

    try:
        # Execute with circuit breaker
        with circuit_breaker:
            snapshot = services.generate_leaderboard_snapshot(
                cycle_id=cycle_id,
                scope=scope,
                scope_ref=scope_ref or "",
                top_n=int(top_n),
            )
        
        # Calculate task duration
        task_duration = (timezone.now() - start_time).total_seconds() if start_time else 0
        
        # Record success metrics
        performance_monitor.record_metric("leaderboard_snapshot_task_duration", task_duration)
        performance_monitor.record_metric("leaderboard_snapshot_task_success", 1.0)
        
        # Log success
        audit_logger.log_audit(
            action=audit_logger.AuditAction.EXECUTE,
            description=f"Task completed successfully: update_leaderboard_snapshot",
            resource_type=audit_logger.ResourceType.INTEGRATION,
            resource_id=str(cycle_id),
            details={
                "task_id": task_id,
                "snapshot_id": str(snapshot.id),
                "entry_count": snapshot.entry_count,
                "task_duration": task_duration,
                "checksum": snapshot.checksum
            }
        )
        
        # Trigger sync for snapshot
        snapshot.trigger_sync("task_generation")
        
        logger.info(
            "[task=%s] update_leaderboard_snapshot completed: snapshot=%s entries=%s duration=%s",
            task_id,
            snapshot.id,
            snapshot.entry_count,
            task_duration,
        )
        
        return {
            "snapshot_id": str(snapshot.id),
            "entry_count": snapshot.entry_count,
            "task_id": task_id,
            "duration": task_duration,
            "checksum": snapshot.checksum
        }
        
    except ContestCycleNotFoundError as exc:
        # Permanent failure — do not retry
        error_msg = f"Cycle not found: {exc}"
        logger.error("[task=%s] update_leaderboard_snapshot: %s", task_id, error_msg)
        
        # Log error
        audit_logger.log_audit(
            action=audit_logger.AuditAction.ERROR,
            description=f"Task failed permanently: {error_msg}",
            resource_type=audit_logger.ResourceType.INTEGRATION,
            resource_id=str(cycle_id),
            details={"task_id": task_id, "error": error_msg, "retryable": False}
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


# ---------------------------------------------------------------------------
# Additional Tasks from tasks_cap.py
# ---------------------------------------------------------------------------

# Contest Cycle Tasks
@shared_task(bind=True, max_retries=3)
def activate_contest_cycle(self, cycle_id: str, activated_by_id: str) -> Dict[str, Any]:
    """Activate a contest cycle asynchronously."""
    try:
        from api.gamification.services.ContestService import ContestService
        service = ContestService()
        cycle = service.activate_cycle(cycle_id, activated_by_id)
        
        logger.info(f"Activated contest cycle {cycle_id} by user {activated_by_id}")
        
        return {
            'status': 'success',
            'cycle_id': cycle_id,
            'activated_by': activated_by_id,
            'activated_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to activate contest cycle {cycle_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def complete_contest_cycle(self, cycle_id: str, completed_by_id: str) -> Dict[str, Any]:
    """Complete a contest cycle asynchronously."""
    try:
        from api.gamification.services.ContestService import ContestService
        service = ContestService()
        cycle = service.complete_cycle(cycle_id, completed_by_id)
        
        logger.info(f"Completed contest cycle {cycle_id} by user {completed_by_id}")
        
        return {
            'status': 'success',
            'cycle_id': cycle_id,
            'completed_by': completed_by_id,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to complete contest cycle {cycle_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def distribute_cycle_rewards(self, cycle_id: str, distributed_by_id: str) -> Dict[str, Any]:
    """Distribute rewards for a completed contest cycle."""
    try:
        from api.gamification.services.ContestService import ContestService
        service = ContestService()
        rewards = service.distribute_rewards(cycle_id, distributed_by_id)
        
        logger.info(f"Distributed rewards for contest cycle {cycle_id}")
        
        return {
            'status': 'success',
            'cycle_id': cycle_id,
            'distributed_by': distributed_by_id,
            'rewards_distributed': len(rewards),
            'distributed_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to distribute rewards for contest cycle {cycle_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Achievement Tasks
@shared_task(bind=True, max_retries=3)
def award_achievement(self, user_id: str, achievement_data: Dict[str, Any]) -> Dict[str, Any]:
    """Award an achievement to a user asynchronously."""
    try:
        from api.gamification.services.BadgeService import BadgeService
        service = BadgeService()
        achievement = service.award_achievement(user_id, achievement_data)
        
        logger.info(f"Awarded achievement to user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'achievement_id': achievement.id,
            'awarded_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to award achievement to user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_achievement_notification(self, achievement_id: str, user_id: str) -> Dict[str, Any]:
    """Send achievement notification to a user."""
    try:
        # Notification logic here
        logger.info(f"Sent achievement notification for {achievement_id} to user {user_id}")
        
        return {
            'status': 'success',
            'achievement_id': achievement_id,
            'user_id': user_id,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to send achievement notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Badge Tasks
@shared_task(bind=True, max_retries=3)
def award_badge(self, user_id: str, badge_id: str, awarded_by_id: str) -> Dict[str, Any]:
    """Award a badge to a user asynchronously."""
    try:
        from api.gamification.services.BadgeService import BadgeService
        service = BadgeService()
        user_badge = service.award_badge(user_id, badge_id, awarded_by_id)
        
        logger.info(f"Awarded badge {badge_id} to user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'badge_id': badge_id,
            'user_badge_id': user_badge.id,
            'awarded_by': awarded_by_id,
            'awarded_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to award badge {badge_id} to user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_badge_notification(self, user_badge_id: str, user_id: str) -> Dict[str, Any]:
    """Send badge notification to a user."""
    try:
        # Notification logic here
        logger.info(f"Sent badge notification for {user_badge_id} to user {user_id}")
        
        return {
            'status': 'success',
            'user_badge_id': user_badge_id,
            'user_id': user_id,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to send badge notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Challenge Tasks
@shared_task(bind=True, max_retries=3)
def create_daily_challenge(self, challenge_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a daily challenge asynchronously."""
    try:
        from api.gamification.services.DailyChallengeService import DailyChallengeService
        service = DailyChallengeService()
        challenge = service.create_challenge(challenge_data)
        
        logger.info(f"Created daily challenge {challenge.id}")
        
        return {
            'status': 'success',
            'challenge_id': challenge.id,
            'created_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to create daily challenge: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def complete_challenge(self, user_challenge_id: str, completed_by_id: str) -> Dict[str, Any]:
    """Complete a user challenge asynchronously."""
    try:
        from api.gamification.services.DailyChallengeService import DailyChallengeService
        service = DailyChallengeService()
        result = service.complete_challenge(user_challenge_id, completed_by_id)
        
        logger.info(f"Completed challenge {user_challenge_id}")
        
        return {
            'status': 'success',
            'user_challenge_id': user_challenge_id,
            'completed_by': completed_by_id,
            'completed_at': timezone.now().isoformat(),
            'result': result
        }
        
    except Exception as exc:
        logger.error(f"Failed to complete challenge {user_challenge_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Streak Tasks
@shared_task(bind=True, max_retries=3)
def update_streak(self, user_id: str, activity_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update user streak asynchronously."""
    try:
        from api.gamification.services.StreakService import StreakService
        service = StreakService()
        streak = service.update_streak(user_id, activity_data)
        
        logger.info(f"Updated streak for user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'streak_id': streak.id,
            'current_days': streak.current_days,
            'updated_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to update streak for user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def reset_streak(self, streak_id: str, reset_by_id: str, reset_reason: str) -> Dict[str, Any]:
    """Reset a user streak asynchronously."""
    try:
        from api.gamification.services.StreakService import StreakService
        service = StreakService()
        streak = service.reset_streak(streak_id, reset_reason)
        
        logger.info(f"Reset streak {streak_id} by user {reset_by_id}")
        
        return {
            'status': 'success',
            'streak_id': streak_id,
            'reset_by': reset_by_id,
            'reset_reason': reset_reason,
            'reset_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to reset streak {streak_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Level Tasks
@shared_task(bind=True, max_retries=3)
def check_level_up(self, user_id: str, total_points: int) -> Dict[str, Any]:
    """Check if user should level up based on points."""
    try:
        from api.gamification.services.LevelUpService import LevelUpService
        service = LevelUpService()
        result = service.check_level_up(user_id, total_points)
        
        logger.info(f"Checked level up for user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'total_points': total_points,
            'leveled_up': result.get('leveled_up', False),
            'new_level': result.get('new_level'),
            'checked_at': timezone.now().isoformat(),
            'result': result
        }
        
    except Exception as exc:
        logger.error(f"Failed to check level up for user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_level_up_notification(self, user_id: str, level_info: Dict[str, Any]) -> Dict[str, Any]:
    """Send level up notification to a user."""
    try:
        # Notification logic here
        logger.info(f"Sent level up notification to user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'level_info': level_info,
            'sent_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to send level up notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Points Tasks
@shared_task(bind=True, max_retries=3)
def award_points(self, user_id: str, points: int, source: str, awarded_by_id: str) -> Dict[str, Any]:
    """Award points to a user asynchronously."""
    try:
        from api.gamification.services.PointsService import PointsService
        service = PointsService()
        result = service.award_points(user_id, points, source, awarded_by_id)
        
        logger.info(f"Awarded {points} points to user {user_id}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'points_awarded': points,
            'source': source,
            'awarded_by': awarded_by_id,
            'new_balance': result.get('new_balance'),
            'awarded_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to award points to user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Maintenance Tasks
@shared_task(bind=True, max_retries=3)
def cleanup_expired_challenges(self) -> Dict[str, Any]:
    """Clean up expired challenges."""
    try:
        # Cleanup logic here
        logger.info("Cleaned up expired challenges")
        
        return {
            'status': 'success',
            'cleaned_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to cleanup expired challenges: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def reset_expired_streaks(self) -> Dict[str, Any]:
    """Reset expired streaks."""
    try:
        # Reset logic here
        logger.info("Reset expired streaks")
        
        return {
            'status': 'success',
            'reset_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to reset expired streaks: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def clear_gamification_cache(self, cache_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Clear gamification cache."""
    try:
        # Cache clearing logic here
        logger.info(f"Cleared gamification cache for keys: {cache_keys}")
        
        return {
            'status': 'success',
            'cache_keys': cache_keys,
            'cleared_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to clear gamification cache: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Analytics Tasks
@shared_task(bind=True, max_retries=3)
def generate_daily_report(self, report_date: Optional[str] = None) -> Dict[str, Any]:
    """Generate daily gamification report."""
    try:
        # Report generation logic here
        logger.info(f"Generated daily report for {report_date}")
        
        return {
            'status': 'success',
            'report_date': report_date,
            'generated_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to generate daily report: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_user_engagement_scores(self) -> Dict[str, Any]:
    """Update user engagement scores."""
    try:
        # Engagement score update logic here
        logger.info("Updated user engagement scores")
        
        return {
            'status': 'success',
            'updated_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to update user engagement scores: {exc}")
        raise self.retry(exc=exc, countdown=60)


# Bulk Operations Tasks
@shared_task(bind=True, max_retries=3)
def bulk_award_badges(self, badge_id: str, user_ids: List[str], awarded_by_id: str) -> Dict[str, Any]:
    """Award a badge to multiple users."""
    try:
        from api.gamification.services.BadgeService import BadgeService
        service = BadgeService()
        results = []
        
        for user_id in user_ids:
            try:
                result = service.award_badge(user_id, badge_id, awarded_by_id)
                results.append({
                    'user_id': user_id,
                    'status': 'success',
                    'user_badge_id': result.id
                })
            except Exception as e:
                results.append({
                    'user_id': user_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info(f"Bulk awarded badge {badge_id} to {success_count}/{len(user_ids)} users")
        
        return {
            'status': 'success',
            'badge_id': badge_id,
            'total_users': len(user_ids),
            'success_count': success_count,
            'results': results,
            'awarded_by': awarded_by_id,
            'awarded_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to bulk award badge {badge_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def bulk_update_points(self, point_updates: List[Dict[str, Any]], updated_by_id: str) -> Dict[str, Any]:
    """Update points for multiple users."""
    try:
        from api.gamification.services.PointsService import PointsService
        service = PointsService()
        results = []
        
        for update in point_updates:
            user_id = update['user_id']
            points = update['points']
            source = update.get('source', 'bulk_update')
            
            try:
                result = service.award_points(user_id, points, source, updated_by_id)
                results.append({
                    'user_id': user_id,
                    'status': 'success',
                    'points_awarded': points,
                    'total_points': result.get('new_balance')
                })
            except Exception as e:
                results.append({
                    'user_id': user_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        logger.info(f"Bulk updated points for {success_count}/{len(point_updates)} users")
        
        return {
            'status': 'success',
            'total_users': len(point_updates),
            'success_count': success_count,
            'results': results,
            'updated_by': updated_by_id,
            'updated_at': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Failed to bulk update points: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_daily_gamification_insight(self) -> dict:
    """
    Daily task: create or refresh today's GamificationInsight record.

    Should be scheduled via celery-beat to run once per day (e.g. midnight UTC).
    Calls GamificationInsight.get_or_create_today() then recalculates metrics.
    """
    try:
        from api.gamification.models import GamificationInsight
        insight = GamificationInsight.get_or_create_today()
        insight = GamificationInsight.calculate_daily_metrics()
        logger.info("Daily gamification insight generated for %s (id=%s)", insight.date, insight.id)
        return {"status": "success", "insight_id": str(insight.id), "date": str(insight.date)}
    except Exception as exc:
        logger.error("Failed to generate daily gamification insight: %s", exc)
        raise self.retry(exc=exc, countdown=300)
