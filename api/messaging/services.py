"""
Messaging Services — Core business logic layer. World-class update.

Existing functions preserved:
  create_direct_chat, create_group_chat, send_chat_message, delete_chat_message,
  get_chat_messages, create_broadcast, send_broadcast, create_support_thread,
  reply_to_support_thread, assign_support_thread, mark_inbox_items_read, get_unread_count

New functions added:
  add_reaction, remove_reaction, update_presence, get_presence,
  initiate_call, accept_call, decline_call, end_call,
  pin_message, unpin_message, get_pinned_messages,
  forward_message, schedule_message, cancel_scheduled_message,
  send_scheduled_message_now, translate_message, block_user, unblock_user,
  create_channel, subscribe_channel, unsubscribe_channel, post_to_channel,
  create_poll, vote_on_poll, get_poll_results, process_bot_triggers
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F as models_F, Q as models_Q
from django.utils import timezone
from django.utils.text import slugify

from .choices import (
    ChatStatus,
    MessageType,
    MessageStatus,
    BroadcastStatus,
    BroadcastAudienceType,
    SupportThreadStatus,
    SupportThreadPriority,
    InboxItemType,
    ParticipantRole,
    CallStatus,
    CallType,
    PresenceStatus,
    ScheduledMessageStatus,
    ReactionEmoji,
)
from .constants import (
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES_PER_MINUTE,
    MAX_SUPPORT_THREADS_PER_USER,
    MAX_BATCH_BROADCAST_SIZE,
    DEFAULT_PAGE_SIZE,
    MAX_MESSAGES_FETCH,
    MAX_REACTIONS_PER_MINUTE,
    MAX_CALLS_PER_HOUR,
    CALL_RING_TIMEOUT_SECONDS,
    CALL_MAX_DURATION_SECONDS,
    PRESENCE_CACHE_TTL,
    TRANSLATION_CACHE_TTL,
    SUPPORTED_TRANSLATION_LANGUAGES,
)
from .exceptions import (
    MessagingError,
    ChatNotFoundError,
    ChatAccessDeniedError,
    ChatArchivedError,
    MessageNotFoundError,
    MessageDeletedError,
    BroadcastNotFoundError,
    BroadcastStateError,
    BroadcastSendError,
    SupportThreadNotFoundError,
    SupportThreadClosedError,
    SupportThreadLimitError,
    UserNotFoundError,
    RateLimitError,
)
from .models import (
    InternalChat,
    ChatParticipant,
    ChatMessage,
    AdminBroadcast,
    SupportThread,
    SupportMessage,
    UserInbox,
    MessageReaction,
    UserPresence,
    CallSession,
    AnnouncementChannel,
    ChannelMember,
    ScheduledMessage,
    MessagePin,
    PollVote,
    BotConfig,
    BotResponse,
    MessagingWebhook,
    WebhookDelivery,
    MessageTranslation,
    UserBlock,
    DeviceToken,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helpers (existing)
# ---------------------------------------------------------------------------

def _get_user_or_raise(user_id: Any) -> Any:
    if user_id is None:
        raise UserNotFoundError("user_id must not be None.")
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise UserNotFoundError(f"User pk={user_id!r} does not exist.")
    except (ValueError, TypeError) as exc:
        raise MessagingError(f"Invalid user_id={user_id!r}: {exc}") from exc


def _get_chat_or_raise(chat_id: Any) -> InternalChat:
    if chat_id is None:
        raise ChatNotFoundError("chat_id must not be None.")
    try:
        return InternalChat.objects.get(pk=chat_id)
    except InternalChat.DoesNotExist:
        raise ChatNotFoundError(f"InternalChat pk={chat_id!r} does not exist.")
    except (ValueError, TypeError) as exc:
        raise MessagingError(f"Invalid chat_id={chat_id!r}: {exc}") from exc


def _assert_chat_participant(chat: InternalChat, user_id: Any) -> ChatParticipant:
    try:
        return ChatParticipant.objects.get(chat=chat, user_id=user_id, left_at__isnull=True)
    except ChatParticipant.DoesNotExist:
        raise ChatAccessDeniedError(
            f"User pk={user_id!r} is not a participant of chat id={chat.id}."
        )


def _check_message_rate_limit(user_id: Any) -> None:
    from datetime import timedelta
    since = timezone.now() - timedelta(seconds=60)
    count = ChatMessage.objects.filter(sender_id=user_id, created_at__gte=since).count()
    if count >= MAX_MESSAGES_PER_MINUTE:
        raise RateLimitError(
            f"User pk={user_id!r} has sent {count} messages in the last 60 seconds. "
            f"Limit is {MAX_MESSAGES_PER_MINUTE}."
        )


def _check_user_blocked(sender_id: Any, chat: InternalChat) -> None:
    """Check if any participant in the chat has blocked the sender."""
    participant_ids = list(
        ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
        .exclude(user_id=sender_id)
        .values_list("user_id", flat=True)
    )
    if UserBlock.objects.filter(blocker_id__in=participant_ids, blocked_id=sender_id).exists():
        raise ChatAccessDeniedError(
            f"User pk={sender_id!r} has been blocked by a participant."
        )


# ---------------------------------------------------------------------------
# Chat Services (existing — unchanged)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_direct_chat(user_id_a: Any, user_id_b: Any) -> InternalChat:
    if user_id_a is None or user_id_b is None:
        raise MessagingError("Both user_id_a and user_id_b are required.")
    if str(user_id_a) == str(user_id_b):
        raise MessagingError("Cannot create a direct chat with yourself.")

    user_a = _get_user_or_raise(user_id_a)
    user_b = _get_user_or_raise(user_id_b)

    existing = InternalChat.objects.get_direct_chat(user_id_a, user_id_b)
    if existing is not None:
        return existing

    chat = InternalChat(is_group=False, created_by=user_a)
    chat.full_clean()
    chat.save()

    for user in (user_a, user_b):
        ChatParticipant.objects.create(chat=chat, user=user, role=ParticipantRole.MEMBER)

    logger.info("create_direct_chat: created chat %s between user %s and %s.", chat.id, user_id_a, user_id_b)
    return chat


@transaction.atomic
def create_group_chat(*, creator_id: Any, name: str, member_ids: Sequence[Any]) -> InternalChat:
    if not name or not name.strip():
        raise MessagingError("Group chat name must not be empty.")

    creator = _get_user_or_raise(creator_id)
    members = []
    for mid in member_ids:
        if str(mid) != str(creator_id):
            members.append(_get_user_or_raise(mid))

    chat = InternalChat(name=name.strip(), is_group=True, created_by=creator)
    chat.full_clean()
    chat.save()

    ChatParticipant.objects.create(chat=chat, user=creator, role=ParticipantRole.OWNER)
    for m in members:
        ChatParticipant.objects.create(chat=chat, user=m, role=ParticipantRole.MEMBER)

    logger.info("create_group_chat: chat=%s name=%r creator=%s members=%d", chat.id, name, creator_id, len(members))
    return chat


@transaction.atomic
def send_chat_message(
    *,
    chat_id: Any,
    sender_id: Any,
    content: str,
    message_type: str = MessageType.TEXT,
    reply_to_id: Optional[Any] = None,
    attachments: Optional[list] = None,
    mentions: Optional[list] = None,
    thread_id: Optional[str] = None,
    poll_data: Optional[dict] = None,
    location_data: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> ChatMessage:
    chat = _get_chat_or_raise(chat_id)
    chat.assert_active()
    _assert_chat_participant(chat, sender_id)
    _check_message_rate_limit(sender_id)
    _check_user_blocked(sender_id, chat)

    if message_type == MessageType.TEXT:
        if not content or not content.strip():
            raise MessagingError("Text message content must not be empty.")
        if len(content) > MAX_MESSAGE_LENGTH:
            raise MessagingError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH}.")

    reply_to = None
    if reply_to_id:
        try:
            reply_to = ChatMessage.objects.get(pk=reply_to_id, chat=chat)
            if reply_to.is_deleted:
                raise MessagingError("Cannot reply to a deleted message.")
        except ChatMessage.DoesNotExist:
            raise MessageNotFoundError(f"Reply-to message {reply_to_id!r} not found in this chat.")

    message = ChatMessage(
        chat=chat,
        sender_id=sender_id,
        content=content.strip() if content else "",
        message_type=message_type,
        reply_to=reply_to,
        attachments=attachments or [],
        mentions=mentions or [],
        thread_id=thread_id,
        poll_data=poll_data,
        location_data=location_data,
        metadata=metadata or {},
    )
    message.full_clean()
    message.save()

    chat.touch()
    _fanout_message_to_inboxes(message, chat, sender_id)

    # Handle thread reply count
    if thread_id:
        ChatMessage.objects.filter(id=thread_id).update(
            thread_reply_count=models_F("thread_reply_count") + 1
        )

    # Handle @mentions
    if mentions:
        from .signals import users_mentioned
        users_mentioned.send(sender=ChatMessage, message=message, mentioned_user_ids=mentions)

    from .signals import chat_message_sent
    chat_message_sent.send(sender=ChatMessage, message=message, chat=chat)

    # Process bot triggers
    _process_bot_triggers_async(message)

    logger.info("send_chat_message: msg=%s chat=%s sender=%s type=%s", message.id, chat_id, sender_id, message_type)
    return message


def _fanout_message_to_inboxes(message: ChatMessage, chat: InternalChat, sender_id: Any) -> None:
    participants = list(
        ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
        .exclude(user_id=sender_id)
        .values_list("user_id", flat=True)
    )

    preview = message.content[:100] if message.content else f"[{message.message_type}]"
    inbox_items = [
        UserInbox(
            user_id=uid,
            item_type=InboxItemType.CHAT_MESSAGE,
            source_id=message.id,
            title=chat.name or "Direct Message",
            preview=preview,
            tenant=message.tenant,
        )
        for uid in participants
    ]
    if inbox_items:
        UserInbox.objects.bulk_create(inbox_items, ignore_conflicts=True)


@transaction.atomic
def get_chat_messages(
    *,
    chat_id: Any,
    user_id: Any,
    before_id: Optional[Any] = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list:
    chat = _get_chat_or_raise(chat_id)
    _assert_chat_participant(chat, user_id)

    limit = min(limit, MAX_MESSAGES_FETCH)
    qs = ChatMessage.objects.filter(chat=chat).select_related("sender", "reply_to")

    if before_id:
        try:
            before_msg = ChatMessage.objects.get(pk=before_id, chat=chat)
            qs = qs.filter(created_at__lt=before_msg.created_at)
        except ChatMessage.DoesNotExist:
            pass

    return list(qs.order_by("-created_at")[:limit])


@transaction.atomic
def delete_chat_message(*, message_id: Any, requesting_user_id: Any) -> ChatMessage:
    try:
        message = ChatMessage.objects.select_related("chat").get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage pk={message_id!r} not found.")

    if message.is_deleted:
        raise MessageDeletedError(f"ChatMessage {message_id!r} is already deleted.")

    _assert_chat_participant(message.chat, requesting_user_id)

    if str(message.sender_id) != str(requesting_user_id):
        participant = ChatParticipant.objects.filter(
            chat=message.chat, user_id=requesting_user_id
        ).first()
        if not participant or participant.role not in (ParticipantRole.ADMIN, ParticipantRole.OWNER):
            raise ChatAccessDeniedError("Only message sender or chat admin can delete a message.")

    message.soft_delete(deleted_by_id=requesting_user_id)
    return message


# ---------------------------------------------------------------------------
# Reaction Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def add_reaction(*, message_id: Any, user_id: Any, emoji: str, custom_emoji: str = "") -> MessageReaction:
    """Add or toggle an emoji reaction on a message."""
    from datetime import timedelta
    since = timezone.now() - timedelta(seconds=60)
    rate = MessageReaction.objects.filter(user_id=user_id, created_at__gte=since).count()
    if rate >= MAX_REACTIONS_PER_MINUTE:
        raise RateLimitError(f"Reaction rate limit exceeded ({MAX_REACTIONS_PER_MINUTE}/min).")

    try:
        message = ChatMessage.objects.select_related("chat").get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage {message_id!r} not found.")

    if message.is_deleted:
        raise MessageDeletedError("Cannot react to a deleted message.")

    _assert_chat_participant(message.chat, user_id)

    reaction, created = MessageReaction.objects.get_or_create(
        message=message,
        user_id=user_id,
        emoji=emoji,
        defaults={"custom_emoji": custom_emoji or None, "tenant": message.tenant},
    )

    if created:
        from .signals import message_reaction_added
        message_reaction_added.send(sender=MessageReaction, reaction=reaction, message=message)
        logger.info("add_reaction: user=%s reacted %s on msg=%s", user_id, emoji, message_id)

    return reaction


@transaction.atomic
def remove_reaction(*, message_id: Any, user_id: Any, emoji: str) -> bool:
    """Remove a reaction. Returns True if deleted, False if it didn't exist."""
    deleted_count, _ = MessageReaction.objects.filter(
        message_id=message_id,
        user_id=user_id,
        emoji=emoji,
    ).delete()

    if deleted_count:
        from .signals import message_reaction_removed
        message_reaction_removed.send(
            sender=MessageReaction,
            user_id=user_id,
            message_id=message_id,
            emoji=emoji,
        )
        logger.info("remove_reaction: user=%s removed %s from msg=%s", user_id, emoji, message_id)
    return deleted_count > 0


