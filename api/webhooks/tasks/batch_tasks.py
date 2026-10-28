"""Batch Dispatch Task

BUG FIX: BatchDispatchService.process_batch_async() imported
`process_batch` from `..tasks.batch_tasks` (wrong relative-import depth —
services/batch/ is two levels below webhooks/, so it needs three dots, not
two) AND that module did not exist at all, so every async batch dispatch
call failed with ImportError (silently swallowed, returning a "success":
False dict). This module provides the missing task; the import in
BatchDispatchService.py has been corrected to `...tasks.batch_tasks`.
"""

import logging

from celery import shared_task

from ..models import WebhookBatch
from ..services.batch.BatchDispatchService import BatchDispatchService

logger = logging.getLogger("ainul.webhooks.tasks.batch")


@shared_task(bind=True, max_retries=3, name="ainul.webhooks.process_batch")
def process_batch(self, batch_id):
    """
    Process a webhook batch (looked up by primary key).

    Args:
        batch_id: The WebhookBatch primary key (str/UUID), as queued by
                  BatchDispatchService.process_batch_async().

    Returns:
        dict: Result of the batch processing operation.
    """
    logger.info("[Task] process_batch started for batch_id=%s", batch_id)
    try:
        batch = WebhookBatch.objects.get(id=batch_id)
    except WebhookBatch.DoesNotExist:
        return {
            "batch_id": str(batch_id),
            "success": False,
            "error": "Batch not found",
        }

    try:
        service = BatchDispatchService()
        return service.process_batch(batch)
    except Exception as e:
        logger.error("Error processing batch %s: %s", batch_id, e)
        raise self.retry(exc=e, countdown=60)
