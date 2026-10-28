"""
Multi-Device Sync — Sync messages across all user devices.
Like WhatsApp Web, Telegram multi-device, iMessage handoff.

When user logs into a new device:
1. Fetch message history (last 90 days by default)
2. Sync unread counts per chat
3. Mark device as active
4. Subscribe to all user's chat groups via WebSocket

Real-time sync:
- Every message sent to a chat is delivered to ALL connected devices of all participants
- Presence is aggregated across devices (online if ANY device is online)
"""
from __future__ import annotations
import logging
from typing import Any

from .notifier import send_websocket_event  # noqa: F401  (module-level so tests can patch it)

logger = logging.getLogger(__name__)

SYNC_DAYS_DEFAULT = 90
MAX_SYNC_MESSAGES_PER_CHAT = 100


def sync_device_on_login(user_id: Any, device_token_id: Any) -> dict:
    """
    Full sync payload for a newly connected device.
    Returns {chats, unread_counts, presence_status}.
    Called when user connects WebSocket.
    """
    from ..models import InternalChat, ChatParticipant, UserInbox, UserPresence
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=SYNC_DAYS_DEFAULT)

    # Get all user's chats
    chat_ids = list(
        ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
        .values_list("chat_id", flat=True)
    )

    # Unread counts per chat.
    # UserInbox.source_id is a generic polymorphic reference (it also backs
    # BROADCAST/SUPPORT_REPLY/SYSTEM/REACTION/MENTION/... item types with
    # source_id pointing at *those* objects, not a chat) - for CHAT_MESSAGE
    # items specifically, source_id is a ChatMessage id, not a chat id. The
    # previous version grouped by source_id and then looked results up by
    # chat.id, which never matched, so every chat's unread_count was 0.
    from django.db.models import Count, Q
    from ..choices import InboxItemType
    from ..models import ChatMessage
    unread_message_ids = list(
        UserInbox.objects.filter(
            user_id=user_id,
            item_type=InboxItemType.CHAT_MESSAGE,
            is_read=False,
            is_archived=False,
        ).values_list("source_id", flat=True)
    )
    unread_by_chat = dict(
        ChatMessage.objects.filter(id__in=unread_message_ids)
        .values("chat_id").annotate(c=Count("id")).values_list("chat_id", "c")
    )

    # Total unread across ALL inbox item types (matches the semantics of
    # delivery_manager.get_total_unread(), which is also item-type-agnostic)
    total_unread = UserInbox.objects.filter(
        user_id=user_id, is_read=False, is_archived=False,
    ).count()

    # Chat summaries (last message + participant count)
    chats_summary = []
    for chat in InternalChat.objects.filter(
        Q(last_message_at__gte=cutoff) | Q(last_message_at__isnull=True),
        id__in=chat_ids, status="ACTIVE",
    ).order_by("-last_message_at")[:50]:
        last_msg = chat.messages.filter(status__in=["SENT","DELIVERED","READ"]).order_by("-created_at").first()
        chats_summary.append({
            "chat_id": str(chat.id),
            "name": chat.name,
            "is_group": chat.is_group,
            "last_message_at": chat.last_message_at.isoformat() if chat.last_message_at else None,
            "last_message_preview": last_msg.content[:100] if last_msg else "",
            "unread_count": unread_by_chat.get(chat.id, 0),
        })

    # Update device last_seen
    from ..models import DeviceToken
    DeviceToken.objects.filter(pk=device_token_id).update(
        last_used_at=timezone.now()
    )

    logger.info("sync_device_on_login: user=%s synced %d chats unread=%d", user_id, len(chats_summary), total_unread)
    return {
        "chats": chats_summary,
        "total_unread": total_unread,
        "sync_timestamp": timezone.now().isoformat(),
    }


def get_messages_for_sync(user_id: Any, chat_id: Any, since: str = None) -> list:
    """
    Get messages for a specific chat to sync to a device.
    `since` is an ISO datetime string — returns messages after that time.
    """
    from ..models import ChatMessage, ChatParticipant, MessageStatus
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    from datetime import timedelta

    # Verify access
    if not ChatParticipant.objects.filter(
        chat_id=chat_id, user_id=user_id, left_at__isnull=True
    ).exists():
        return []

    qs = ChatMessage.objects.filter(
        chat_id=chat_id,
        status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
    ).select_related("sender").order_by("-created_at")

    if since:
        since_dt = parse_datetime(since)
        if since_dt:
            qs = qs.filter(created_at__gt=since_dt)
        else:
            # Unparseable `since` (e.g. a malformed client value) should
            # fall back to the same bounded default as "no since given",
            # not silently return the chat's entire unbounded history.
            qs = qs.filter(
                created_at__gte=timezone.now() - timedelta(days=SYNC_DAYS_DEFAULT)
            )
    else:
        qs = qs.filter(
            created_at__gte=timezone.now() - timedelta(days=SYNC_DAYS_DEFAULT)
        )

    return list(qs[:MAX_SYNC_MESSAGES_PER_CHAT])


def broadcast_to_all_user_devices(user_id: Any, event_type: str, data: dict) -> int:
    """
    Send a WebSocket event to all of a user's connected devices/sockets.
    Used for cross-device sync (e.g., message read on one device → mark read on all).
    Returns an upper-bound count of devices notified (Channels' group_send
    doesn't report per-socket delivery, so this is "active device tokens if
    the send succeeded", same as before - just no longer silently wrong).

    Bug fix (Part 6 audit): every one of a user's WS connections joins a
    single shared group - consumers._user_devices_group(user_id), i.e.
    "user_devices_{user_id}" with no per-device suffix - regardless of
    which device it's on. This function previously appended each
    DeviceToken's own pk to build a per-device group name and looped,
    calling send_websocket_event once per token; since no consumer has
    ever subscribed to a "user_devices_{user_id}_{token_pk}" group, every
    call silently reached zero sockets while still reporting success. Fixed
    to import the real group name from consumers.py (single source of
    truth) and send once - Channels already fans a single group_send out
    to every connected socket in that group, so looping per device both
    targeted the wrong group *and* would have duplicated delivery to every
    socket once the name was corrected.
    """
    from ..models import DeviceToken
    from ..consumers import _user_devices_group

    active_token_count = DeviceToken.objects.filter(user_id=user_id, is_active=True).count()
    if active_token_count == 0:
        return 0

    success = send_websocket_event(
        group_name=_user_devices_group(user_id), event_type=event_type, data=data
    )
    return active_token_count if success else 0


def get_aggregated_presence(user_id: Any) -> dict:
    """
    Get user's effective presence aggregated across all devices.
    User is ONLINE if ANY device is online.
    """
    from ..models import UserPresence, DeviceToken
    from ..choices import PresenceStatus
    from django.utils import timezone
    from datetime import timedelta
    from ..constants import PRESENCE_OFFLINE_AFTER_SECONDS

    # Check if any device was active recently
    cutoff = timezone.now() - timedelta(seconds=PRESENCE_OFFLINE_AFTER_SECONDS)
    active_devices = DeviceToken.objects.filter(
        user_id=user_id, is_active=True, last_used_at__gte=cutoff
    ).count()

    if active_devices > 0:
        return {"status": PresenceStatus.ONLINE, "device_count": active_devices}

    try:
        presence = UserPresence.objects.get(user_id=user_id)
        return {
            "status": presence.effective_status,
            "last_seen_at": presence.last_seen_at.isoformat() if presence.last_seen_at else None,
            "device_count": 0,
        }
    except UserPresence.DoesNotExist:
        return {"status": PresenceStatus.OFFLINE, "device_count": 0}