def get_message_reactions(message_id: Any) -> dict:
    """Return reaction counts grouped by emoji."""
    from django.db.models import Count
    reactions = (
        MessageReaction.objects
        .filter(message_id=message_id)
        .values("emoji")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return {r["emoji"]: r["count"] for r in reactions}


# ---------------------------------------------------------------------------
# Presence Services (NEW)
# ---------------------------------------------------------------------------

def update_presence(*, user_id: Any, status: str, platform: str = "web") -> UserPresence:
    """Upsert user presence. Called on WS connect/disconnect/ping."""
    from django.core.cache import cache

    presence, _ = UserPresence.objects.get_or_create(
        user_id=user_id,
        defaults={"status": status, "last_seen_on": platform},
    )

    now = timezone.now()
    UserPresence.objects.filter(pk=presence.pk).update(
        status=status,
        last_seen_at=now,
        last_seen_on=platform,
        updated_at=now,
    )
    presence.status = status
    presence.last_seen_at = now

    # Cache for fast reads
    cache_key = f"presence:{user_id}"
    cache.set(cache_key, {"status": status, "last_seen_at": now.isoformat()}, PRESENCE_CACHE_TTL)

    old_status = getattr(presence, "_original_status", None)
    if old_status and old_status != status:
        from .signals import presence_changed
        presence_changed.send(sender=UserPresence, user_id=user_id, old_status=old_status, new_status=status)

    return presence


def get_presence(user_id: Any) -> dict:
    """Get user presence. Checks cache first, falls back to DB."""
    from django.core.cache import cache
    cache_key = f"presence:{user_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        p = UserPresence.objects.get(user_id=user_id)
        data = {
            "status": p.effective_status,
            "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
            "custom_status": p.custom_status,
            "custom_status_emoji": p.custom_status_emoji,
        }
        cache.set(cache_key, data, PRESENCE_CACHE_TTL)
        return data
    except UserPresence.DoesNotExist:
        return {"status": PresenceStatus.OFFLINE, "last_seen_at": None}


def get_chat_presences(chat_id: Any) -> dict:
    """Return {user_id: presence_dict} for all participants in a chat."""
    participant_ids = list(
        ChatParticipant.objects.filter(chat_id=chat_id, left_at__isnull=True)
        .values_list("user_id", flat=True)
    )
    return {uid: get_presence(uid) for uid in participant_ids}


# ---------------------------------------------------------------------------
# Call Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def initiate_call(
    *,
    caller_id: Any,
    chat_id: Any,
    call_type: str = CallType.AUDIO,
    ice_servers: Optional[list] = None,
) -> CallSession:
    """Start a call in a chat room."""
    from datetime import timedelta
    import uuid as _uuid

    chat = _get_chat_or_raise(chat_id)
    _assert_chat_participant(chat, caller_id)

    # Rate limit: max calls per hour
    since = timezone.now() - timedelta(hours=1)
    call_count = CallSession.objects.filter(initiated_by_id=caller_id, created_at__gte=since).count()
    if call_count >= MAX_CALLS_PER_HOUR:
        raise RateLimitError(f"Call rate limit: max {MAX_CALLS_PER_HOUR} calls per hour.")

    # Check no ongoing call in this chat
    ongoing = CallSession.objects.filter(chat=chat, status__in=[CallStatus.RINGING, CallStatus.ONGOING]).first()
    if ongoing:
        raise MessagingError(f"There is already an active call in this chat (room={ongoing.room_id}).")

    room_id = str(_uuid.uuid4()).replace("-", "")[:16]
    call = CallSession(
        call_type=call_type,
        status=CallStatus.RINGING,
        chat=chat,
        initiated_by_id=caller_id,
        room_id=room_id,
        ice_servers=ice_servers or _get_default_ice_servers(),
        tenant=chat.tenant,
    )
    call.save()

    # Add caller as participant
    call.participants.add(caller_id)

    # Auto-add all chat participants to the call
    participant_ids = list(
        ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
        .exclude(user_id=caller_id)
        .values_list("user_id", flat=True)
    )
    if participant_ids:
        call.participants.add(*participant_ids)

    from .signals import call_started
    caller = _get_user_or_raise(caller_id)
    call_started.send(sender=CallSession, call=call, caller=caller)

    logger.info("initiate_call: call=%s type=%s room=%s caller=%s", call.id, call_type, room_id, caller_id)
    return call


