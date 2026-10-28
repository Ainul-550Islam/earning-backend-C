# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Integration Sync Tasks
tasks/integration_sync_tasks.py  (NEW FILE)

Connects the INTEGRATION_SYSTEM (previously 19 orphaned files) into the
Celery task scheduler so enterprise sync runs automatically.

Beat schedule (add to celery.py):
    sync_all_endpoints_with_integration → every 6 hours
    sync_single_endpoint_with_integration → on-demand only

Settings required (settings.py):
    WEBHOOKS = {
        "INTEGRATION_ENABLED": True,
        "INTEGRATION_CONFIG": { ... }   # see INTEGRATION_SYSTEM docs
    }
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .distributed_lock import DistributedLock

logger = logging.getLogger("ainul.webhooks.integration")


def _integration_enabled() -> bool:
    """Check if integration system is enabled in settings."""
    cfg = getattr(settings, "WEBHOOKS", {})
    return cfg.get("INTEGRATION_ENABLED", False)


def _get_integration():
    """
    Lazy-load the integration system.

    Returns the WebhooksIntegration instance or None if disabled/unavailable.
    """
    if not _integration_enabled():
        return None
    try:
        from ..INTEGRATION_SYSTEM.webhooks_integration import WebhooksIntegration
        return WebhooksIntegration()
    except Exception as exc:
        logger.error("Failed to load WebhooksIntegration: %s", exc)
        return None


@shared_task(
    name="webhooks.integration.sync_all_endpoints",
    bind=True,
    max_retries=3,
    default_retry_delay=300,    # 5-minute retry gap
    soft_time_limit=540,
    time_limit=600,
)
def sync_all_endpoints_with_integration(self):
    """
    Sync all active webhook endpoints with the enterprise integration system.

    Protected by DistributedLock — safe across multiple workers.
    Recommended beat: every 6 hours.

    Returns:
        dict: { synced, failed, total, errors[], timestamp }
    """
    if not _integration_enabled():
        return {"status": "disabled", "message": "WEBHOOKS['INTEGRATION_ENABLED'] is False"}

    lock = DistributedLock("integration.sync_all", timeout=600)
    if not lock.acquire(blocking=False):
        logger.info("sync_all_endpoints_with_integration: already running — skipping")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        from ..models.core import WebhookEndpoint

        integ  = _get_integration()
        if integ is None:
            return {"status": "error", "message": "Integration system unavailable"}

        endpoints = WebhookEndpoint.objects.filter(status="active")
        results   = {
            "synced":    0,
            "failed":    0,
            "total":     endpoints.count(),
            "errors":    [],
            "timestamp": timezone.now().isoformat(),
        }

        for endpoint in endpoints:
            try:
                integ.sync_endpoint(endpoint)
                results["synced"] += 1
            except Exception as exc:
                results["failed"] += 1
                results["errors"].append({
                    "endpoint_id":    str(endpoint.pk),
                    "endpoint_label": endpoint.label,
                    "error":          str(exc),
                })
                logger.error("Integration sync failed for endpoint %s: %s", endpoint.pk, exc)

        # Cache last-run stats for the status API
        cache.set(
            "integ:last_sync_stats",
            {
                "timestamp":  results["timestamp"],
                "synced":     results["synced"],
                "failed":     results["failed"],
                "total":      results["total"],
            },
            timeout=7 * 24 * 3600,  # keep for a week
        )

        logger.info(
            "sync_all_endpoints_with_integration: %d/%d synced",
            results["synced"], results["total"],
        )
        return results

    except Exception as exc:
        logger.exception("sync_all_endpoints_with_integration: unexpected error")
        raise self.retry(
            exc=exc,
            countdown=min(60 * (2 ** self.request.retries), 1800),
        )
    finally:
        lock.release()


@shared_task(
    name="webhooks.integration.sync_single_endpoint",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=60,
    time_limit=90,
)
def sync_single_endpoint_with_integration(self, endpoint_id: str):
    """
    Sync a single endpoint immediately (on-demand, triggered from API).

    Args:
        endpoint_id: UUID string of the WebhookEndpoint to sync.

    Returns:
        dict: { success, endpoint_id, result }
    """
    if not _integration_enabled():
        return {"status": "disabled"}

    from ..models.core import WebhookEndpoint

    try:
        endpoint = WebhookEndpoint.objects.get(pk=endpoint_id)
    except WebhookEndpoint.DoesNotExist:
        logger.error("sync_single_endpoint: endpoint %s not found", endpoint_id)
        return {"success": False, "error": "Endpoint not found"}

    try:
        integ = _get_integration()
        if integ is None:
            return {"success": False, "error": "Integration system unavailable"}

        result = integ.sync_endpoint(endpoint)
        logger.info("sync_single_endpoint: endpoint=%s synced", endpoint_id)
        return {"success": True, "endpoint_id": endpoint_id, "result": result}

    except Exception as exc:
        logger.error("sync_single_endpoint: failed for %s — %s", endpoint_id, exc)
        raise self.retry(exc=exc, countdown=60)
