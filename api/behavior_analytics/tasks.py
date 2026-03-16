# =============================================================================
# behavior_analytics/tasks.py
# =============================================================================
"""
Celery tasks for the behavior_analytics application.

Design rules:
  - All tasks are idempotent: re-running them is safe.
  - Tasks that touch the DB use transaction.atomic() inside the service layer.
  - bind=True so we have access to self for retries.
  - Max retries and backoff are configured per-task depending on criticality.
  - Tasks log structured key=value lines; never swallow exceptions silently.
  - We import models/services lazily (inside the task body) to avoid
    circular import issues at module load time in some Django configurations.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.contrib.auth import get_user_model
from django.utils import timezone

from .constants import (
    REPORT_DAILY_RETENTION_DAYS,
    REPORT_WEEKLY_RETENTION_WEEKS,
    TASK_CALCULATE_ENGAGEMENT,
    TASK_CLEANUP_OLD_PATHS,
    TASK_GENERATE_DAILY_REPORT,
    TASK_GENERATE_WEEKLY_REPORT,
    TASK_PROCESS_CLICK_BATCH,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# =============================================================================
# Engagement calculation
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CALCULATE_ENGAGEMENT,
    max_retries=3,
    default_retry_delay=60,        # 1 minute
    acks_late=True,
    reject_on_worker_lost=True,
)
def calculate_engagement_score(
    self,
    user_id: str | int,
    target_date_iso: str | None = None,
) -> dict[str, Any]:
    """
    Calculate (or recalculate) the engagement score for a single user
    on `target_date_iso` (ISO-8601 date string, e.g. '2024-03-15').
    If not provided, today is used.

    Returns a summary dict on success.
    """
    from .services import EngagementScoreService

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("calc_engagement.user_not_found user_id=%s", user_id)
        return {"status": "error", "reason": "user_not_found", "user_id": str(user_id)}

    target: date | None = None
    if target_date_iso:
        try:
            target = date.fromisoformat(target_date_iso)
        except ValueError:
            logger.error(
                "calc_engagement.invalid_date user_id=%s date=%s",
                user_id, target_date_iso,
            )
            return {"status": "error", "reason": "invalid_date"}

    try:
        score_obj = EngagementScoreService.calculate_for_user(
            user=user, target_date=target
        )
        logger.info(
            "calc_engagement.done user_id=%s date=%s score=%s",
            user_id, score_obj.date, score_obj.score,
        )
        return {
            "status":  "ok",
            "user_id": str(user_id),
            "date":    str(score_obj.date),
            "score":   float(score_obj.score),
            "tier":    score_obj.tier,
        }

    except Exception as exc:
        logger.exception(
            "calc_engagement.error user_id=%s attempt=%d",
            user_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "calc_engagement.max_retries_exceeded user_id=%s",
                user_id,
            )
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Batch engagement recalculation (e.g. daily Celery beat job)
# =============================================================================

@shared_task(
    bind=True,
    name="behavior_analytics.tasks.recalculate_all_engagement",
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def recalculate_all_engagement(self, target_date_iso: str | None = None) -> dict:
    """
    Enqueue individual engagement-score tasks for *all active users*.
    This task fans out work; it does not perform calculations itself.

    Typically scheduled via Celery beat once per day (e.g. 01:00 UTC).
    """
    target_iso = target_date_iso or timezone.localdate().isoformat()

    users = User.objects.filter(is_active=True).values_list("pk", flat=True)
    count = 0
    for uid in users:
        calculate_engagement_score.delay(str(uid), target_iso)
        count += 1

    logger.info("recalculate_all_engagement.dispatched count=%d date=%s", count, target_iso)
    return {"status": "ok", "dispatched": count, "date": target_iso}


# =============================================================================
# Click batch processing
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_PROCESS_CLICK_BATCH,
    max_retries=5,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_click_batch(
    self,
    path_id: str,
    events: list[dict],
) -> dict[str, Any]:
    """
    Bulk-persist a list of click events for the given path_id.

    This task is typically enqueued by the tracking middleware when it
    accumulates a batch of events without wanting to block the HTTP response.
    """
    from .models import UserPath
    from .services import ClickMetricService

    try:
        path = UserPath.objects.get(pk=path_id)
    except UserPath.DoesNotExist:
        logger.error("process_click_batch.path_not_found path_id=%s", path_id)
        return {"status": "error", "reason": "path_not_found"}

    try:
        created = ClickMetricService.bulk_record(path=path, events=events)
        logger.info(
            "process_click_batch.done path_id=%s count=%d",
            path_id, len(created),
        )
        return {"status": "ok", "created": len(created)}
    except Exception as exc:
        logger.exception(
            "process_click_batch.error path_id=%s attempt=%d",
            path_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Report generation
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_GENERATE_DAILY_REPORT,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def generate_daily_report(self, report_date_iso: str | None = None) -> dict:
    """
    Generate (or regenerate) the daily analytics report for `report_date_iso`.
    Defaults to yesterday so the full day's data is available.
    """
    from .reports.daily_report import DailyReportGenerator

    try:
        target = (
            date.fromisoformat(report_date_iso)
            if report_date_iso
            else timezone.localdate() - timedelta(days=1)
        )
        result = DailyReportGenerator().generate(target_date=target)
        logger.info(
            "daily_report.generated date=%s rows=%s",
            target, result.get("row_count", "?"),
        )
        return {"status": "ok", "date": str(target), **result}
    except Exception as exc:
        logger.exception(
            "daily_report.error date=%s attempt=%d",
            report_date_iso, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


@shared_task(
    bind=True,
    name=TASK_GENERATE_WEEKLY_REPORT,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def generate_weekly_report(self, week_start_iso: str | None = None) -> dict:
    """
    Generate the weekly analytics report.
    week_start_iso should be a Monday date (ISO-8601).
    Defaults to the previous ISO week.
    """
    from .reports.weekly_analytics import WeeklyReportGenerator

    try:
        if week_start_iso:
            week_start = date.fromisoformat(week_start_iso)
        else:
            today      = timezone.localdate()
            week_start = today - timedelta(days=today.weekday() + 7)

        result = WeeklyReportGenerator().generate(week_start=week_start)
        logger.info("weekly_report.generated week_start=%s", week_start)
        return {"status": "ok", "week_start": str(week_start), **result}
    except Exception as exc:
        logger.exception(
            "weekly_report.error week_start=%s attempt=%d",
            week_start_iso, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# Cleanup
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_PATHS,
    max_retries=1,
    acks_late=True,
)
def cleanup_old_paths(self) -> dict:
    """
    Delete UserPath records (and cascade: ClickMetric, StayTime) older than
    REPORT_DAILY_RETENTION_DAYS.  Runs in chunks to avoid lock contention.
    """
    from .models import UserPath

    CHUNK = 1_000
    cutoff = timezone.now() - timedelta(days=REPORT_DAILY_RETENTION_DAYS)

    total_deleted = 0
    while True:
        ids = list(
            UserPath.objects.filter(created_at__lt=cutoff)
            .values_list("pk", flat=True)[:CHUNK]
        )
        if not ids:
            break
        deleted, _ = UserPath.objects.filter(pk__in=ids).delete()
        total_deleted += deleted
        logger.info("cleanup_old_paths.chunk_deleted count=%d", deleted)

    logger.info(
        "cleanup_old_paths.done total_deleted=%d cutoff=%s",
        total_deleted, cutoff.date(),
    )
    return {"status": "ok", "total_deleted": total_deleted}
