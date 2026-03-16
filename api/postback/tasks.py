"""tasks.py – Celery tasks for the postback module."""
import logging
from celery import shared_task
from django.utils import timezone

from .constants import (
    MAX_POSTBACK_PROCESSING_RETRIES,
    POSTBACK_RETRY_COUNTDOWN_SECONDS,
    TASK_PROCESS_POSTBACK,
    TASK_CLEANUP_OLD_LOGS,
    TASK_RETRY_FAILED,
    POSTBACK_LOG_RETENTION_DAYS,
    DUPLICATE_LOG_RETENTION_DAYS,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name=TASK_PROCESS_POSTBACK,
    max_retries=MAX_POSTBACK_PROCESSING_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_postback(
    self,
    log_id: str,
    *,
    signature: str,
    timestamp_str: str,
    nonce: str,
    body_bytes_hex: str,
    path: str,
    query_params: dict,
):
    """
    Process a postback through the full validation pipeline.
    Retries on unexpected errors with exponential back-off.
    """
    from .models import PostbackLog
    from .services import process_postback_sync

    try:
        log = PostbackLog.objects.select_related("network").get(pk=log_id)
    except PostbackLog.DoesNotExist:
        logger.error("[process_postback] PostbackLog %s not found – cannot process.", log_id)
        return

    try:
        process_postback_sync(
            log,
            signature=signature,
            timestamp_str=timestamp_str,
            nonce=nonce,
            body_bytes=bytes.fromhex(body_bytes_hex),
            path=path,
            query_params=query_params,
        )
    except Exception as exc:
        retry_n = self.request.retries
        if retry_n < MAX_POSTBACK_PROCESSING_RETRIES:
            countdown = POSTBACK_RETRY_COUNTDOWN_SECONDS[
                min(retry_n, len(POSTBACK_RETRY_COUNTDOWN_SECONDS) - 1)
            ]
            logger.warning(
                "[process_postback] Log %s – retry %d in %ds: %s",
                log_id, retry_n + 1, countdown, exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "[process_postback] Log %s permanently failed after %d retries: %s",
            log_id, MAX_POSTBACK_PROCESSING_RETRIES, exc,
        )


@shared_task(
    bind=True,
    name=TASK_RETRY_FAILED,
    max_retries=1,
)
def retry_failed_postbacks(self):
    """Re-queue failed postbacks that are eligible for retry."""
    from .models import PostbackLog

    retryable = PostbackLog.objects.retryable().values_list("id", flat=True)
    queued = 0
    for log_id in retryable:
        # Re-queue with empty security params – the log already has raw_payload.
        # The retry path in process_postback_sync handles this gracefully.
        process_postback.delay(
            str(log_id),
            signature="",
            timestamp_str="",
            nonce="",
            body_bytes_hex="",
            path="",
            query_params={},
        )
        queued += 1
    logger.info("[retry_failed_postbacks] Queued %d retries.", queued)
    return {"queued": queued}


@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_LOGS,
    max_retries=2,
)
def cleanup_old_logs(self):
    """
    Delete PostbackLog records beyond the retention window.
    DuplicateLeadCheck records are cleaned based on their own retention window.
    """
    from .models import PostbackLog, DuplicateLeadCheck

    log_threshold = timezone.now() - timezone.timedelta(days=POSTBACK_LOG_RETENTION_DAYS)
    dedup_threshold = timezone.now() - timezone.timedelta(days=DUPLICATE_LOG_RETENTION_DAYS)

    log_count, _ = PostbackLog.objects.filter(received_at__lt=log_threshold).delete()
    dedup_count, _ = DuplicateLeadCheck.objects.filter(first_seen_at__lt=dedup_threshold).delete()

    logger.info(
        "[cleanup_old_logs] Deleted %d postback logs and %d dedup records.",
        log_count, dedup_count,
    )
    return {"logs_deleted": log_count, "dedup_deleted": dedup_count}
