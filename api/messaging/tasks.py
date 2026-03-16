"""
Messaging Celery Tasks — Async broadcast sending, cleanup, and notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from .exceptions import (
    BroadcastNotFoundError,
    BroadcastStateError,
    BroadcastSendError,
    MessagingError,
)

logger = logging.getLogger(__name__)

DEFAULT_RETRY_DELAY: int = 60
DEFAULT_MAX_RETRIES: int = 3
BACKOFF_MULTIPLIER: int = 2


# ---------------------------------------------------------------------------
# Broadcast Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=DEFAULT_MAX_RETRIES,
    default_retry_delay=DEFAULT_RETRY_DELAY,
    name="messaging.send_broadcast_async",
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_broadcast_async(self, broadcast_id: Any, *, actor_id: Optional[Any] = None) -> dict:
    """
    Celery task: send an AdminBroadcast asynchronously.

    Retries on transient errors. Does NOT retry on permanent failures
    (BroadcastNotFoundError, BroadcastStateError).

    Args:
        broadcast_id: PK of the AdminBroadcast.
        actor_id:     PK of the triggering user (optional, for logging).

    Returns:
        Dict with recipient_count, delivered_count, task_id.
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] send_broadcast_async started: broadcast=%s actor=%s",
        task_id, broadcast_id, actor_id,
    )

    if not broadcast_id:
        logger.error("[task=%s] send_broadcast_async: broadcast_id is required.", task_id)
        return {"error": "broadcast_id is required.", "task_id": task_id}

    try:
        from . import services
        result = services.send_broadcast(broadcast_id=broadcast_id, actor_id=actor_id)
    except BroadcastNotFoundError as exc:
        logger.error("[task=%s] send_broadcast_async: not found: %s", task_id, exc)
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except BroadcastStateError as exc:
        logger.error("[task=%s] send_broadcast_async: state error: %s", task_id, exc)
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except BroadcastSendError as exc:
        retry_count = self.request.retries
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] send_broadcast_async: send error (attempt %d/%d): %s. Retry in %ds.",
            task_id, retry_count + 1, DEFAULT_MAX_RETRIES, exc, delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            logger.error(
                "[task=%s] send_broadcast_async: max retries exceeded: %s", task_id, exc
            )
            return {"error": str(exc), "max_retries_exceeded": True, "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] send_broadcast_async: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=DEFAULT_RETRY_DELAY)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    result["broadcast_id"] = str(broadcast_id)
    logger.info(
        "[task=%s] send_broadcast_async completed: delivered=%d/%d",
        task_id,
        result.get("delivered_count", 0),
        result.get("recipient_count", 0),
    )
    return result


@shared_task(
    bind=True,
    max_retries=1,
    name="messaging.send_scheduled_broadcasts",
    acks_late=True,
)
def send_scheduled_broadcasts(self) -> dict:
    """
    Celery beat task: find all scheduled broadcasts due for sending and dispatch them.
    Intended to run every minute via Celery Beat.

    Returns:
        Dict with dispatched_count and errors.
    """
    task_id = self.request.id
    logger.info("[task=%s] send_scheduled_broadcasts started.", task_id)

    from .models import AdminBroadcast
    due = AdminBroadcast.objects.due_for_sending()

    dispatched = 0
    errors = []

    for broadcast in due:
        try:
            send_broadcast_async.delay(str(broadcast.id))
            dispatched += 1
            logger.info(
                "[task=%s] Dispatched broadcast %s for async sending.", task_id, broadcast.id
            )
        except Exception as exc:
            err = f"broadcast {broadcast.id}: {exc}"
            logger.error("[task=%s] Failed to dispatch: %s", task_id, err)
            errors.append(err)

    logger.info(
        "[task=%s] send_scheduled_broadcasts: dispatched=%d errors=%d",
        task_id, dispatched, len(errors),
    )
    return {"dispatched_count": dispatched, "errors": errors, "task_id": task_id}


# ---------------------------------------------------------------------------
# Notification Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="messaging.notify_new_chat_message",
    acks_late=True,
)
def notify_new_chat_message(
    self,
    user_id: Any,
    chat_id: Any,
    sender_name: str,
    preview: str,
) -> dict:
    """
    Celery task: send push notification for a new chat message.

    Args:
        user_id:     Recipient user PK.
        chat_id:     Source chat PK.
        sender_name: Display name of sender.
        preview:     Message preview text.
    """
    task_id = self.request.id

    if not user_id or not chat_id:
        logger.warning(
            "[task=%s] notify_new_chat_message: missing user_id or chat_id.", task_id
        )
        return {"error": "user_id and chat_id are required.", "task_id": task_id}

    try:
        from .utils.notifier import notify_user_new_message
        success = notify_user_new_message(
            user_id=user_id,
            chat_id=chat_id,
            sender_name=sender_name or "Someone",
            preview=preview or "",
        )
        return {"success": success, "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] notify_new_chat_message: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="messaging.notify_support_reply",
    acks_late=True,
)
def notify_support_reply(
    self,
    user_id: Any,
    thread_id: Any,
    subject: str,
    preview: str,
) -> dict:
    """
    Celery task: notify user of a support thread reply.
    """
    task_id = self.request.id
    try:
        from .utils.notifier import notify_user_support_reply
        success = notify_user_support_reply(
            user_id=user_id,
            thread_id=thread_id,
            subject=subject or "Support",
            preview=preview or "",
        )
        return {"success": success, "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] notify_support_reply: error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}


# ---------------------------------------------------------------------------
# Cleanup Tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=1,
    name="messaging.cleanup_old_inbox_items",
    acks_late=True,
)
def cleanup_old_inbox_items(self, days: int = 90) -> dict:
    """
    Celery beat task: delete archived inbox items older than *days* days.

    Args:
        days: Items older than this are purged (default: 90).

    Returns:
        Dict with deleted_count.
    """
    task_id = self.request.id

    if not isinstance(days, int) or days < 1:
        logger.error("[task=%s] cleanup_old_inbox_items: days must be >= 1.", task_id)
        return {"error": "days must be a positive integer.", "task_id": task_id}

    from datetime import timedelta
    from django.utils import timezone
    from .models import UserInbox

    cutoff = timezone.now() - timedelta(days=days)
    try:
        deleted, _ = UserInbox.objects.filter(
            is_archived=True, created_at__lt=cutoff
        ).delete()
        logger.info(
            "[task=%s] cleanup_old_inbox_items: deleted %d items older than %d days.",
            task_id, deleted, days,
        )
        return {"deleted_count": deleted, "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] cleanup_old_inbox_items: unexpected error: %s", task_id, exc
        )
        return {"error": str(exc), "task_id": task_id}
