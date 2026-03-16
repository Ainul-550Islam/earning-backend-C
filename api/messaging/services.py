"""
Messaging Services — Core business logic layer.

All public functions are the ONLY authorised entry-points for mutating
messaging state. Views, tasks, consumers, and signals must go through
this layer.

Design principles:
- Every public function runs inside an atomic transaction.
- Every function validates inputs before touching the database.
- Structured logging at INFO/DEBUG/WARNING/ERROR everywhere.
- Domain-specific exceptions only — no bare Exception leaks to callers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone

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
)
from .constants import (
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES_PER_MINUTE,
    MAX_SUPPORT_THREADS_PER_USER,
    MAX_BATCH_BROADCAST_SIZE,
    DEFAULT_PAGE_SIZE,
    MAX_MESSAGES_FETCH,
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
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helpers
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
    """
    Verify *user_id* is an active participant of *chat*.

    Returns:
        The ChatParticipant record.

    Raises:
        ChatAccessDeniedError: If the user is not a participant.
    """
    try:
        return ChatParticipant.objects.get(
            chat=chat, user_id=user_id, left_at__isnull=True
        )
    except ChatParticipant.DoesNotExist:
        raise ChatAccessDeniedError(
            f"User pk={user_id!r} is not a participant of chat id={chat.id}."
        )


def _check_message_rate_limit(user_id: Any) -> None:
    """
    Rudimentary rate limit: count messages sent by user in the last 60 seconds.

    Raises:
        RateLimitError: If the user exceeds MAX_MESSAGES_PER_MINUTE.
    """
    from datetime import timedelta
    since = timezone.now() - timedelta(seconds=60)
    count = ChatMessage.objects.filter(
        sender_id=user_id, created_at__gte=since
    ).count()
    if count >= MAX_MESSAGES_PER_MINUTE:
        raise RateLimitError(
            f"User pk={user_id!r} has sent {count} messages in the last 60 seconds. "
            f"Limit is {MAX_MESSAGES_PER_MINUTE}."
        )


# ---------------------------------------------------------------------------
# Chat Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_direct_chat(user_id_a: Any, user_id_b: Any) -> InternalChat:
    """
    Create or return an existing direct (1-to-1) chat between two users.
    Idempotent: returns existing chat if one already exists.

    Args:
        user_id_a: PK of the first user.
        user_id_b: PK of the second user.

    Returns:
        The InternalChat instance (new or existing).

    Raises:
        UserNotFoundError: If either user does not exist.
        MessagingError:    If both user IDs are the same.
    """
    if user_id_a is None or user_id_b is None:
        raise MessagingError("Both user_id_a and user_id_b are required.")
    if str(user_id_a) == str(user_id_b):
        raise MessagingError("Cannot create a direct chat with yourself.")

    user_a = _get_user_or_raise(user_id_a)
    user_b = _get_user_or_raise(user_id_b)

    existing = InternalChat.objects.get_direct_chat(user_id_a, user_id_b)
    if existing is not None:
        logger.debug(
            "create_direct_chat: returning existing chat %s for users %s and %s.",
            existing.id, user_id_a, user_id_b,
        )
        return existing

    chat = InternalChat(is_group=False, created_by=user_a)
    chat.full_clean()
    chat.save()

    for user in (user_a, user_b):
        ChatParticipant.objects.create(
            chat=chat,
            user=user,
            role=ParticipantRole.MEMBER,
        )

    logger.info(
        "create_direct_chat: created chat %s between user %s and %s.",
        chat.id, user_id_a, user_id_b,
    )
    return chat


@transaction.atomic
def create_group_chat(
    *,
    creator_id: Any,
    name: str,
    member_ids: Sequence[Any],
) -> InternalChat:
    """
    Create a new group chat with the creator as OWNER and members as MEMBER.

    Args:
        creator_id: PK of the user creating the group.
        name:       Group chat name (required).
        member_ids: PKs of users to add (excluding creator — added automatically).

    Returns:
        The new InternalChat instance.

    Raises:
        UserNotFoundError: If creator or any member does not exist.
        MessagingError:    If name is empty or member_ids is invalid.
    """
    if not name or not isinstance(name, str) or not name.strip():
        raise MessagingError("Group chat name must be a non-empty string.")
    if not isinstance(member_ids, (list, tuple, set)):
        raise MessagingError("member_ids must be a list, tuple, or set.")

    creator = _get_user_or_raise(creator_id)

    # Validate all member users exist before touching the DB
    unique_member_ids = list(set(str(m) for m in member_ids if str(m) != str(creator_id)))
    members = []
    for mid in unique_member_ids:
        members.append(_get_user_or_raise(mid))

    chat = InternalChat(name=name.strip(), is_group=True, created_by=creator)
    chat.full_clean()
    chat.save()

    ChatParticipant.objects.create(
        chat=chat, user=creator, role=ParticipantRole.OWNER
    )
    for member in members:
        ChatParticipant.objects.create(
            chat=chat, user=member, role=ParticipantRole.MEMBER
        )

    logger.info(
        "create_group_chat: created group '%s' (id=%s) by creator=%s with %d members.",
        chat.name, chat.id, creator_id, len(members),
    )
    return chat


@transaction.atomic
def send_chat_message(
    *,
    chat_id: Any,
    sender_id: Any,
    content: str,
    message_type: str = MessageType.TEXT,
    attachments: Optional[list] = None,
    reply_to_id: Optional[Any] = None,
    metadata: Optional[dict] = None,
) -> ChatMessage:
    """
    Send a message to an InternalChat.

    Args:
        chat_id:       PK of the target chat.
        sender_id:     PK of the sending user.
        content:       Message text (required for TEXT messages).
        message_type:  One of MessageType choices.
        attachments:   List of attachment dicts (optional).
        reply_to_id:   PK of the message being replied to (optional).
        metadata:      Arbitrary extra data.

    Returns:
        The saved ChatMessage instance.

    Raises:
        ChatNotFoundError:     If chat_id does not exist.
        ChatAccessDeniedError: If sender is not a participant.
        ChatArchivedError:     If the chat is not ACTIVE.
        RateLimitError:        If the sender is sending too fast.
        MessagingError:        On other validation failures.
    """
    if message_type not in MessageType.values:
        raise MessagingError(
            f"Invalid message_type '{message_type}'. Valid: {MessageType.values}"
        )

    chat = _get_chat_or_raise(chat_id)
    chat.assert_active()

    sender = _get_user_or_raise(sender_id)
    _assert_chat_participant(chat, sender_id)
    _check_message_rate_limit(sender_id)

    if message_type == MessageType.TEXT:
        if not content or not content.strip():
            raise MessagingError("content must not be empty for TEXT messages.")
        if len(content) > MAX_MESSAGE_LENGTH:
            raise MessagingError(
                f"content exceeds max length of {MAX_MESSAGE_LENGTH}."
            )

    reply_to = None
    if reply_to_id is not None:
        try:
            reply_to = ChatMessage.objects.get(pk=reply_to_id, chat=chat)
        except ChatMessage.DoesNotExist:
            raise MessageNotFoundError(
                f"Reply-to message pk={reply_to_id!r} not found in chat {chat_id}."
            )
        if reply_to.is_deleted:
            raise MessageDeletedError(
                f"Cannot reply to a deleted message (id={reply_to_id})."
            )

    message = ChatMessage(
        chat=chat,
        sender=sender,
        content=(content or "").strip(),
        message_type=message_type,
        attachments=attachments if isinstance(attachments, list) else [],
        reply_to=reply_to,
        metadata=metadata if isinstance(metadata, dict) else {},
    )
    message.full_clean()
    message.save()

    # Update chat's last_message_at
    chat.touch()

    # Fan-out to UserInbox for all participants (excluding sender)
    _fanout_message_to_inboxes(message=message, chat=chat, sender_id=sender_id)

    logger.info(
        "send_chat_message: message %s sent to chat %s by user %s.",
        message.id, chat_id, sender_id,
    )
    return message


def _fanout_message_to_inboxes(
    *, message: ChatMessage, chat: InternalChat, sender_id: Any
) -> None:
    """
    Create UserInbox items for all participants except the sender.
    Errors here are logged but do NOT abort the message send.
    """
    participants = ChatParticipant.objects.filter(
        chat=chat, left_at__isnull=True, is_muted=False
    ).exclude(user_id=sender_id).values_list("user_id", flat=True)

    preview = (message.content[:100] + "...") if len(message.content) > 100 else message.content
    inbox_items = [
        UserInbox(
            user_id=uid,
            item_type=InboxItemType.CHAT_MESSAGE,
            source_id=message.id,
            title=chat.name or "Direct Message",
            preview=preview,
        )
        for uid in participants
    ]
    try:
        UserInbox.objects.bulk_create(inbox_items, ignore_conflicts=True)
    except Exception as exc:
        logger.error(
            "_fanout_message_to_inboxes: failed for message %s: %s", message.id, exc
        )


def get_chat_messages(
    *,
    chat_id: Any,
    requester_id: Any,
    limit: int = DEFAULT_PAGE_SIZE,
    before_id: Optional[Any] = None,
) -> list[ChatMessage]:
    """
    Retrieve paginated visible messages from a chat (cursor-based, oldest-first).

    Args:
        chat_id:      PK of the chat.
        requester_id: PK of the requesting user (access check).
        limit:        Max messages to return (capped at MAX_MESSAGES_FETCH).
        before_id:    If set, fetch messages before this message's created_at.

    Returns:
        Ordered list of ChatMessage instances.

    Raises:
        ChatNotFoundError:     If chat does not exist.
        ChatAccessDeniedError: If requester is not a participant.
        MessagingError:        On invalid arguments.
    """
    if not isinstance(limit, int) or limit < 1:
        raise MessagingError(f"limit must be a positive integer, got {limit!r}.")
    limit = min(limit, MAX_MESSAGES_FETCH)

    chat = _get_chat_or_raise(chat_id)
    _assert_chat_participant(chat, requester_id)

    qs = ChatMessage.objects.for_chat(chat_id).with_sender().select_related("reply_to")

    if before_id is not None:
        try:
            anchor = ChatMessage.objects.get(pk=before_id, chat_id=chat_id)
            qs = qs.filter(created_at__lt=anchor.created_at)
        except ChatMessage.DoesNotExist:
            raise MessageNotFoundError(
                f"Cursor message pk={before_id!r} not found in chat {chat_id}."
            )

    return list(qs.order_by("-created_at")[:limit])


@transaction.atomic
def delete_chat_message(
    *, message_id: Any, requester_id: Any
) -> ChatMessage:
    """
    Soft-delete a chat message. Only the sender or a staff user may delete.

    Args:
        message_id:   PK of the message.
        requester_id: PK of the requesting user.

    Returns:
        The updated (deleted) ChatMessage.

    Raises:
        MessageNotFoundError:  If message does not exist.
        ChatAccessDeniedError: If requester is not the sender or staff.
        MessageDeletedError:   If already deleted.
    """
    try:
        message = ChatMessage.objects.select_for_update().get(pk=message_id)
    except ChatMessage.DoesNotExist:
        raise MessageNotFoundError(f"ChatMessage pk={message_id!r} does not exist.")

    if message.is_deleted:
        raise MessageDeletedError(f"ChatMessage {message_id} is already deleted.")

    requester = _get_user_or_raise(requester_id)
    is_sender = str(message.sender_id) == str(requester_id)
    if not is_sender and not requester.is_staff:
        raise ChatAccessDeniedError(
            f"User pk={requester_id!r} is not allowed to delete message {message_id}."
        )

    message.soft_delete(deleted_by_id=requester_id)
    logger.info("delete_chat_message: message %s deleted by user %s.", message_id, requester_id)
    return message


# ---------------------------------------------------------------------------
# AdminBroadcast Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_broadcast(
    *,
    creator_id: Any,
    title: str,
    body: str,
    audience_type: str = BroadcastAudienceType.ALL_USERS,
    audience_filter: Optional[dict] = None,
    scheduled_at: Optional[Any] = None,
    metadata: Optional[dict] = None,
) -> AdminBroadcast:
    """
    Create a new AdminBroadcast in DRAFT status.

    Args:
        creator_id:      PK of the admin creating the broadcast.
        title:           Broadcast title.
        body:            Broadcast body (markdown/plain text).
        audience_type:   One of BroadcastAudienceType choices.
        audience_filter: Optional filter criteria dict.
        scheduled_at:    Optional future datetime for scheduled sending.
        metadata:        Arbitrary extra data.

    Returns:
        The saved AdminBroadcast.

    Raises:
        UserNotFoundError: If creator_id does not exist.
        MessagingError:    On validation failures.
    """
    if not title or not isinstance(title, str) or not title.strip():
        raise MessagingError("title must be a non-empty string.")
    if not body or not isinstance(body, str) or not body.strip():
        raise MessagingError("body must be a non-empty string.")
    if audience_type not in BroadcastAudienceType.values:
        raise MessagingError(
            f"Invalid audience_type '{audience_type}'. Valid: {BroadcastAudienceType.values}"
        )
    if scheduled_at is not None:
        if scheduled_at <= timezone.now():
            raise MessagingError("scheduled_at must be in the future.")

    creator = _get_user_or_raise(creator_id)
    if not creator.is_staff:
        raise MessagingError(
            f"User pk={creator_id!r} is not a staff user and cannot create broadcasts."
        )

    broadcast = AdminBroadcast(
        title=title.strip(),
        body=body.strip(),
        audience_type=audience_type,
        audience_filter=audience_filter if isinstance(audience_filter, dict) else {},
        scheduled_at=scheduled_at,
        metadata=metadata if isinstance(metadata, dict) else {},
        created_by=creator,
        status=BroadcastStatus.DRAFT,
    )
    broadcast.full_clean()
    broadcast.save()

    logger.info(
        "create_broadcast: id=%s title=%r by creator=%s audience=%s.",
        broadcast.id, broadcast.title, creator_id, audience_type,
    )
    return broadcast


@transaction.atomic
def send_broadcast(broadcast_id: Any, *, actor_id: Optional[Any] = None) -> dict:
    """
    Dispatch an AdminBroadcast to its target audience.

    This function:
    1. Transitions broadcast to SENDING.
    2. Resolves the target User queryset.
    3. Bulk-creates UserInbox records in batches.
    4. Transitions to SENT.

    Args:
        broadcast_id: PK of the AdminBroadcast.
        actor_id:     PK of the user triggering the send (for logging).

    Returns:
        Dict with "recipient_count" and "delivered_count".

    Raises:
        BroadcastNotFoundError: If broadcast_id does not exist.
        BroadcastStateError:    If the broadcast is not in a sendable state.
        BroadcastSendError:     On delivery failure.
    """
    try:
        broadcast = AdminBroadcast.objects.select_for_update().get(pk=broadcast_id)
    except AdminBroadcast.DoesNotExist:
        raise BroadcastNotFoundError(
            f"AdminBroadcast pk={broadcast_id!r} does not exist."
        )

    sendable_states = [BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED]
    if broadcast.status not in sendable_states:
        raise BroadcastStateError(
            f"Cannot send AdminBroadcast in status '{broadcast.status}'. "
            f"Sendable states: {sendable_states}"
        )

    broadcast.transition_to(BroadcastStatus.SENDING, actor=actor_id)

    # Resolve audience
    try:
        recipients_qs = _resolve_broadcast_audience(broadcast)
        recipient_ids = list(recipients_qs.values_list("pk", flat=True))
    except Exception as exc:
        broadcast.mark_failed(f"Audience resolution failed: {exc}")
        raise BroadcastSendError(
            f"Failed to resolve audience for broadcast {broadcast_id}: {exc}"
        ) from exc

    if not recipient_ids:
        logger.warning(
            "send_broadcast: broadcast %s has 0 recipients; marking sent.",
            broadcast_id,
        )
        broadcast.recipient_count = 0
        broadcast.delivered_count = 0
        AdminBroadcast.objects.filter(pk=broadcast.pk).update(
            recipient_count=0, delivered_count=0
        )
        broadcast.transition_to(BroadcastStatus.SENT, actor=actor_id)
        return {"recipient_count": 0, "delivered_count": 0}

    # Bulk-create inbox records
    preview = (broadcast.body[:100] + "...") if len(broadcast.body) > 100 else broadcast.body
    delivered = 0
    batch_size = MAX_BATCH_BROADCAST_SIZE

    try:
        for i in range(0, len(recipient_ids), batch_size):
            batch = recipient_ids[i: i + batch_size]
            inbox_items = [
                UserInbox(
                    user_id=uid,
                    item_type=InboxItemType.BROADCAST,
                    source_id=broadcast.id,
                    title=broadcast.title,
                    preview=preview,
                )
                for uid in batch
            ]
            created = UserInbox.objects.bulk_create(
                inbox_items, ignore_conflicts=True
            )
            delivered += len(created)
    except Exception as exc:
        broadcast.mark_failed(f"Delivery error: {exc}")
        raise BroadcastSendError(
            f"Error delivering broadcast {broadcast_id}: {exc}"
        ) from exc

    AdminBroadcast.objects.filter(pk=broadcast.pk).update(
        recipient_count=len(recipient_ids),
        delivered_count=delivered,
    )
    broadcast.recipient_count = len(recipient_ids)
    broadcast.delivered_count = delivered
    broadcast.transition_to(BroadcastStatus.SENT, actor=actor_id)

    logger.info(
        "send_broadcast: broadcast %s sent to %d/%d recipients.",
        broadcast_id, delivered, len(recipient_ids),
    )
    return {"recipient_count": len(recipient_ids), "delivered_count": delivered}


def _resolve_broadcast_audience(broadcast: AdminBroadcast):
    """
    Return a User queryset matching the broadcast's audience_type.
    """
    qs = User.objects.filter(is_active=True)

    if broadcast.audience_type == BroadcastAudienceType.ALL_USERS:
        return qs
    elif broadcast.audience_type == BroadcastAudienceType.ACTIVE_USERS:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        return qs.filter(last_login__gte=cutoff)
    elif broadcast.audience_type == BroadcastAudienceType.SPECIFIC_USERS:
        user_ids = broadcast.audience_filter.get("user_ids", [])
        if not isinstance(user_ids, list):
            raise BroadcastSendError("audience_filter.user_ids must be a list.")
        return qs.filter(pk__in=user_ids)
    elif broadcast.audience_type == BroadcastAudienceType.USER_GROUP:
        group_name = broadcast.audience_filter.get("group", "")
        if not group_name:
            raise BroadcastSendError("audience_filter.group must be set for USER_GROUP audience.")
        return qs.filter(groups__name=group_name)
    else:
        raise BroadcastSendError(
            f"Unhandled audience_type '{broadcast.audience_type}'."
        )


# ---------------------------------------------------------------------------
# SupportThread Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_support_thread(
    *,
    user_id: Any,
    subject: str,
    initial_message: str,
    priority: str = SupportThreadPriority.NORMAL,
    metadata: Optional[dict] = None,
) -> SupportThread:
    """
    Create a new support thread and post the user's opening message.

    Args:
        user_id:         PK of the user raising the thread.
        subject:         Thread subject line.
        initial_message: First message body.
        priority:        Initial priority (default: NORMAL).
        metadata:        Arbitrary extra data.

    Returns:
        The new SupportThread instance.

    Raises:
        UserNotFoundError:       If user_id does not exist.
        SupportThreadLimitError: If user has too many open threads.
        MessagingError:          On validation failures.
    """
    if not subject or not isinstance(subject, str) or not subject.strip():
        raise MessagingError("subject must be a non-empty string.")
    if not initial_message or not isinstance(initial_message, str) or not initial_message.strip():
        raise MessagingError("initial_message must be a non-empty string.")
    if priority not in SupportThreadPriority.values:
        raise MessagingError(
            f"Invalid priority '{priority}'. Valid: {SupportThreadPriority.values}"
        )

    user = _get_user_or_raise(user_id)

    # Enforce open thread limit
    open_count = SupportThread.objects.for_user(user_id).active().count()
    if open_count >= MAX_SUPPORT_THREADS_PER_USER:
        raise SupportThreadLimitError(
            f"User pk={user_id!r} already has {open_count} open support threads. "
            f"Maximum is {MAX_SUPPORT_THREADS_PER_USER}."
        )

    thread = SupportThread(
        user=user,
        subject=subject.strip(),
        priority=priority,
        metadata=metadata if isinstance(metadata, dict) else {},
    )
    thread.full_clean()
    thread.save()

    # Post opening message
    SupportMessage.objects.create(
        thread=thread,
        sender=user,
        content=initial_message.strip(),
        is_agent_reply=False,
    )

    thread.last_reply_at = timezone.now()
    SupportThread.objects.filter(pk=thread.pk).update(last_reply_at=thread.last_reply_at)

    logger.info(
        "create_support_thread: thread %s created by user=%s subject=%r.",
        thread.id, user_id, subject,
    )
    return thread


@transaction.atomic
def reply_to_support_thread(
    *,
    thread_id: Any,
    sender_id: Any,
    content: str,
    attachments: Optional[list] = None,
    is_internal_note: bool = False,
) -> SupportMessage:
    """
    Post a reply to an existing SupportThread.

    Args:
        thread_id:        PK of the thread.
        sender_id:        PK of the user or agent replying.
        content:          Reply content.
        attachments:      List of attachment dicts (optional).
        is_internal_note: If True, only agents can see this message.

    Returns:
        The new SupportMessage.

    Raises:
        SupportThreadNotFoundError: If thread_id does not exist.
        SupportThreadClosedError:   If the thread is closed.
        MessagingError:             On validation failures.
    """
    if not content or not isinstance(content, str) or not content.strip():
        raise MessagingError("content must be a non-empty string.")

    try:
        thread = SupportThread.objects.select_for_update().get(pk=thread_id)
    except SupportThread.DoesNotExist:
        raise SupportThreadNotFoundError(
            f"SupportThread pk={thread_id!r} does not exist."
        )

    thread.assert_open_for_reply()
    sender = _get_user_or_raise(sender_id)
    is_agent = sender.is_staff

    # Non-staff users cannot post internal notes
    if is_internal_note and not is_agent:
        raise MessagingError("Only agents can post internal notes.")

    msg = SupportMessage(
        thread=thread,
        sender=sender,
        content=content.strip(),
        is_agent_reply=is_agent,
        attachments=attachments if isinstance(attachments, list) else [],
        is_internal_note=is_internal_note,
    )
    msg.full_clean()
    msg.save()

    # Update thread state
    now = timezone.now()
    update_kwargs: dict = {"last_reply_at": now}

    if is_agent and thread.status == SupportThreadStatus.OPEN:
        update_kwargs["status"] = SupportThreadStatus.IN_PROGRESS
        thread.status = SupportThreadStatus.IN_PROGRESS
    elif not is_agent and thread.status == SupportThreadStatus.WAITING_USER:
        update_kwargs["status"] = SupportThreadStatus.IN_PROGRESS
        thread.status = SupportThreadStatus.IN_PROGRESS

    SupportThread.objects.filter(pk=thread.pk).update(**update_kwargs)

    # Notify user if agent replied
    if is_agent and not is_internal_note:
        _create_inbox_item(
            user_id=thread.user_id,
            item_type=InboxItemType.SUPPORT_REPLY,
            source_id=msg.id,
            title=f"Support: {thread.subject}",
            preview=content[:100],
        )

    logger.info(
        "reply_to_support_thread: message %s posted in thread %s by user=%s (agent=%s).",
        msg.id, thread_id, sender_id, is_agent,
    )
    return msg


@transaction.atomic
def assign_support_thread(
    *, thread_id: Any, agent_id: Any
) -> SupportThread:
    """
    Assign a SupportThread to an agent.

    Args:
        thread_id: PK of the thread.
        agent_id:  PK of the staff user to assign.

    Returns:
        The updated SupportThread.

    Raises:
        SupportThreadNotFoundError: If thread_id does not exist.
        MessagingError:             If agent_id is not a staff user.
    """
    try:
        thread = SupportThread.objects.select_for_update().get(pk=thread_id)
    except SupportThread.DoesNotExist:
        raise SupportThreadNotFoundError(
            f"SupportThread pk={thread_id!r} does not exist."
        )

    agent = _get_user_or_raise(agent_id)
    if not agent.is_staff:
        raise MessagingError(
            f"User pk={agent_id!r} is not a staff user and cannot be assigned to support threads."
        )

    SupportThread.objects.filter(pk=thread.pk).update(
        assigned_agent=agent, updated_at=timezone.now()
    )
    thread.assigned_agent = agent

    logger.info(
        "assign_support_thread: thread %s assigned to agent=%s.",
        thread_id, agent_id,
    )
    return thread


# ---------------------------------------------------------------------------
# UserInbox Services
# ---------------------------------------------------------------------------

def _create_inbox_item(
    *,
    user_id: Any,
    item_type: str,
    source_id: Any,
    title: str = "",
    preview: str = "",
    metadata: Optional[dict] = None,
) -> UserInbox:
    """Internal helper to create a single UserInbox record. Non-atomic."""
    try:
        return UserInbox.objects.create(
            user_id=user_id,
            item_type=item_type,
            source_id=source_id,
            title=(title or "")[:255],
            preview=(preview or "")[:200],
            metadata=metadata if isinstance(metadata, dict) else {},
        )
    except Exception as exc:
        logger.error(
            "_create_inbox_item: failed for user=%s type=%s: %s", user_id, item_type, exc
        )
        raise


@transaction.atomic
def mark_inbox_items_read(
    *, user_id: Any, item_ids: list[Any]
) -> int:
    """
    Mark a list of inbox items as read for a user.

    Args:
        user_id:  PK of the user.
        item_ids: List of UserInbox PKs.

    Returns:
        Number of records actually updated.

    Raises:
        UserNotFoundError: If user_id does not exist.
        MessagingError:    If item_ids is not a list or is empty.
    """
    _get_user_or_raise(user_id)

    if not isinstance(item_ids, list):
        raise MessagingError(
            f"item_ids must be a list, got {type(item_ids).__name__}."
        )
    if not item_ids:
        raise MessagingError("item_ids must not be empty.")

    updated = UserInbox.objects.bulk_mark_read(user_id=user_id, item_ids=item_ids)
    logger.info(
        "mark_inbox_items_read: %d items marked read for user=%s.", updated, user_id
    )
    return updated


def get_unread_count(user_id: Any) -> int:
    """
    Return the total unread inbox item count for a user.

    Args:
        user_id: PK of the user.

    Returns:
        Integer unread count (0 if none).

    Raises:
        UserNotFoundError: If user_id does not exist.
    """
    _get_user_or_raise(user_id)
    count = UserInbox.objects.unread_count(user_id)
    logger.debug("get_unread_count: user=%s → %d unread.", user_id, count)
    return count
