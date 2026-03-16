# =============================================================================
# version_control/tasks.py
# =============================================================================
"""
Celery tasks for the version_control application.

Tasks:
  - check_updates                     : one-off check for a single client
  - schedule_maintenance_notification : send push notification before maintenance
  - end_maintenance                   : auto-end a maintenance window at scheduled_end
  - cleanup_old_policies              : archive old inactive policies
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone

from .constants import (
    TASK_CHECK_UPDATES,
    TASK_CLEANUP_OLD_POLICIES,
    TASK_END_MAINTENANCE,
    TASK_SCHEDULE_MAINTENANCE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# check_updates
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CHECK_UPDATES,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def check_updates(
    self,
    platform: str,
    client_version: str,
) -> dict[str, Any]:
    """
    Async version-check — useful when check results need to be stored
    or forwarded (e.g. via WebSocket push).
    """
    from .services import VersionCheckService
    try:
        result = VersionCheckService.check(
            platform=platform, client_version=client_version
        )
        logger.info(
            "check_updates platform=%s version=%s update_required=%s",
            platform, client_version, result.get("update_required"),
        )
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception(
            "check_updates.error platform=%s version=%s attempt=%d",
            platform, client_version, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# schedule_maintenance_notification
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_SCHEDULE_MAINTENANCE,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def schedule_maintenance_notification(
    self,
    schedule_id: str,
) -> dict[str, Any]:
    """
    Send advance push notifications to affected platforms before a
    maintenance window starts.

    This task is typically scheduled by a Celery beat entry or by
    the MaintenanceService at creation time, timed to fire
    MAINTENANCE_WARNING_ADVANCE_MINUTES before scheduled_start.
    """
    from .models import MaintenanceSchedule
    from .choices import MaintenanceStatus

    try:
        schedule = MaintenanceSchedule.objects.get(pk=schedule_id)
    except MaintenanceSchedule.DoesNotExist:
        logger.error(
            "maintenance_notification.schedule_not_found pk=%s", schedule_id
        )
        return {"status": "error", "reason": "schedule_not_found"}

    if schedule.status != MaintenanceStatus.SCHEDULED:
        logger.info(
            "maintenance_notification.skipped pk=%s status=%s",
            schedule_id, schedule.status,
        )
        return {"status": "skipped", "reason": f"status is {schedule.status}"}

    if not schedule.notify_users:
        return {"status": "skipped", "reason": "notify_users=False"}

    try:
        # Placeholder: replace with your push notification service
        _send_maintenance_push(schedule)
        logger.info(
            "maintenance_notification.sent pk=%s platforms=%s",
            schedule_id, schedule.platforms,
        )
        return {"status": "ok", "schedule_id": str(schedule_id)}
    except Exception as exc:
        logger.exception(
            "maintenance_notification.error pk=%s attempt=%d",
            schedule_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


def _send_maintenance_push(schedule) -> None:
    """
    Stub: integrate your push notification provider here
    (FCM, APNs, OneSignal, etc.).
    """
    logger.debug(
        "_send_maintenance_push title=%r platforms=%s start=%s",
        schedule.title, schedule.platforms, schedule.scheduled_start,
    )


# =============================================================================
# end_maintenance  (auto-end at scheduled_end)
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_END_MAINTENANCE,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def end_maintenance(self, schedule_id: str) -> dict[str, Any]:
    """
    Automatically end a maintenance window at its scheduled_end time.
    Enqueued by the Celery beat scheduler or by MaintenanceService.create_schedule().
    """
    from .models import MaintenanceSchedule
    from .services import MaintenanceService
    from .choices import MaintenanceStatus

    try:
        schedule = MaintenanceSchedule.objects.get(pk=schedule_id)
    except MaintenanceSchedule.DoesNotExist:
        logger.error("end_maintenance.not_found pk=%s", schedule_id)
        return {"status": "error", "reason": "not_found"}

    if schedule.status != MaintenanceStatus.ACTIVE:
        logger.info(
            "end_maintenance.skipped pk=%s status=%s",
            schedule_id, schedule.status,
        )
        return {"status": "skipped", "reason": f"status is {schedule.status}"}

    try:
        MaintenanceService.end_maintenance(schedule)
        logger.info("end_maintenance.done pk=%s", schedule_id)
        return {"status": "ok"}
    except Exception as exc:
        logger.exception(
            "end_maintenance.error pk=%s attempt=%d",
            schedule_id, self.request.retries,
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "error", "reason": "max_retries_exceeded"}


# =============================================================================
# cleanup_old_policies
# =============================================================================

@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_POLICIES,
    max_retries=1,
    acks_late=True,
)
def cleanup_old_policies(self, days_old: int = 180) -> dict[str, Any]:
    """
    Archive AppUpdatePolicy records that have been INACTIVE for more
    than `days_old` days.  Runs monthly via Celery beat.
    """
    from .models import AppUpdatePolicy
    from .choices import PolicyStatus

    cutoff = timezone.now() - timedelta(days=days_old)
    updated = (
        AppUpdatePolicy.objects.filter(
            status=PolicyStatus.INACTIVE,
            updated_at__lt=cutoff,
        ).update(status=PolicyStatus.ARCHIVED)
    )
    logger.info(
        "cleanup_old_policies.done archived=%d cutoff=%s",
        updated, cutoff.date(),
    )
    return {"status": "ok", "archived": updated}
