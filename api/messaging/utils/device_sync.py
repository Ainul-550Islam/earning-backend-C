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

    # Unread counts per chat
    from django.db.models import Count, Q
    unread_by_chat = dict(
        UserInbox.objects.filter(
            user_id=user_id,
            is_read=False,
            is_archived=False,
        ).values("source_id").annotate(c=Count("id")).values_list("source_id", "c")
    )

    # Total unread
    total_unread = sum(unread_by_chat.values())

    # Chat summaries (last message + participant count)
    chats_summary = []
    for chat in InternalChat.objects.filter(
        id__in=chat_ids, status="ACTIVE"
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
        qs = qs.filter(
            created_at__gte=timezone.now() - timedelta(days=SYNC_DAYS_DEFAULT)
        )

    return list(qs[:MAX_SYNC_MESSAGES_PER_CHAT])


def broadcast_to_all_user_devices(user_id: Any, event_type: str, data: dict) -> int:
    """
    Send a WebSocket event to ALL connected devices of a user.
    Used for cross-device sync (e.g., message read on one device → mark read on all).
    Returns count of devices notified.
    """
    from ..models import DeviceToken
    from ..utils.notifier import send_websocket_event

    active_tokens = DeviceToken.objects.filter(user_id=user_id, is_active=True)
    notified = 0
    for token in active_tokens:
        # Each device has its own WS group
        group = f"user_devices_{user_id}_{token.pk}"
        success = send_websocket_event(group_name=group, event_type=event_type, data=data)
        if success:
            notified += 1
    return notified


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
