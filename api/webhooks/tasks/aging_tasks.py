# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Aging Celery Tasks
tasks/aging_tasks.py

FIX APPLIED:
    - aging_full_sweep and aging_archive_due now use DistributedLock so
      concurrent workers (e.g. two beat workers after a restart) cannot
      run the same sweep simultaneously and cause double-archival.
    - aging_purge_execute lock is intentionally SHORT (20 min hard cap)
      so a stale lock can't block the next scheduled purge window.
    - Non-destructive tasks (dry_run, evaluate) are unlocked — they're safe
      to run concurrently.

Beat schedule (suggested in celery.py):
    aging_full_sweep      → every 6 hours
    aging_archive_due     → every 12 hours
    aging_purge_dry_run   → daily
    aging_purge_execute   → weekly (Sunday 02:00 UTC)
"""

import logging

from celery import shared_task
from django.utils import timezone

from ..services.analytics.AgingService import AgingService
from .distributed_lock import DistributedLock

logger = logging.getLogger("ainul.webhooks.aging")


@shared_task(
    name="webhooks.aging.full_sweep",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def aging_full_sweep():
    """
    Evaluate every endpoint and delivery log, assign age tiers,
    schedule archive/purge timestamps, send lifecycle notifications.

    Protected by DistributedLock — safe to schedule on multiple workers.
    Recommended beat: every 6 hours.
    """
    lock = DistributedLock("aging.full_sweep", timeout=600)

    if not lock.acquire(blocking=False):
        logger.info("aging_full_sweep: already running on another worker — skipping")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        logger.info("aging_full_sweep: starting at %s", timezone.now().isoformat())
        svc    = AgingService()
        result = svc.run_full_sweep()
        logger.info("aging_full_sweep: complete — %s", result)
        return result
    except Exception as exc:
        logger.exception("aging_full_sweep: unexpected error")
        raise
    finally:
        lock.release()


@shared_task(
    name="webhooks.aging.archive_due",
    max_retries=2,
    soft_time_limit=120,
    time_limit=240,
)
def aging_archive_due():
    """
    Archive all endpoint and delivery log aging records whose
    archive_after timestamp has passed.

    Protected by DistributedLock.
    Recommended beat: every 12 hours.
    """
    lock = DistributedLock("aging.archive_due", timeout=240)

    if not lock.acquire(blocking=False):
        logger.info("aging_archive_due: already running — skipping")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        logger.info("aging_archive_due: starting")
        svc    = AgingService()
        result = svc.archive_due_records()
        logger.info("aging_archive_due: complete — %s", result)
        return result
    except Exception as exc:
        logger.exception("aging_archive_due: unexpected error")
        raise
    finally:
        lock.release()


@shared_task(
    name="webhooks.aging.purge_dry_run",
    max_retries=1,
    soft_time_limit=60,
)
def aging_purge_dry_run():
    """
    Dry-run purge: count records due for deletion without deleting anything.
    Safe to run concurrently — no lock needed.

    Recommended beat: daily.
    """
    logger.info("aging_purge_dry_run: starting")
    svc    = AgingService()
    result = svc.purge_due_records(dry_run=True)
    logger.info("aging_purge_dry_run: %s records due for purge", result)
    return result


@shared_task(
    name="webhooks.aging.purge_execute",
    max_retries=0,          # Never auto-retry destructive operations
    soft_time_limit=300,
    time_limit=600,
)
def aging_purge_execute():
    """
    Execute purge: permanently delete delivery logs and mark endpoint
    aging records as purged.

    Protected by DistributedLock with a shorter timeout than the task
    itself, so a stale lock won't block the next weekly window.
    Recommended beat: weekly (e.g. Sunday 02:00 UTC).
    """
    lock = DistributedLock("aging.purge_execute", timeout=1200)   # 20-min lock max

    if not lock.acquire(blocking=False):
        logger.warning("aging_purge_execute: already running — aborting to prevent double-purge")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        logger.warning(
            "aging_purge_execute: STARTING DESTRUCTIVE PURGE at %s",
            timezone.now().isoformat(),
        )
        svc    = AgingService()
        result = svc.purge_due_records(dry_run=False)
        logger.warning("aging_purge_execute: complete — %s", result)
        return result
    except Exception as exc:
        logger.exception("aging_purge_execute: unexpected error during purge")
        raise
    finally:
        lock.release()


@shared_task(
    name="webhooks.aging.evaluate_endpoint",
    max_retries=2,
    soft_time_limit=30,
)
def aging_evaluate_endpoint(endpoint_id: str):
    """
    Evaluate one endpoint's aging on-demand.
    Triggered after rotate-secret or resume actions.
    No lock needed — single-endpoint, no overlap risk.
    """
    from ..models.core import WebhookEndpoint

    try:
        endpoint = WebhookEndpoint.objects.select_related("owner").get(pk=endpoint_id)
    except WebhookEndpoint.DoesNotExist:
        logger.warning("aging_evaluate_endpoint: endpoint %s not found", endpoint_id)
        return {"error": f"Endpoint {endpoint_id} not found"}

    svc    = AgingService()
    result = svc.evaluate_endpoint(endpoint)
    logger.info("aging_evaluate_endpoint: endpoint=%s result=%s", endpoint_id, result)
    return result