@transaction.atomic
def accept_call(*, call_id: Any, user_id: Any) -> CallSession:
    try:
        call = CallSession.objects.get(pk=call_id)
    except CallSession.DoesNotExist:
        raise MessagingError(f"Call {call_id} not found.")
    if call.status != CallStatus.RINGING:
        raise MessagingError(f"Cannot accept call in status '{call.status}'.")
    call.status = CallStatus.ONGOING
    call.started_at = timezone.now()
    CallSession.objects.filter(pk=call.pk).update(
        status=CallStatus.ONGOING, started_at=call.started_at
    )
    logger.info("accept_call: call=%s accepted by user=%s", call_id, user_id)
    return call


@transaction.atomic
def decline_call(*, call_id: Any, user_id: Any) -> CallSession:
    try:
        call = CallSession.objects.get(pk=call_id)
    except CallSession.DoesNotExist:
        raise MessagingError(f"Call {call_id} not found.")
    if call.status not in (CallStatus.RINGING,):
        raise MessagingError(f"Cannot decline call in status '{call.status}'.")
    call.end_call(status=CallStatus.DECLINED)
    from .signals import call_ended
    call_ended.send(sender=CallSession, call=call, duration_seconds=0)
    return call


@transaction.atomic
def end_call(*, call_id: Any, user_id: Any) -> CallSession:
    try:
        call = CallSession.objects.get(pk=call_id)
    except CallSession.DoesNotExist:
        raise MessagingError(f"Call {call_id} not found.")
    if call.status not in (CallStatus.RINGING, CallStatus.ONGOING):
        raise MessagingError(f"Call {call_id} is already ended.")
    call.end_call(status=CallStatus.ENDED)
    from .signals import call_ended
    call_ended.send(sender=CallSession, call=call, duration_seconds=call.duration_seconds)
    return call


def _get_default_ice_servers() -> list:
    from django.conf import settings
    return getattr(settings, "WEBRTC_ICE_SERVERS", [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ])


# ---------------------------------------------------------------------------
# Pin Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def pin_message(*, message_id: Any, chat_id: Any, pinned_by_id: Any) -> MessagePin:
    """Pin a message in a chat."""
    try:
        message = ChatMessage.objects.get(pk=message_id, chat_id=chat_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"Message {message_id} not found in chat {chat_id}.")

    if message.is_deleted:
        raise MessageDeletedError("Cannot pin a deleted message.")

    participant = _assert_chat_participant(message.chat, pinned_by_id)
    if participant.role not in (ParticipantRole.ADMIN, ParticipantRole.OWNER):
        raise ChatAccessDeniedError("Only chat admins can pin messages.")

    pin, created = MessagePin.objects.get_or_create(
        chat_id=chat_id,
        message=message,
        defaults={"pinned_by_id": pinned_by_id, "tenant": message.tenant},
    )
    if not created:
        raise MessagingError("This message is already pinned.")

    from .signals import message_pinned
    message_pinned.send(sender=MessagePin, pin=pin, chat=message.chat, pinned_by=_get_user_or_raise(pinned_by_id))
    logger.info("pin_message: msg=%s chat=%s by=%s", message_id, chat_id, pinned_by_id)
    return pin


@transaction.atomic
def unpin_message(*, message_id: Any, chat_id: Any, unpinned_by_id: Any) -> bool:
    deleted_count, _ = MessagePin.objects.filter(
        message_id=message_id, chat_id=chat_id
    ).delete()
    if deleted_count:
        from .signals import message_unpinned
        message_unpinned.send(
            sender=MessagePin,
            message_id=message_id,
            chat_id=chat_id,
            unpinned_by=_get_user_or_raise(unpinned_by_id),
        )
    return deleted_count > 0


def get_pinned_messages(chat_id: Any) -> list:
    return list(
        MessagePin.objects.filter(chat_id=chat_id)
        .select_related("message", "pinned_by")
        .order_by("-pinned_at")
    )


# ---------------------------------------------------------------------------
# Forward Service (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def forward_message(*, message_id: Any, target_chat_id: Any, forwarded_by_id: Any) -> ChatMessage:
    """Forward a message to another chat."""
    try:
        original = ChatMessage.objects.get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"Message {message_id} not found.")

    if original.is_deleted:
        raise MessageDeletedError("Cannot forward a deleted message.")

    forwarded = send_chat_message(
        chat_id=target_chat_id,
        sender_id=forwarded_by_id,
        content=original.content,
        message_type=original.message_type,
        attachments=original.attachments,
        metadata={"forwarded": True, "original_chat_id": str(original.chat_id)},
    )

    ChatMessage.objects.filter(pk=forwarded.pk).update(
        is_forwarded=True,
        forwarded_from=original,
    )
    forwarded.is_forwarded = True
    forwarded.forwarded_from = original

    from .signals import message_forwarded
    message_forwarded.send(
        sender=ChatMessage,
        original_message=original,
        forwarded_message=forwarded,
        forwarded_by=_get_user_or_raise(forwarded_by_id),
    )
    return forwarded


# ---------------------------------------------------------------------------
# Scheduled Message Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def schedule_message(
    *,
    chat_id: Any,
    sender_id: Any,
    content: str,
    scheduled_for: Any,
    message_type: str = MessageType.TEXT,
    attachments: Optional[list] = None,
) -> ScheduledMessage:
    """Schedule a message to be sent at scheduled_for datetime."""
    chat = _get_chat_or_raise(chat_id)
    chat.assert_active()
    _assert_chat_participant(chat, sender_id)

    if scheduled_for <= timezone.now():
        raise MessagingError("scheduled_for must be in the future.")

    sched = ScheduledMessage(
        chat=chat,
        sender_id=sender_id,
        content=content.strip() if content else "",
        message_type=message_type,
        attachments=attachments or [],
        scheduled_for=scheduled_for,
        status=ScheduledMessageStatus.PENDING,
        tenant=chat.tenant,
    )
    sched.save()
    logger.info("schedule_message: sched=%s chat=%s sender=%s for=%s", sched.id, chat_id, sender_id, scheduled_for)
    return sched


