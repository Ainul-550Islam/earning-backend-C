"""
Messaging Notifier — Push and in-app notification dispatch utilities.

All functions are defensive: they never raise exceptions to callers.
Failures are logged at ERROR level and return False.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def notify_user_new_message(
    *,
    user_id: Any,
    chat_id: Any,
    sender_name: str,
    preview: str,
) -> bool:
    """
    Send an in-app / push notification to a user about a new chat message.

    Args:
        user_id:     PK of the recipient.
        chat_id:     PK of the chat.
        sender_name: Display name of the sender.
        preview:     Short message preview.

    Returns:
        True on success, False on failure.
    """
    if user_id is None or chat_id is None:
        logger.warning(
            "notify_user_new_message: user_id or chat_id is None; skipping."
        )
        return False

    if not isinstance(preview, str):
        preview = str(preview)[:100]
    if not isinstance(sender_name, str):
        sender_name = str(sender_name)

    try:
        # Placeholder: integrate with FCM, APNs, or WebPush here.
        # Example:
        # from push_notifications.models import APNSDevice, GCMDevice
        # devices = GCMDevice.objects.filter(user_id=user_id)
        # devices.send_message(preview, title=f"New message from {sender_name}")
        logger.debug(
            "notify_user_new_message: user=%s chat=%s sender=%r preview=%r",
            user_id, chat_id, sender_name, preview[:50],
        )
        return True
    except Exception as exc:
        logger.error(
            "notify_user_new_message: failed for user=%s: %s", user_id, exc
        )
        return False


def notify_user_support_reply(
    *,
    user_id: Any,
    thread_id: Any,
    subject: str,
    preview: str,
) -> bool:
    """
    Notify a user that an agent has replied to their support thread.

    Args:
        user_id:   PK of the user.
        thread_id: PK of the SupportThread.
        subject:   Thread subject.
        preview:   Short reply preview.

    Returns:
        True on success, False on failure.
    """
    if user_id is None or thread_id is None:
        logger.warning("notify_user_support_reply: missing user_id or thread_id.")
        return False

    try:
        logger.debug(
            "notify_user_support_reply: user=%s thread=%s subject=%r",
            user_id, thread_id, subject[:50],
        )
        return True
    except Exception as exc:
        logger.error(
            "notify_user_support_reply: failed for user=%s: %s", user_id, exc
        )
        return False


def notify_broadcast_sent(
    *,
    broadcast_id: Any,
    recipient_count: int,
    delivered_count: int,
    creator_id: Optional[Any] = None,
) -> bool:
    """
    Notify the broadcast creator that their broadcast has been sent.

    Args:
        broadcast_id:    PK of the AdminBroadcast.
        recipient_count: Target audience size.
        delivered_count: Actual delivery count.
        creator_id:      PK of the admin who created the broadcast.

    Returns:
        True on success, False on failure.
    """
    if broadcast_id is None:
        logger.warning("notify_broadcast_sent: broadcast_id is None.")
        return False

    try:
        logger.info(
            "notify_broadcast_sent: broadcast=%s delivered=%d/%d creator=%s",
            broadcast_id, delivered_count, recipient_count, creator_id,
        )
        return True
    except Exception as exc:
        logger.error(
            "notify_broadcast_sent: failed for broadcast=%s: %s", broadcast_id, exc
        )
        return False


def send_websocket_event(
    *,
    group_name: str,
    event_type: str,
    payload: dict,
) -> bool:
    """
    Send an event to a Channels group via the channel layer.

    This is a synchronous wrapper — call from within a Celery task
    or Django signal receiver. For use within async consumers, call
    channel_layer.group_send() directly.

    Args:
        group_name:  Channel layer group name.
        event_type:  Event type string (e.g. "chat.message.broadcast").
        payload:     Additional event data dict.

    Returns:
        True on success, False on failure.
    """
    if not group_name or not isinstance(group_name, str):
        logger.error("send_websocket_event: invalid group_name %r.", group_name)
        return False
    if not event_type or not isinstance(event_type, str):
        logger.error("send_websocket_event: invalid event_type %r.", event_type)
        return False
    if not isinstance(payload, dict):
        logger.error("send_websocket_event: payload must be a dict.")
        return False

    try:
        from channels.layers import get_channel_layer
        import asyncio

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning(
                "send_websocket_event: no channel layer configured; skipping."
            )
            return False

        event = {"type": event_type, **payload}
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                channel_layer.group_send(group_name, event), loop
            )
            future.result(timeout=5)
        else:
            loop.run_until_complete(channel_layer.group_send(group_name, event))

        logger.debug(
            "send_websocket_event: sent type=%s to group=%s.", event_type, group_name
        )
        return True
    except Exception as exc:
        logger.error(
            "send_websocket_event: failed group=%s type=%s: %s",
            group_name, event_type, exc,
        )
        return False
