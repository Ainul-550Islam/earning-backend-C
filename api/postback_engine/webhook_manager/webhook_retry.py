"""
webhook_manager/webhook_retry.py
──────────────────────────────────
Retry logic for failed webhook deliveries.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from ..constants import MAX_WEBHOOK_RETRIES, WEBHOOK_RETRY_DELAYS
from ..models import RetryLog
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookRetry:

    def schedule(
        self,
        conversion_id: str,
        url: str,
        error: str,
        attempt: int = 1,
    ) -> bool:
        """
        Schedule a failed webhook for retry.
        Returns False if max retries exceeded.
        """
        if attempt > MAX_WEBHOOK_RETRIES:
            logger.warning("Webhook max retries exceeded: url=%s", url[:80])
            return False

        import uuid
        delay = WEBHOOK_RETRY_DELAYS[min(attempt - 1, len(WEBHOOK_RETRY_DELAYS) - 1)]
        next_retry = timezone.now() + timedelta(seconds=delay)

        RetryLog.objects.create(
            retry_type="webhook",
            object_id=uuid.UUID(conversion_id),
            attempt_number=attempt,
            succeeded=False,
            error_message=error,
            response_data={"url": url},
            next_retry_at=next_retry,
        )

        from ..tasks import send_webhook_notification
        send_webhook_notification.apply_async(
            args=[conversion_id], countdown=delay
        )
        logger.info("Webhook retry %d/%d scheduled in %ds: %s", attempt, MAX_WEBHOOK_RETRIES, delay, url[:60])
        return True


webhook_retry = WebhookRetry()