@transaction.atomic
def cancel_scheduled_message(*, scheduled_id: Any, user_id: Any) -> ScheduledMessage:
    try:
        sched = ScheduledMessage.objects.get(pk=scheduled_id)
    except ScheduledMessage.DoesNotExist:
        raise MessagingError(f"Scheduled message {scheduled_id} not found.")

    if str(sched.sender_id) != str(user_id):
        raise ChatAccessDeniedError("Only the sender can cancel a scheduled message.")

    if sched.status != ScheduledMessageStatus.PENDING:
        raise MessagingError(f"Cannot cancel a {sched.status} scheduled message.")

    sched.status = ScheduledMessageStatus.CANCELLED
    ScheduledMessage.objects.filter(pk=sched.pk).update(status=ScheduledMessageStatus.CANCELLED)
    return sched


@transaction.atomic
def send_scheduled_message_now(*, scheduled_id: Any) -> ChatMessage:
    """Called by Celery task to actually send the scheduled message."""
    try:
        sched = ScheduledMessage.objects.select_for_update().get(
            pk=scheduled_id, status=ScheduledMessageStatus.PENDING
        )
    except ScheduledMessage.DoesNotExist:
        raise MessagingError(f"Scheduled message {scheduled_id} not found or not pending.")

    try:
        msg = send_chat_message(
            chat_id=sched.chat_id,
            sender_id=sched.sender_id,
            content=sched.content,
            message_type=sched.message_type,
            attachments=sched.attachments,
        )
        ScheduledMessage.objects.filter(pk=sched.pk).update(
            status=ScheduledMessageStatus.SENT,
            sent_message=msg,
        )
        from .signals import scheduled_message_sent
        scheduled_message_sent.send(sender=ScheduledMessage, scheduled_msg=sched, sent_message=msg)
        return msg
    except Exception as exc:
        ScheduledMessage.objects.filter(pk=sched.pk).update(
            status=ScheduledMessageStatus.FAILED,
            error=str(exc)[:500],
        )
        raise


# ---------------------------------------------------------------------------
# Translation Services (NEW)
# ---------------------------------------------------------------------------

def translate_message(*, message_id: Any, target_language: str, user_id: Any) -> str:
    """
    Translate a message to target_language.
    Caches translation in MessageTranslation model.
    Falls back to a stub if no provider configured.
    """
    if target_language not in SUPPORTED_TRANSLATION_LANGUAGES:
        raise MessagingError(f"Unsupported language: {target_language}. Supported: {SUPPORTED_TRANSLATION_LANGUAGES}")

    try:
        message = ChatMessage.objects.get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage {message_id} not found.")

    # Return cached translation if exists
    cached = MessageTranslation.objects.filter(
        message=message, target_language=target_language
    ).first()
    if cached:
        return cached.translated_content

    # Call translation provider
    translated_content, source_lang = _call_translation_provider(message.content, target_language)

    # Cache it
    MessageTranslation.objects.update_or_create(
        message=message,
        target_language=target_language,
        defaults={
            "translated_content": translated_content,
            "source_language": source_lang,
            "tenant": message.tenant,
        },
    )

    logger.info("translate_message: msg=%s → %s (source=%s)", message_id, target_language, source_lang)
    return translated_content


def _call_translation_provider(text: str, target_lang: str) -> tuple[str, str]:
    """
    Call configured translation provider.
    Supports Google Translate (GOOGLE_TRANSLATE_API_KEY) or DeepL (DEEPL_API_KEY).
    Falls back to stub for testing.
    """
    from django.conf import settings
    import requests

    google_key = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", None)
    deepl_key = getattr(settings, "DEEPL_API_KEY", None)

    if google_key:
        try:
            resp = requests.post(
                "https://translation.googleapis.com/language/translate/v2",
                json={"q": text, "target": target_lang, "format": "text"},
                params={"key": google_key},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data["data"]["translations"][0]
            return result["translatedText"], result.get("detectedSourceLanguage", "")
        except Exception as exc:
            logger.warning("Google Translate failed: %s", exc)

    if deepl_key:
        try:
            resp = requests.post(
                "https://api-free.deepl.com/v2/translate",
                headers={"Authorization": f"DeepL-Auth-Key {deepl_key}"},
                data={"text": text, "target_lang": target_lang.upper()},
                timeout=5,
            )
            resp.raise_for_status()
            result = resp.json()["translations"][0]
            return result["text"], result.get("detected_source_language", "").lower()
        except Exception as exc:
            logger.warning("DeepL failed: %s", exc)

    # Stub fallback for development
    logger.debug("Translation stub: no provider configured. Returning original text.")
    return f"[{target_lang.upper()}] {text}", "unknown"


# ---------------------------------------------------------------------------
# Block Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def block_user(*, blocker_id: Any, blocked_id: Any, reason: str = "") -> UserBlock:
    if str(blocker_id) == str(blocked_id):
        raise MessagingError("Cannot block yourself.")

    _get_user_or_raise(blocked_id)

    block, created = UserBlock.objects.get_or_create(
        blocker_id=blocker_id,
        blocked_id=blocked_id,
        defaults={"reason": reason[:200]},
    )
    if not created:
        raise MessagingError(f"User {blocked_id} is already blocked.")

    from .signals import user_blocked
    user_blocked.send(sender=UserBlock, block=block)
    logger.info("block_user: %s blocked %s", blocker_id, blocked_id)
    return block


@transaction.atomic
def unblock_user(*, blocker_id: Any, blocked_id: Any) -> bool:
    deleted_count, _ = UserBlock.objects.filter(
        blocker_id=blocker_id, blocked_id=blocked_id
    ).delete()
    if deleted_count:
        from .signals import user_unblocked
        user_unblocked.send(sender=UserBlock, blocker_id=blocker_id, blocked_id=blocked_id)
    return deleted_count > 0


def is_user_blocked(blocker_id: Any, blocked_id: Any) -> bool:
    return UserBlock.objects.filter(blocker_id=blocker_id, blocked_id=blocked_id).exists()


# ---------------------------------------------------------------------------
# Channel Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_channel(
    *,
    name: str,
    created_by_id: Any,
    description: str = "",
    channel_type: str = "PUBLIC",
    tenant=None,
) -> AnnouncementChannel:
    creator = _get_user_or_raise(created_by_id)
    base_slug = slugify(name)[:80] or "channel"
    slug = base_slug
    counter = 1
    while AnnouncementChannel.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    channel = AnnouncementChannel(
        name=name.strip(),
        slug=slug,
        description=description[:1000],
        channel_type=channel_type,
        created_by=creator,
        tenant=tenant,
    )
    channel.save()

    # Creator becomes admin member
    ChannelMember.objects.create(channel=channel, user=creator, is_admin=True, tenant=tenant)

    logger.info("create_channel: channel=%s slug=%s by=%s", channel.id, slug, created_by_id)
    return channel


@transaction.atomic
def subscribe_channel(*, channel_id: Any, user_id: Any) -> ChannelMember:
    try:
        channel = AnnouncementChannel.objects.get(pk=channel_id)
    except AnnouncementChannel.DoesNotExist:
        raise MessagingError(f"Channel {channel_id} not found.")

    member, created = ChannelMember.objects.get_or_create(
        channel=channel,
        user_id=user_id,
        defaults={"tenant": channel.tenant},
    )
    if created:
        AnnouncementChannel.objects.filter(pk=channel.pk).update(
            subscriber_count=models_F("subscriber_count") + 1
        )
        from .signals import channel_subscribed
        channel_subscribed.send(
            sender=ChannelMember,
            channel=channel,
            user=_get_user_or_raise(user_id),
        )
    return member


