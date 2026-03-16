"""
Messaging Signal Receivers — Connected in MessagingConfig.ready().
All receivers are defensive: never let exceptions bubble up.
"""

from __future__ import annotations

import logging
from typing import Any

from django.dispatch import receiver

from .signals import (
    chat_message_sent,
    broadcast_sent,
    support_reply_posted,
    support_thread_status_changed,
)

logger = logging.getLogger(__name__)


@receiver(chat_message_sent)
def on_chat_message_sent(sender: Any, **kwargs: Any) -> None:
    """
    After a chat message is sent:
    - Enqueue push notification for each non-sender participant.
    """
    message = kwargs.get("message")
    chat = kwargs.get("chat")

    if message is None or chat is None:
        logger.error(
            "on_chat_message_sent: missing 'message' or 'chat' in signal kwargs."
        )
        return

    try:
        from .models import ChatParticipant
        from .tasks import notify_new_chat_message
        from .consumers import _chat_group_name
        from .utils.notifier import send_websocket_event

        sender_name = _safe_display_name(message.sender)
        preview = (message.content[:100] + "...") if len(message.content) > 100 else message.content

        # Push notification to offline users (muted=False, not the sender)
        participant_ids = list(
            ChatParticipant.objects.filter(
                chat=chat,
                left_at__isnull=True,
                is_muted=False,
            ).exclude(user_id=message.sender_id).values_list("user_id", flat=True)
        )

        for uid in participant_ids:
            try:
                notify_new_chat_message.delay(
                    user_id=str(uid),
                    chat_id=str(chat.id),
                    sender_name=sender_name,
                    preview=preview,
                )
            except Exception as exc:
                logger.warning(
                    "on_chat_message_sent: failed to enqueue notification for user=%s: %s",
                    uid, exc,
                )
    except Exception as exc:
        logger.exception("on_chat_message_sent: unexpected error: %s", exc)


@receiver(broadcast_sent)
def on_broadcast_sent(sender: Any, **kwargs: Any) -> None:
    """
    After a broadcast is sent:
    - Notify the creator via in-app message.
    """
    broadcast = kwargs.get("broadcast")
    if broadcast is None:
        logger.error("on_broadcast_sent: missing 'broadcast' in kwargs.")
        return

    try:
        from .utils.notifier import notify_broadcast_sent
        notify_broadcast_sent(
            broadcast_id=broadcast.id,
            recipient_count=broadcast.recipient_count,
            delivered_count=broadcast.delivered_count,
            creator_id=broadcast.created_by_id,
        )
    except Exception as exc:
        logger.exception("on_broadcast_sent: unexpected error: %s", exc)


@receiver(support_reply_posted)
def on_support_reply_posted(sender: Any, **kwargs: Any) -> None:
    """
    After an agent posts a support reply:
    - Notify the user via push notification.
    - Send WebSocket event to the support thread room.
    """
    support_message = kwargs.get("support_message")
    thread = kwargs.get("thread")

    if support_message is None or thread is None:
        logger.error("on_support_reply_posted: missing signal kwargs.")
        return

    if not support_message.is_agent_reply or support_message.is_internal_note:
        return  # Don't notify user for their own messages or internal notes

    try:
        from .tasks import notify_support_reply
        notify_support_reply.delay(
            user_id=str(thread.user_id),
            thread_id=str(thread.id),
            subject=thread.subject,
            preview=(support_message.content[:100]),
        )
    except Exception as exc:
        logger.exception("on_support_reply_posted: failed to enqueue notification: %s", exc)


@receiver(support_thread_status_changed)
def on_support_thread_status_changed(sender: Any, **kwargs: Any) -> None:
    """Log support thread status changes for audit trail."""
    thread = kwargs.get("thread")
    old_status = kwargs.get("old_status")
    new_status = kwargs.get("new_status")

    if thread is None:
        return

    logger.info(
        "SupportThread %s status changed: %s → %s (user=%s)",
        getattr(thread, "id", "?"),
        old_status,
        new_status,
        getattr(thread, "user_id", "?"),
    )


def _safe_display_name(user: Any) -> str:
    """Safe display name from a user object."""
    if user is None:
        return "System"
    try:
        full = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full or getattr(user, "username", str(user.pk))
    except Exception:
        return str(getattr(user, "pk", "unknown"))
