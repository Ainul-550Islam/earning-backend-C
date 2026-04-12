"""
Messaging Notifier — World-class push notification dispatch.
Supports FCM (Android), APNs (iOS), WebPush, Expo, and WebSocket events.
All functions are defensive — never raise exceptions to callers.
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
    if user_id is None or chat_id is None:
        logger.warning("notify_user_new_message: user_id or chat_id is None; skipping.")
        return False
    if not isinstance(preview, str):
        preview = str(preview)[:100]
    if not isinstance(sender_name, str):
        sender_name = str(sender_name)
    try:
        return _send_push_to_user(
            user_id=user_id,
            title=f"New message from {sender_name}",
            body=preview[:80],
            data={"type": "chat_message", "chat_id": str(chat_id)},
        )
    except Exception as exc:
        logger.error("notify_user_new_message: failed for user=%s: %s", user_id, exc)
        return False


def notify_user_support_reply(
    *,
    user_id: Any,
    thread_id: Any,
    preview: str,
) -> bool:
    if user_id is None:
        return False
    try:
        return _send_push_to_user(
            user_id=user_id,
            title="Support team replied",
            body=(preview or "")[:80],
            data={"type": "support_reply", "thread_id": str(thread_id)},
        )
    except Exception as exc:
        logger.error("notify_user_support_reply: failed for user=%s: %s", user_id, exc)
        return False


def notify_broadcast_sent(*, broadcast_id: Any, title: str) -> bool:
    """Log that a broadcast was sent (actual fan-out handled by inbox creation)."""
    logger.info("notify_broadcast_sent: broadcast_id=%s title=%r", broadcast_id, title)
    return True


def notify_incoming_call(
    *,
    user_id: Any,
    call_id: str,
    caller_name: str,
    call_type: str,
) -> bool:
    """High-priority push for incoming call. Uses 'voip' priority on APNs."""
    if user_id is None:
        return False
    try:
        return _send_push_to_user(
            user_id=user_id,
            title=f"Incoming {call_type.lower()} call",
            body=f"{caller_name} is calling...",
            data={"type": "incoming_call", "call_id": call_id, "call_type": call_type},
            priority="high",
            apns_push_type="voip",
        )
    except Exception as exc:
        logger.error("notify_incoming_call: failed for user=%s: %s", user_id, exc)
        return False


def notify_reaction(
    *,
    user_id: Any,
    reactor_name: str,
    emoji: str,
    message_preview: str,
) -> bool:
    """Notify user that someone reacted to their message."""
    if user_id is None:
        return False
    try:
        return _send_push_to_user(
            user_id=user_id,
            title=f"{reactor_name} reacted {emoji}",
            body=(message_preview or "")[:60],
            data={"type": "reaction"},
        )
    except Exception as exc:
        logger.error("notify_reaction: failed for user=%s: %s", user_id, exc)
        return False


def notify_mention(
    *,
    user_id: Any,
    mentioner_name: str,
    chat_id: str,
    preview: str,
) -> bool:
    """Notify user they were @mentioned."""
    if user_id is None:
        return False
    try:
        return _send_push_to_user(
            user_id=user_id,
            title=f"{mentioner_name} mentioned you",
            body=(preview or "")[:80],
            data={"type": "mention", "chat_id": chat_id},
        )
    except Exception as exc:
        logger.error("notify_mention: failed for user=%s: %s", user_id, exc)
        return False


def send_websocket_event(*, group_name: str, event_type: str, data: dict) -> bool:
    """
    Broadcast an event to a Django Channels group.
    Used for real-time WebSocket delivery.
    """
    if not group_name or not event_type:
        return False
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning("send_websocket_event: channel layer not configured.")
            return False
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": event_type.replace(".", "_"), "data": data},
        )
        return True
    except Exception as exc:
        logger.error("send_websocket_event: group=%s event=%s failed: %s", group_name, event_type, exc)
        return False


# ---------------------------------------------------------------------------
# Internal push dispatcher
# ---------------------------------------------------------------------------

def _send_push_to_user(
    *,
    user_id: Any,
    title: str,
    body: str,
    data: Optional[dict] = None,
    priority: str = "normal",
    apns_push_type: str = "alert",
) -> bool:
    """
    Dispatch push notification to ALL active device tokens for a user.
    Supports FCM (Android/Web), APNs (iOS), and Expo.
    """
    from .device_push import send_fcm, send_apns, send_expo_push, send_webpush
    from ..models import DeviceToken

    tokens = DeviceToken.objects.filter(user_id=user_id, is_active=True)
    if not tokens.exists():
        logger.debug("_send_push_to_user: no device tokens for user=%s", user_id)
        return False

    success = False
    for token_obj in tokens:
        try:
            if token_obj.platform == "android":
                ok = send_fcm(
                    token=token_obj.token,
                    title=title,
                    body=body,
                    data=data or {},
                    priority=priority,
                )
            elif token_obj.platform == "ios":
                ok = send_apns(
                    token=token_obj.token,
                    title=title,
                    body=body,
                    data=data or {},
                    push_type=apns_push_type,
                )
            elif token_obj.platform == "web":
                ok = send_webpush(
                    subscription_info=token_obj.token,
                    title=title,
                    body=body,
                    data=data or {},
                )
            elif token_obj.platform == "expo":
                ok = send_expo_push(
                    token=token_obj.token,
                    title=title,
                    body=body,
                    data=data or {},
                )
            else:
                ok = False

            if ok:
                success = True
                from django.utils import timezone
                DeviceToken.objects.filter(pk=token_obj.pk).update(last_used_at=timezone.now())
            else:
                logger.warning("_send_push_to_user: push failed for token=%s platform=%s", token_obj.id, token_obj.platform)
        except Exception as exc:
            logger.error("_send_push_to_user: exception for token=%s: %s", token_obj.id, exc)

    return success
