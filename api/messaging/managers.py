"""
Messaging Managers — Custom QuerySet and Manager classes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import models
from django.db.models import QuerySet, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# InternalChat
# ---------------------------------------------------------------------------

class InternalChatQuerySet(models.QuerySet):

    def active(self) -> "InternalChatQuerySet":
        from .choices import ChatStatus
        return self.filter(status=ChatStatus.ACTIVE)

    def archived(self) -> "InternalChatQuerySet":
        from .choices import ChatStatus
        return self.filter(status=ChatStatus.ARCHIVED)

    def not_deleted(self) -> "InternalChatQuerySet":
        from .choices import ChatStatus
        return self.exclude(status=ChatStatus.DELETED)

    def for_user(self, user_id: Any) -> "InternalChatQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(participants__user_id=user_id)

    def direct_chats(self) -> "InternalChatQuerySet":
        return self.filter(is_group=False)

    def group_chats(self) -> "InternalChatQuerySet":
        return self.filter(is_group=True)

    def with_participants(self) -> "InternalChatQuerySet":
        return self.prefetch_related("participants__user")

    def with_last_message(self) -> "InternalChatQuerySet":
        return self.order_by("-last_message_at")


class InternalChatManager(models.Manager):
    def get_queryset(self) -> InternalChatQuerySet:
        return InternalChatQuerySet(self.model, using=self._db)

    def active(self) -> InternalChatQuerySet:
        return self.get_queryset().active()

    def for_user(self, user_id: Any) -> InternalChatQuerySet:
        return self.get_queryset().for_user(user_id).not_deleted()

    def get_direct_chat(self, user_id_a: Any, user_id_b: Any) -> Optional[Any]:
        """
        Return the existing direct (non-group) chat between two users, or None.
        Uses annotation to find chats where both users are participants.
        """
        if user_id_a is None or user_id_b is None:
            raise ValueError("Both user_ids must be provided.")
        return (
            self.get_queryset()
            .filter(is_group=False)
            .not_deleted()
            .filter(participants__user_id=user_id_a)
            .filter(participants__user_id=user_id_b)
            .annotate(participant_count=Count("participants"))
            .filter(participant_count=2)
            .first()
        )


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class ChatMessageQuerySet(models.QuerySet):

    def visible(self) -> "ChatMessageQuerySet":
        from .choices import MessageStatus
        return self.exclude(status=MessageStatus.DELETED)

    def for_chat(self, chat_id: Any) -> "ChatMessageQuerySet":
        if chat_id is None:
            raise ValueError("chat_id must not be None.")
        return self.filter(chat_id=chat_id)

    def unread_for_user(self, user_id: Any, last_read_at: Any) -> "ChatMessageQuerySet":
        """Messages sent after user's last_read_at timestamp."""
        if last_read_at is None:
            return self
        return self.filter(created_at__gt=last_read_at).exclude(sender_id=user_id)

    def with_sender(self) -> "ChatMessageQuerySet":
        return self.select_related("sender")


class ChatMessageManager(models.Manager):
    def get_queryset(self) -> ChatMessageQuerySet:
        return ChatMessageQuerySet(self.model, using=self._db)

    def visible(self) -> ChatMessageQuerySet:
        return self.get_queryset().visible()

    def for_chat(self, chat_id: Any) -> ChatMessageQuerySet:
        return self.get_queryset().for_chat(chat_id).visible().order_by("created_at")


# ---------------------------------------------------------------------------
# AdminBroadcast
# ---------------------------------------------------------------------------

class AdminBroadcastQuerySet(models.QuerySet):

    def draft(self) -> "AdminBroadcastQuerySet":
        from .choices import BroadcastStatus
        return self.filter(status=BroadcastStatus.DRAFT)

    def scheduled(self) -> "AdminBroadcastQuerySet":
        from .choices import BroadcastStatus
        return self.filter(status=BroadcastStatus.SCHEDULED)

    def due_for_sending(self) -> "AdminBroadcastQuerySet":
        """Scheduled broadcasts whose scheduled_at has passed."""
        from .choices import BroadcastStatus
        return self.filter(
            status=BroadcastStatus.SCHEDULED,
            scheduled_at__lte=timezone.now(),
        )

    def sent(self) -> "AdminBroadcastQuerySet":
        from .choices import BroadcastStatus
        return self.filter(status=BroadcastStatus.SENT)

    def failed(self) -> "AdminBroadcastQuerySet":
        from .choices import BroadcastStatus
        return self.filter(status=BroadcastStatus.FAILED)

    def by_creator(self, user_id: Any) -> "AdminBroadcastQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(created_by_id=user_id)