@transaction.atomic
def unsubscribe_channel(*, channel_id: Any, user_id: Any) -> bool:
    deleted_count, _ = ChannelMember.objects.filter(
        channel_id=channel_id, user_id=user_id
    ).delete()
    if deleted_count:
        AnnouncementChannel.objects.filter(pk=channel_id).update(
            subscriber_count=models_F("subscriber_count") - 1
        )
        from .signals import channel_unsubscribed
        channel_unsubscribed.send(sender=ChannelMember, channel_id=channel_id, user_id=user_id)
    return deleted_count > 0


# ---------------------------------------------------------------------------
# Poll Services (NEW)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_poll(
    *,
    chat_id: Any,
    sender_id: Any,
    question: str,
    options: list[str],
    multiple_choice: bool = False,
    expires_in_hours: int = 24,
) -> ChatMessage:
    """Create a poll message in a chat."""
    if not question or not question.strip():
        raise MessagingError("Poll question must not be empty.")
    if len(options) < 2:
        raise MessagingError("Poll must have at least 2 options.")
    if len(options) > 10:
        raise MessagingError("Poll cannot have more than 10 options.")

    from datetime import timedelta
    expires_at = timezone.now() + timedelta(hours=expires_in_hours)

    poll_data = {
        "question": question.strip(),
        "options": [{"id": str(i), "text": opt.strip()} for i, opt in enumerate(options)],
        "multiple_choice": multiple_choice,
        "expires_at": expires_at.isoformat(),
    }

    return send_chat_message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=question.strip(),
        message_type=MessageType.POLL,
        poll_data=poll_data,
    )


@transaction.atomic
def vote_on_poll(*, message_id: Any, user_id: Any, option_id: str) -> PollVote:
    """Cast or update a vote on a poll."""
    try:
        message = ChatMessage.objects.get(pk=message_id, message_type=MessageType.POLL)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"Poll message {message_id} not found.")

    poll_data = message.poll_data or {}
    option_ids = [o["id"] for o in poll_data.get("options", [])]
    if option_id not in option_ids:
        raise MessagingError(f"Option '{option_id}' does not exist in this poll.")

    # Check poll expiry
    expires_at_str = poll_data.get("expires_at")
    if expires_at_str:
        from django.utils.dateparse import parse_datetime
        expires_at = parse_datetime(expires_at_str)
        if expires_at and timezone.now() > expires_at:
            raise MessagingError("This poll has expired.")

    vote, created = PollVote.objects.update_or_create(
        message=message,
        user_id=user_id,
        defaults={"option_id": option_id, "tenant": message.tenant},
    )
    return vote


def get_poll_results(message_id: Any) -> dict:
    """Return poll results as {option_id: {text, votes, percentage}}."""
    try:
        message = ChatMessage.objects.get(pk=message_id, message_type=MessageType.POLL)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"Poll message {message_id} not found.")

    from django.db.models import Count
    votes = dict(
        PollVote.objects.filter(message=message)
        .values("option_id")
        .annotate(count=Count("id"))
        .values_list("option_id", "count")
    )
    total_votes = sum(votes.values())

    poll_data = message.poll_data or {}
    results = {}
    for opt in poll_data.get("options", []):
        opt_id = opt["id"]
        count = votes.get(opt_id, 0)
        results[opt_id] = {
            "text": opt["text"],
            "votes": count,
            "percentage": round(count / total_votes * 100, 1) if total_votes else 0,
        }

    return {
        "question": poll_data.get("question", ""),
        "total_votes": total_votes,
        "options": results,
        "expires_at": poll_data.get("expires_at"),
    }


# ---------------------------------------------------------------------------
# Bot Engine (NEW)
# ---------------------------------------------------------------------------

def _process_bot_triggers_async(message: ChatMessage) -> None:
    """Queue bot trigger processing in Celery (non-blocking)."""
    try:
        from .tasks import process_bot_triggers_task
        process_bot_triggers_task.delay(str(message.id))
    except Exception as exc:
        logger.warning("Could not queue bot trigger task: %s", exc)


def process_bot_triggers(message_id: Any) -> list[BotResponse]:
    """
    Check all active BotConfigs and send matching auto-replies.
    Called by Celery task.
    """
    try:
        message = ChatMessage.objects.select_related("chat", "sender").get(pk=message_id)
    except ChatMessage.DoesNotExist:
        return []

    if message.is_deleted or message.message_type == MessageType.SYSTEM:
        return []

    from .choices import BotTriggerType
    bots = BotConfig.objects.filter(
        is_active=True
    ).filter(
        models_Q(chat=message.chat) | models_Q(chat__isnull=True)
    ).order_by("-priority")

    responses = []
    for bot in bots:
        triggered = False
        content = message.content or ""

        if bot.trigger_type == BotTriggerType.KEYWORD:
            triggered = bot.trigger_value.lower() in content.lower()
        elif bot.trigger_type == BotTriggerType.REGEX:
            try:
                triggered = bool(re.search(bot.trigger_value, content, re.IGNORECASE))
            except re.error:
                logger.warning("Bot %s has invalid regex: %s", bot.id, bot.trigger_value)
        elif bot.trigger_type == BotTriggerType.ALWAYS:
            triggered = True

        if not triggered:
            continue

        # Build response text
        sender_name = ""
        if message.sender:
            sender_name = getattr(message.sender, "get_full_name", lambda: "")() or str(message.sender)
        response_text = bot.response_template.replace("{user_name}", sender_name).replace(
            "{chat_name}", message.chat.name or "this chat"
        )

        try:
            import time as _time
            if bot.delay_seconds:
                _time.sleep(bot.delay_seconds)

            # Post as a SYSTEM/BOT message
            sent_msg = ChatMessage.objects.create(
                chat=message.chat,
                content=response_text,
                message_type=MessageType.BOT,
                tenant=message.tenant,
            )
            bot_resp = BotResponse.objects.create(
                bot=bot,
                trigger_message=message,
                sent_message=sent_msg,
                was_successful=True,
                tenant=message.tenant,
            )
            responses.append(bot_resp)
            logger.info("Bot %s replied to msg %s in chat %s", bot.id, message_id, message.chat_id)
        except Exception as exc:
            BotResponse.objects.create(
                bot=bot,
                trigger_message=message,
                was_successful=False,
                error=str(exc)[:500],
                tenant=message.tenant,
            )
            logger.error("Bot %s failed for msg %s: %s", bot.id, message_id, exc)

    return responses


# ---------------------------------------------------------------------------
# Webhook Dispatcher (NEW)
# ---------------------------------------------------------------------------

def dispatch_webhook_event(event_type: str, payload: dict) -> None:
    """Dispatch a webhook event to all registered listeners. Non-blocking via Celery."""
    try:
        from .tasks import dispatch_webhook_task
        dispatch_webhook_task.delay(event_type, payload)
    except Exception as exc:
        logger.warning("Could not queue webhook dispatch: %s", exc)


# ---------------------------------------------------------------------------
# Broadcast Services (existing — unchanged)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_broadcast(
    *,
    title: str,
    body: str,
    created_by_id: Any,
    audience_type: str = BroadcastAudienceType.ALL_USERS,
    audience_filter: Optional[dict] = None,
    scheduled_at=None,
) -> AdminBroadcast:
    creator = _get_user_or_raise(created_by_id)
    broadcast = AdminBroadcast(
        title=title.strip(),
        body=body.strip(),
        created_by=creator,
        audience_type=audience_type,
        audience_filter=audience_filter or {},
        scheduled_at=scheduled_at,
        status=BroadcastStatus.DRAFT,
        tenant=getattr(creator, "tenant", None),
    )
    broadcast.full_clean()
    broadcast.save()
    logger.info("create_broadcast: id=%s title=%r by=%s", broadcast.id, title, created_by_id)
    return broadcast


@transaction.atomic
def send_broadcast(broadcast_id: Any, *, actor_id: Optional[Any] = None) -> dict:
    try:
        broadcast = AdminBroadcast.objects.select_for_update().get(pk=broadcast_id)
    except AdminBroadcast.DoesNotExist:
        raise BroadcastNotFoundError(f"AdminBroadcast pk={broadcast_id!r} does not exist.")

    if broadcast.status not in (BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED):
        raise BroadcastStateError(
            f"Cannot send broadcast in status '{broadcast.status}'. Must be DRAFT or SCHEDULED."
        )

    broadcast.transition_to(BroadcastStatus.SENDING, actor=_get_user_or_raise(actor_id) if actor_id else None)

    try:
        recipients = list(_resolve_broadcast_audience(broadcast))
        total = len(recipients)
        broadcast.recipient_count = total
        AdminBroadcast.objects.filter(pk=broadcast.pk).update(recipient_count=total)

        inbox_items = [
            UserInbox(
                user_id=uid,
                item_type=InboxItemType.BROADCAST,
                source_id=broadcast.id,
                title=broadcast.title,
                preview=broadcast.body[:100],
                tenant=broadcast.tenant,
            )
            for uid in recipients
        ]

        delivered = 0
        for i in range(0, len(inbox_items), MAX_BATCH_BROADCAST_SIZE):
            batch = inbox_items[i:i + MAX_BATCH_BROADCAST_SIZE]
            UserInbox.objects.bulk_create(batch, ignore_conflicts=True)
            delivered += len(batch)
            AdminBroadcast.objects.filter(pk=broadcast.pk).update(delivered_count=delivered)

        broadcast.transition_to(BroadcastStatus.SENT, actor=None)

        from .signals import broadcast_sent
        broadcast_sent.send(sender=AdminBroadcast, broadcast=broadcast)

        logger.info("send_broadcast: id=%s sent to %d recipients", broadcast_id, delivered)
        return {"success": True, "broadcast_id": str(broadcast_id), "recipients": total, "delivered": delivered}

    except Exception as exc:
        broadcast.mark_failed(str(exc))
        raise BroadcastSendError(f"Broadcast {broadcast_id} failed: {exc}") from exc


def _resolve_broadcast_audience(broadcast: AdminBroadcast):
    qs = User.objects.all()
    if broadcast.audience_type == BroadcastAudienceType.ACTIVE_USERS:
        from datetime import timedelta
        since = timezone.now() - timedelta(days=30)
        qs = qs.filter(last_login__gte=since)
    elif broadcast.audience_type == BroadcastAudienceType.SPECIFIC_USERS:
        user_ids = broadcast.audience_filter.get("user_ids", [])
        qs = qs.filter(pk__in=user_ids)
    return qs.values_list("pk", flat=True)


# ---------------------------------------------------------------------------
# Support Services (existing — unchanged)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_support_thread(
    *,
    user_id: Any,
    subject: str,
    initial_message: str,
    priority: str = SupportThreadPriority.NORMAL,
) -> SupportThread:
    user = _get_user_or_raise(user_id)

    open_count = SupportThread.objects.filter(
        user=user,
        status__in=[SupportThreadStatus.OPEN, SupportThreadStatus.IN_PROGRESS, SupportThreadStatus.WAITING_USER],
    ).count()

    if open_count >= MAX_SUPPORT_THREADS_PER_USER:
        raise SupportThreadLimitError(
            f"User pk={user_id!r} already has {open_count} open support threads. "
            f"Max is {MAX_SUPPORT_THREADS_PER_USER}."
        )

    if not subject or not subject.strip():
        raise MessagingError("Support thread subject must not be empty.")
    if not initial_message or not initial_message.strip():
        raise MessagingError("Initial message must not be empty.")

    thread = SupportThread(
        user=user,
        subject=subject.strip(),
        priority=priority,
        status=SupportThreadStatus.OPEN,
        tenant=getattr(user, "tenant", None),
    )
    thread.full_clean()
    thread.save()

    SupportMessage.objects.create(
        thread=thread,
        sender=user,
        content=initial_message.strip(),
        is_agent_reply=False,
        tenant=thread.tenant,
    )

    logger.info("create_support_thread: thread=%s user=%s subject=%r", thread.id, user_id, subject[:50])
    return thread


@transaction.atomic
def reply_to_support_thread(
    *,
    thread_id: Any,
    sender_id: Any,
    content: str,
    is_agent: bool = False,
    is_internal_note: bool = False,
) -> SupportMessage:
    try:
        thread = SupportThread.objects.select_for_update().get(pk=thread_id)
    except SupportThread.DoesNotExist:
        raise SupportThreadNotFoundError(f"SupportThread pk={thread_id!r} does not exist.")

    thread.assert_open_for_reply()

    if not content or not content.strip():
        raise MessagingError("Reply content must not be empty.")

    sender = _get_user_or_raise(sender_id)
    msg = SupportMessage.objects.create(
        thread=thread,
        sender=sender,
        content=content.strip(),
        is_agent_reply=is_agent,
        is_internal_note=is_internal_note,
        tenant=thread.tenant,
    )

    now = timezone.now()
    SupportThread.objects.filter(pk=thread.pk).update(last_reply_at=now, updated_at=now)

    if thread.status == SupportThreadStatus.OPEN and is_agent:
        thread.transition_to(SupportThreadStatus.IN_PROGRESS, agent=sender)
    elif thread.status == SupportThreadStatus.WAITING_USER and not is_agent:
        thread.transition_to(SupportThreadStatus.IN_PROGRESS, agent=sender)

    if is_agent and not is_internal_note:
        from .signals import support_reply_posted
        support_reply_posted.send(sender=SupportMessage, support_message=msg, thread=thread)

    logger.info("reply_to_support_thread: thread=%s msg=%s by=%s agent=%s", thread_id, msg.id, sender_id, is_agent)
    return msg


@transaction.atomic
def assign_support_thread(*, thread_id: Any, agent_id: Any, assigner_id: Any) -> SupportThread:
    try:
        thread = SupportThread.objects.get(pk=thread_id)
    except SupportThread.DoesNotExist:
        raise SupportThreadNotFoundError(f"SupportThread pk={thread_id!r} does not exist.")

    agent = _get_user_or_raise(agent_id)
    old_agent_id = thread.assigned_agent_id
    thread.assigned_agent = agent
    SupportThread.objects.filter(pk=thread.pk).update(
        assigned_agent=agent, updated_at=timezone.now()
    )
    logger.info("assign_support_thread: thread=%s agent=%s (was %s)", thread_id, agent_id, old_agent_id)
    return thread


# ---------------------------------------------------------------------------
# Inbox Services (existing — unchanged)
# ---------------------------------------------------------------------------

def _create_inbox_item(
    *,
    user_id: Any,
    item_type: str,
    source_id: Any,
    title: str = "",
    preview: str = "",
    metadata: Optional[dict] = None,
    tenant=None,
) -> Optional[UserInbox]:
    try:
        return UserInbox.objects.create(
            user_id=user_id,
            item_type=item_type,
            source_id=source_id,
            title=title[:255],
            preview=preview[:200],
            metadata=metadata or {},
            tenant=tenant,
        )
    except Exception as exc:
        logger.error("_create_inbox_item: failed for user=%s type=%s: %s", user_id, item_type, exc)
        return None