class AdminBroadcastManager(models.Manager):
    def get_queryset(self) -> AdminBroadcastQuerySet:
        return AdminBroadcastQuerySet(self.model, using=self._db)

    def draft(self) -> AdminBroadcastQuerySet:
        return self.get_queryset().draft()

    def due_for_sending(self) -> AdminBroadcastQuerySet:
        return self.get_queryset().due_for_sending()

    def sent(self) -> AdminBroadcastQuerySet:
        return self.get_queryset().sent()


# ---------------------------------------------------------------------------
# SupportThread
# ---------------------------------------------------------------------------

class SupportThreadQuerySet(models.QuerySet):

    def open(self) -> "SupportThreadQuerySet":
        from .choices import SupportThreadStatus
        return self.filter(status=SupportThreadStatus.OPEN)

    def in_progress(self) -> "SupportThreadQuerySet":
        from .choices import SupportThreadStatus
        return self.filter(status=SupportThreadStatus.IN_PROGRESS)

    def closed(self) -> "SupportThreadQuerySet":
        from .choices import SupportThreadStatus
        return self.filter(status=SupportThreadStatus.CLOSED)

    def active(self) -> "SupportThreadQuerySet":
        """Threads that can still receive replies (not closed)."""
        from .choices import SupportThreadStatus
        return self.exclude(status=SupportThreadStatus.CLOSED)

    def for_user(self, user_id: Any) -> "SupportThreadQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(user_id=user_id)

    def for_agent(self, agent_id: Any) -> "SupportThreadQuerySet":
        if agent_id is None:
            raise ValueError("agent_id must not be None.")
        return self.filter(assigned_agent_id=agent_id)

    def unassigned(self) -> "SupportThreadQuerySet":
        return self.filter(assigned_agent__isnull=True)

    def by_priority(self, priority: str) -> "SupportThreadQuerySet":
        return self.filter(priority=priority)

    def urgent(self) -> "SupportThreadQuerySet":
        from .choices import SupportThreadPriority
        return self.filter(priority=SupportThreadPriority.URGENT)

    def with_messages(self) -> "SupportThreadQuerySet":
        return self.prefetch_related("messages__sender")


class SupportThreadManager(models.Manager):
    def get_queryset(self) -> SupportThreadQuerySet:
        return SupportThreadQuerySet(self.model, using=self._db)

    def open(self) -> SupportThreadQuerySet:
        return self.get_queryset().open()

    def for_user(self, user_id: Any) -> SupportThreadQuerySet:
        return self.get_queryset().for_user(user_id)

    def unassigned_open(self) -> SupportThreadQuerySet:
        return self.get_queryset().open().unassigned().order_by("-priority", "created_at")


# ---------------------------------------------------------------------------
# UserInbox
# ---------------------------------------------------------------------------

class UserInboxQuerySet(models.QuerySet):

    def for_user(self, user_id: Any) -> "UserInboxQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(user_id=user_id)

    def unread(self) -> "UserInboxQuerySet":
        return self.filter(is_read=False)

    def read(self) -> "UserInboxQuerySet":
        return self.filter(is_read=True)

    def not_archived(self) -> "UserInboxQuerySet":
        return self.filter(is_archived=False)

    def of_type(self, item_type: str) -> "UserInboxQuerySet":
        if not item_type:
            raise ValueError("item_type must not be empty.")
        return self.filter(item_type=item_type)

    def unread_count_for_user(self, user_id: Any) -> int:
        """Fast unread count for a specific user."""
        return self.for_user(user_id).unread().not_archived().count()


class UserInboxManager(models.Manager):
    def get_queryset(self) -> UserInboxQuerySet:
        return UserInboxQuerySet(self.model, using=self._db)

    def for_user(self, user_id: Any) -> UserInboxQuerySet:
        return self.get_queryset().for_user(user_id).not_archived().order_by("-created_at")

    def unread_for_user(self, user_id: Any) -> UserInboxQuerySet:
        return self.get_queryset().for_user(user_id).unread().not_archived()

    def unread_count(self, user_id: Any) -> int:
        return self.get_queryset().unread_count_for_user(user_id)

    def bulk_mark_read(self, user_id: Any, item_ids: list) -> int:
        """
        Atomically mark multiple inbox items as read for a user.

        Returns:
            Number of records updated.
        """
        if not isinstance(item_ids, list) or not item_ids:
            return 0
        now = timezone.now()
        return (
            self.get_queryset()
            .filter(pk__in=item_ids, user_id=user_id, is_read=False)
            .update(is_read=True, read_at=now, updated_at=now)
        )