@transaction.atomic
def mark_inbox_items_read(*, user_id: Any, item_ids: Optional[Sequence[Any]] = None) -> int:
    now = timezone.now()
    qs = UserInbox.objects.filter(user_id=user_id, is_read=False)
    if item_ids:
        qs = qs.filter(pk__in=item_ids)
    updated = qs.update(is_read=True, read_at=now, updated_at=now)
    logger.debug("mark_inbox_items_read: user=%s updated=%d", user_id, updated)
    return updated


def get_unread_count(user_id: Any) -> int:
    return UserInbox.objects.filter(user_id=user_id, is_read=False, is_archived=False).count()


# ---------------------------------------------------------------------------
# Search Service (NEW)
# ---------------------------------------------------------------------------

def search_messages(
    *,
    user_id: Any,
    query: str,
    chat_id: Optional[Any] = None,
    limit: int = 20,
) -> list:
    """Full-text search within messages the user has access to."""
    if not query or not query.strip():
        return []

    # Get all chats the user participates in
    user_chat_ids = list(
        ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
        .values_list("chat_id", flat=True)
    )

    qs = ChatMessage.objects.filter(
        chat_id__in=user_chat_ids,
        status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
        content__icontains=query.strip(),
    ).select_related("chat", "sender").order_by("-created_at")

    if chat_id:
        qs = qs.filter(chat_id=chat_id)

    return list(qs[:min(limit, 50)])


# ---------------------------------------------------------------------------
# Helpers (module-level imports for F/Q that may be used above)
# ---------------------------------------------------------------------------

from django.db.models import F as models_F, Q as models_Q


# ===========================================================================
# FINAL 6% — New Service Functions
# ===========================================================================

# ---------------------------------------------------------------------------
# Message Edit History
# ---------------------------------------------------------------------------

@transaction.atomic
def edit_message_with_history(
    *,
    message_id: Any,
    user_id: Any,
    new_content: str,
    reason: str = "",
) -> tuple:
    """
    Edit a message and save the previous version to MessageEditHistory.
    Returns (updated_message, edit_history_record).
    """
    from .models import MessageEditHistory
    try:
        message = ChatMessage.objects.select_for_update().get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage {message_id} not found.")

    if message.is_deleted:
        raise MessageDeletedError("Cannot edit a deleted message.")
    if str(message.sender_id) != str(user_id):
        raise ChatAccessDeniedError("Only the message sender can edit this message.")

    # Count previous edits
    edit_count = MessageEditHistory.objects.filter(message=message).count() + 1

    # Save history record BEFORE editing
    history = MessageEditHistory.objects.create(
        message=message,
        edited_by_id=user_id,
        previous_content=message.content,
        previous_attachments=message.attachments or [],
        edit_reason=reason[:300],
        edit_number=edit_count,
        tenant=message.tenant,
    )

    # Apply the edit
    message.mark_edited(new_content)

    logger.info("edit_message_with_history: msg=%s edit#%d by user=%s", message_id, edit_count, user_id)
    return message, history


def get_message_edit_history(message_id: Any, user_id: Any) -> list:
    """Return all edit history records for a message."""
    from .models import MessageEditHistory
    try:
        message = ChatMessage.objects.only("chat_id").get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage {message_id} not found.")
    _assert_chat_participant(message.chat, user_id)
    return list(
        MessageEditHistory.objects.filter(message_id=message_id)
        .select_related("edited_by")
        .order_by("created_at")
    )


# ---------------------------------------------------------------------------
# Disappearing Messages
# ---------------------------------------------------------------------------

@transaction.atomic
def set_disappearing_messages(
    *,
    chat_id: Any,
    enabled_by_id: Any,
    ttl_seconds: Optional[int],
) -> "DisappearingMessageConfig":
    """
    Enable or disable disappearing messages for a chat.
    Pass ttl_seconds=None to disable.
    """
    from .models import DisappearingMessageConfig
    chat = _get_chat_or_raise(chat_id)
    participant = _assert_chat_participant(chat, enabled_by_id)

    # Only admins/owners can change this setting
    if participant.role not in (ParticipantRole.ADMIN, ParticipantRole.OWNER):
        raise ChatAccessDeniedError("Only chat admins can change disappearing message settings.")

    is_enabled = ttl_seconds is not None
    config, _ = DisappearingMessageConfig.objects.update_or_create(
        chat=chat,
        defaults={
            "is_enabled": is_enabled,
            "ttl_seconds": ttl_seconds or 604_800,
            "enabled_by_id": enabled_by_id,
            "enabled_at": timezone.now() if is_enabled else None,
            "tenant": chat.tenant,
        },
    )

    logger.info("set_disappearing_messages: chat=%s enabled=%s ttl=%s by=%s",
                chat_id, is_enabled, ttl_seconds, enabled_by_id)
    return config


def expire_disappearing_messages() -> int:
    """
    Delete messages that have exceeded their disappearing TTL.
    Called by Celery beat task every 5 minutes.
    Returns count of messages deleted.
    """
    from .models import DisappearingMessageConfig
    from datetime import timedelta

    total_deleted = 0
    configs = DisappearingMessageConfig.objects.filter(is_enabled=True)
    now = timezone.now()

    for config in configs:
        cutoff = now - timedelta(seconds=config.ttl_seconds)
        messages = ChatMessage.objects.filter(
            chat=config.chat,
            created_at__lt=cutoff,
            status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
        )
        count = messages.count()
        messages.update(
            status=MessageStatus.DELETED,
            content="[This message has disappeared]",
            attachments=[],
            deleted_at=now,
            updated_at=now,
        )
        total_deleted += count

    if total_deleted:
        logger.info("expire_disappearing_messages: deleted %d messages", total_deleted)
    return total_deleted


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------

@transaction.atomic
def create_story(
    *,
    user_id: Any,
    story_type: str = "text",
    content: str = "",
    media_url: Optional[str] = None,
    background_color: str = "#000000",
    visibility: str = "all",
    link_url: Optional[str] = None,
    link_label: str = "",
    location: str = "",
    music_track: Optional[dict] = None,
    tenant=None,
) -> "UserStory":
    from .models import UserStory
    from .constants import STORY_TTL_HOURS, STORY_MAX_PER_USER_PER_DAY
    from datetime import timedelta

    # Rate limit: max stories per day
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = UserStory.objects.filter(
        user_id=user_id, created_at__gte=today_start
    ).count()
    if today_count >= STORY_MAX_PER_USER_PER_DAY:
        raise RateLimitError(f"Max {STORY_MAX_PER_USER_PER_DAY} stories per day.")

    if story_type == "text" and not content.strip():
        raise MessagingError("Text stories must have content.")
    if story_type in ("image", "video") and not media_url:
        raise MessagingError(f"{story_type} stories must have a media_url.")

    story = UserStory(
        user_id=user_id,
        story_type=story_type,
        content=content.strip()[:500],
        media_url=media_url,
        background_color=background_color,
        visibility=visibility,
        link_url=link_url,
        link_label=link_label[:100],
        location=location[:200],
        music_track=music_track,
        expires_at=timezone.now() + timedelta(hours=STORY_TTL_HOURS),
        is_active=True,
        tenant=tenant,
    )
    story.save()

    logger.info("create_story: story=%s type=%s user=%s", story.id, story_type, user_id)
    return story


@transaction.atomic
def view_story(*, story_id: Any, viewer_id: Any) -> "StoryView":
    """Record a story view. Increments view count."""
    from .models import UserStory, StoryView

    try:
        story = UserStory.objects.get(pk=story_id, is_active=True)
    except UserStory.DoesNotExist:
        raise MessagingError(f"Story {story_id} not found or expired.")

    if story.is_expired:
        raise MessagingError("This story has expired.")

    # Don't count owner's own views
    view, created = StoryView.objects.get_or_create(
        story=story,
        viewer_id=viewer_id,
        defaults={"tenant": story.tenant},
    )
    if created and str(viewer_id) != str(story.user_id):
        UserStory.objects.filter(pk=story.pk).update(
            view_count=models_F("view_count") + 1
        )
    return view


@transaction.atomic
def reply_to_story(
    *,
    story_id: Any,
    viewer_id: Any,
    reply_text: str = "",
    reaction_emoji: str = "",
) -> "StoryView":
    """Add a reply or reaction to a story view."""
    from .models import UserStory, StoryView

    try:
        view = StoryView.objects.get(story_id=story_id, viewer_id=viewer_id)
    except StoryView.DoesNotExist:
        raise MessagingError("Must view a story before replying.")

    if reply_text:
        StoryView.objects.filter(pk=view.pk).update(reply_text=reply_text[:500])
        view.reply_text = reply_text

    if reaction_emoji:
        StoryView.objects.filter(pk=view.pk).update(reaction_emoji=reaction_emoji[:10])
        view.reaction_emoji = reaction_emoji

    # Send a DM from the viewer to the story owner
    if reply_text and str(viewer_id) != str(view.story.user_id):
        try:
            dm_chat = create_direct_chat(viewer_id, view.story.user_id)
            send_chat_message(
                chat_id=str(dm_chat.id),
                sender_id=viewer_id,
                content=reply_text,
                metadata={"story_reply": True, "story_id": str(story_id)},
            )
        except Exception as exc:
            logger.warning("reply_to_story: could not send DM: %s", exc)

    return view


def get_active_stories_for_contacts(user_id: Any) -> list:
    """
    Return active stories from all contacts visible to user.
    Grouped by user for WhatsApp-style story tray.
    """
    from .models import UserStory, ChatParticipant
    from django.db.models import Prefetch

    # Get all users this user has chats with
    contact_ids = list(
        ChatParticipant.objects.filter(
            chat__participants__user_id=user_id,
            left_at__isnull=True,
        ).exclude(user_id=user_id)
        .values_list("user_id", flat=True)
        .distinct()[:200]
    )

    # Also include the user's own stories
    contact_ids.append(user_id)

    now = timezone.now()
    stories = (
        UserStory.objects
        .filter(
            user_id__in=contact_ids,
            is_active=True,
            expires_at__gt=now,
        )
        .exclude(
            visibility="except",
            visibility_user_ids__contains=[user_id],
        )
        .select_related("user")
        .prefetch_related(
            Prefetch("views", queryset=StoryView.objects.filter(viewer_id=user_id), to_attr="my_views")
        )
        .order_by("user_id", "created_at")
    )

    # Group by user
    from itertools import groupby
    grouped = []
    for uid, user_stories in groupby(stories, key=lambda s: s.user_id):
        story_list = list(user_stories)
        grouped.append({
            "user_id": uid,
            "user": story_list[0].user,
            "stories": story_list,
            "has_unseen": any(not s.my_views for s in story_list),
        })

    return grouped


def expire_old_stories() -> int:
    """Mark expired stories as inactive. Called by Celery beat."""
    from .models import UserStory
    now = timezone.now()
    count = UserStory.objects.filter(
        is_active=True, expires_at__lt=now
    ).update(is_active=False)
    if count:
        logger.info("expire_old_stories: deactivated %d stories", count)
    return count


# ---------------------------------------------------------------------------
# Link Preview
# ---------------------------------------------------------------------------

def fetch_and_save_link_previews(message_id: Any) -> list:
    """
    Extract URLs from a message, fetch OG metadata, and save LinkPreview records.
    Called by Celery task after message is sent.
    """
    from .models import LinkPreview, MessageLinkPreview
    from .utils.link_preview import extract_urls, fetch_link_preview, check_safe_browsing
    from .constants import MAX_LINK_PREVIEWS_PER_MSG

    try:
        message = ChatMessage.objects.get(pk=message_id)
    except ChatMessage.DoesNotExist:
        return []

    if not message.content or message.is_deleted:
        return []

    urls = extract_urls(message.content)[:MAX_LINK_PREVIEWS_PER_MSG]
    if not urls:
        return []

    previews = []
    for i, url in enumerate(urls):
        # Check cache first
        existing = LinkPreview.objects.filter(url=url).first()
        if existing:
            preview = existing
        else:
            # Fetch metadata
            data = fetch_link_preview(url)

            # Safe browsing check
            is_safe = data.get("is_safe", True)
            if is_safe:
                is_safe = check_safe_browsing(url)

            preview = LinkPreview.objects.create(
                url=url,
                title=data.get("title", "")[:500],
                description=data.get("description", ""),
                image_url=data.get("image_url"),
                favicon_url=data.get("favicon_url"),
                site_name=data.get("site_name", "")[:200],
                domain=data.get("domain", "")[:200],
                content_type=data.get("content_type", "website")[:50],
                video_url=data.get("video_url"),
                is_safe=is_safe,
                fetch_error=data.get("fetch_error", ""),
            )

        # Link preview to message
        MessageLinkPreview.objects.get_or_create(
            message=message,
            preview=preview,
            defaults={"position": i, "tenant": message.tenant},
        )
        previews.append(preview)

    logger.info("fetch_and_save_link_previews: msg=%s found %d previews", message_id, len(previews))
    return previews


# ---------------------------------------------------------------------------
# Voice Message
# ---------------------------------------------------------------------------

@transaction.atomic
def process_voice_message(message_id: Any) -> "VoiceMessageTranscription":
    """
    Process an AUDIO type message:
    1. Generate waveform data
    2. Transcribe to text (if STT configured)
    Called by Celery task.
    """
    from .models import VoiceMessageTranscription
    from .utils.voice_processor import transcribe_audio, generate_waveform, get_audio_duration
    from django.conf import settings
    import requests

    try:
        message = ChatMessage.objects.get(pk=message_id, message_type=MessageType.AUDIO)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"Audio message {message_id} not found.")

    # Check if already processed
    existing = VoiceMessageTranscription.objects.filter(message=message).first()
    if existing and not existing.is_processing:
        return existing

    # Get audio URL from attachments
    attachments = message.attachments or []
    if not attachments:
        raise MessagingError("Audio message has no attachments.")

    audio_url = attachments[0].get("url", "")
    if not audio_url:
        raise MessagingError("Audio attachment has no URL.")

    # Create or update transcription record (mark as processing)
    transcription, _ = VoiceMessageTranscription.objects.update_or_create(
        message=message,
        defaults={
            "is_processing": True,
            "transcribed_text": "",
            "tenant": message.tenant,
        },
    )

    try:
        # Download audio data
        resp = requests.get(audio_url, timeout=30)
        resp.raise_for_status()
        audio_data = resp.content

        # Generate waveform
        waveform = generate_waveform(audio_data)
        duration = get_audio_duration(audio_data)

        # Transcribe
        stt_provider = getattr(settings, "STT_PROVIDER", "whisper")
        result = transcribe_audio(audio_data, provider=stt_provider)

        VoiceMessageTranscription.objects.filter(pk=transcription.pk).update(
            transcribed_text=result.get("text", ""),
            language=result.get("language", ""),
            confidence=result.get("confidence", 0.0),
            provider=result.get("provider", stt_provider),
            duration_seconds=duration,
            waveform_data=waveform,
            is_processing=False,
            error=result.get("error", ""),
        )
        transcription.transcribed_text = result.get("text", "")
        transcription.waveform_data = waveform
        transcription.is_processing = False

        logger.info("process_voice_message: msg=%s transcribed %d chars", message_id, len(result.get("text", "")))

    except Exception as exc:
        VoiceMessageTranscription.objects.filter(pk=transcription.pk).update(
            is_processing=False,
            error=str(exc)[:500],
        )
        logger.error("process_voice_message: failed for msg=%s: %s", message_id, exc)
        raise

    return transcription
