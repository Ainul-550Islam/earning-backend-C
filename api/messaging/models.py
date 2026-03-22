"""
Messaging Models — InternalChat, AdminBroadcast, SupportThread, UserInbox.

Design principles:
- UUID primary keys throughout.
- All mutations validated in clean() before save().
- Soft-delete pattern: status=DELETED, never hard-delete user messages.
- Immutability guards on critical fields after state transitions.
- DB-level CheckConstraints and UniqueConstraints as last line of defence.
- All JSON fields have size guards in clean().
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Optional, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q, F, CheckConstraint, UniqueConstraint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    ChatStatus,
    MessageStatus,
    MessageType,
    BroadcastStatus,
    BroadcastAudienceType,
    SupportThreadStatus,
    SupportThreadPriority,
    InboxItemType,
    ParticipantRole,
)
from .constants import (
    MAX_CHAT_NAME_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_BROADCAST_TITLE_LENGTH,
    MAX_BROADCAST_BODY_LENGTH,
    MAX_SUBJECT_LENGTH,
    MAX_THREAD_NOTE_LENGTH,
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_ATTACHMENT_SIZE_BYTES,
    ALLOWED_ATTACHMENT_MIMETYPES,
)
from .exceptions import (
    ChatArchivedError,
    ChatAccessDeniedError,
    BroadcastStateError,
    SupportThreadClosedError,
)
from .managers import (
    InternalChatManager,
    AdminBroadcastManager,
    SupportThreadManager,
    UserInboxManager,
    ChatMessageManager,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
User = get_user_model()

_MAX_META_BYTES = 32_768  # 32 KB


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------

class TimestampedModel(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} id={self.id}>"

    def _validate_metadata(self, value: dict, field_name: str = "metadata") -> None:
        """Reusable metadata JSON size guard for subclasses."""
        if not isinstance(value, dict):
            raise ValidationError({field_name: [_("Must be a JSON object.")]})
        try:
            encoded = json.dumps(value).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError({field_name: [_(f"Not serialisable JSON: {exc}")]})
        if len(encoded) > _MAX_META_BYTES:
            raise ValidationError(
                {field_name: [_(f"Exceeds max {_MAX_META_BYTES} bytes.")]}
            )


# ---------------------------------------------------------------------------
# InternalChat  (peer-to-peer or group chat between users)
# ---------------------------------------------------------------------------

class InternalChat(TimestampedModel):
    """
    A conversation thread between two or more users.

    Group chats have a name; direct (1-to-1) chats leave name blank.
    Participants are tracked via ChatParticipant (separate model).
    Messages are tracked via ChatMessage.
    """

    name = models.CharField(
        max_length=MAX_CHAT_NAME_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Chat Name"),
        help_text=_("Optional name for group chats. Leave blank for direct messages."),
    )
    is_group = models.BooleanField(
        default=False,
        verbose_name=_("Is Group Chat"),
    )
    status = models.CharField(
        max_length=20,
        choices=ChatStatus.choices,
        default=ChatStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_chats",
        verbose_name=_("Created By"),
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Last Message At"),
        help_text=_("Updated whenever a new message is sent. Used for inbox ordering."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
    )

    objects: InternalChatManager = InternalChatManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Internal Chat")
        verbose_name_plural = _("Internal Chats")
        indexes = [
            models.Index(fields=["status", "last_message_at"], name="msg_ic_status_lma_idx"),
            models.Index(fields=["created_by", "status"], name="msg_ic_creator_status_idx"),
        ]

    def __str__(self) -> str:
        label = self.name if self.name else f"Chat {self.id}"
        return f"{label} [{self.get_status_display()}]"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status == ChatStatus.ACTIVE

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}
        # Group chats should have a name
        if self.is_group and not self.name.strip():
            errors.setdefault("name", []).append(
                _("Group chats must have a name.")
            )
        self._validate_metadata(self.metadata)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def archive(self) -> None:
        """Soft-archive this chat. Idempotent."""
        if self.status == ChatStatus.ARCHIVED:
            return
        if self.status == ChatStatus.DELETED:
            raise ChatArchivedError(
                f"Cannot archive a DELETED chat (id={self.id})."
            )
        self.status = ChatStatus.ARCHIVED
        InternalChat.objects.filter(pk=self.pk).update(
            status=ChatStatus.ARCHIVED, updated_at=timezone.now()
        )
        logger.info("InternalChat %s archived.", self.id)

    def soft_delete(self) -> None:
        """Mark chat as DELETED. Does not remove DB records."""
        self.status = ChatStatus.DELETED
        InternalChat.objects.filter(pk=self.pk).update(
            status=ChatStatus.DELETED, updated_at=timezone.now()
        )
        logger.info("InternalChat %s soft-deleted.", self.id)

    def assert_active(self) -> None:
        """Raise ChatArchivedError if the chat is not ACTIVE."""
        if self.status != ChatStatus.ACTIVE:
            raise ChatArchivedError(
                f"Chat id={self.id} is '{self.status}' and cannot receive messages."
            )

    def touch(self) -> None:
        """Update last_message_at to now. Called after a new message is sent."""
        now = timezone.now()
        InternalChat.objects.filter(pk=self.pk).update(
            last_message_at=now, updated_at=now
        )
        self.last_message_at = now


# ---------------------------------------------------------------------------
# ChatParticipant
# ---------------------------------------------------------------------------

class ChatParticipant(TimestampedModel):
    """
    Through-model linking Users to InternalChats with role and read-state.
    """

    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name=_("Chat"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_participations",
        verbose_name=_("User"),
    )
    role = models.CharField(
        max_length=10,
        choices=ParticipantRole.choices,
        default=ParticipantRole.MEMBER,
        verbose_name=_("Role"),
    )
    last_read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Read At"),
        help_text=_("Timestamp of last message the user has seen in this chat."),
    )
    is_muted = models.BooleanField(
        default=False,
        verbose_name=_("Is Muted"),
        help_text=_("User will not receive push notifications for this chat."),
    )
    joined_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Joined At"),
    )
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Left At"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Chat Participant")
        verbose_name_plural = _("Chat Participants")
        constraints = [
            UniqueConstraint(
                fields=["chat", "user"],
                name="msg_cp_unique_chat_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "chat"], name="msg_cp_user_chat_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in Chat {self.chat_id} [{self.role}]"

    def clean(self) -> None:
        if self.left_at and self.joined_at and self.left_at < self.joined_at:
            raise ValidationError(
                {"left_at": [_("left_at cannot be before joined_at.")]}
            )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_read(self) -> None:
        """Record that this participant has read up to now."""
        now = timezone.now()
        ChatParticipant.objects.filter(pk=self.pk).update(
            last_read_at=now, updated_at=now
        )
        self.last_read_at = now


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class ChatMessage(TimestampedModel):
    """
    A single message within an InternalChat.

    Design notes:
    - Never hard-deleted; status=DELETED replaces content with a tombstone.
    - Attachments stored as JSON array; validated in clean().
    - message_type=SYSTEM messages are injected by the server (e.g. "Alice left").
    """

    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
        verbose_name=_("Chat"),
    )
    sender = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_messages",
        verbose_name=_("Sender"),
        help_text=_("NULL for SYSTEM messages."),
    )
    content = models.TextField(
        blank=True,
        default="",
        max_length=MAX_MESSAGE_LENGTH,
        verbose_name=_("Content"),
    )
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        db_index=True,
        verbose_name=_("Message Type"),
    )
    status = models.CharField(
        max_length=10,
        choices=MessageStatus.choices,
        default=MessageStatus.SENT,
        db_index=True,
        verbose_name=_("Status"),
    )
    attachments = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Attachments"),
        help_text=_(
            "List of attachment dicts: {url, filename, mimetype, size_bytes}."
        ),
    )
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
        verbose_name=_("Reply To"),
    )
    is_edited = models.BooleanField(default=False, verbose_name=_("Is Edited"))
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Edited At"))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Deleted At"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    objects: ChatMessageManager = ChatMessageManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Chat Message")
        verbose_name_plural = _("Chat Messages")
        indexes = [
            models.Index(fields=["chat", "created_at"], name="msg_cm_chat_created_idx"),
            models.Index(fields=["sender", "created_at"], name="msg_cm_sender_created_idx"),
            models.Index(fields=["status", "created_at"], name="msg_cm_status_created_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=~Q(message_type="TEXT") | Q(content__gt=""),
                name="msg_cm_text_needs_content",
            ),
        ]

    def __str__(self) -> str:
        preview = (self.content[:40] + "...") if len(self.content) > 40 else self.content
        return f"Message [{self.message_type}] from {self.sender_id}: {preview!r}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_deleted(self) -> bool:
        return self.status == MessageStatus.DELETED

    @property
    def is_visible(self) -> bool:
        return self.status != MessageStatus.DELETED

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}

        # TEXT messages must have content
        if self.message_type == MessageType.TEXT and not (self.content or "").strip():
            errors.setdefault("content", []).append(
                _("Text messages must have non-empty content.")
            )

        # SYSTEM messages must not have a sender
        if self.message_type == MessageType.SYSTEM and self.sender_id is not None:
            errors.setdefault("sender", []).append(
                _("System messages must not have a sender.")
            )

        # Attachment validation
        if self.attachments is not None:
            if not isinstance(self.attachments, list):
                errors.setdefault("attachments", []).append(
                    _("attachments must be a JSON array.")
                )
            else:
                if len(self.attachments) > MAX_ATTACHMENTS_PER_MESSAGE:
                    errors.setdefault("attachments", []).append(
                        _(f"Cannot attach more than {MAX_ATTACHMENTS_PER_MESSAGE} files per message.")
                    )
                for idx, att in enumerate(self.attachments):
                    if not isinstance(att, dict):
                        errors.setdefault("attachments", []).append(
                            _(f"Attachment at index {idx} must be a JSON object.")
                        )
                        continue
                    for required in ("url", "filename", "mimetype", "size_bytes"):
                        if required not in att:
                            errors.setdefault("attachments", []).append(
                                _(f"Attachment {idx} missing key '{required}'.")
                            )
                    size = att.get("size_bytes", 0)
                    if isinstance(size, (int, float)) and size > MAX_ATTACHMENT_SIZE_BYTES:
                        errors.setdefault("attachments", []).append(
                            _(f"Attachment {idx} exceeds max size of {MAX_ATTACHMENT_SIZE_BYTES} bytes.")
                        )
                    mimetype = att.get("mimetype", "")
                    if mimetype and mimetype not in ALLOWED_ATTACHMENT_MIMETYPES:
                        errors.setdefault("attachments", []).append(
                            _(f"Attachment {idx} has disallowed mimetype '{mimetype}'.")
                        )

        # Edit consistency
        if self.is_edited and not self.edited_at:
            errors.setdefault("edited_at", []).append(
                _("edited_at must be set when is_edited is True.")
            )
        if self.deleted_at and self.status != MessageStatus.DELETED:
            errors.setdefault("deleted_at", []).append(
                _("deleted_at should only be set when status is DELETED.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def soft_delete(self, *, deleted_by_id: Optional[int] = None) -> None:
        """
        Soft-delete this message: replace content with tombstone text,
        clear attachments, and set status=DELETED.
        Idempotent.
        """
        if self.is_deleted:
            logger.debug("ChatMessage %s already deleted; skipping.", self.id)
            return

        now = timezone.now()
        ChatMessage.objects.filter(pk=self.pk).update(
            status=MessageStatus.DELETED,
            content="[This message was deleted]",
            attachments=[],
            deleted_at=now,
            updated_at=now,
        )
        self.status = MessageStatus.DELETED
        self.content = "[This message was deleted]"
        self.attachments = []
        self.deleted_at = now
        logger.info(
            "ChatMessage %s soft-deleted by user=%s.", self.id, deleted_by_id
        )

    def mark_edited(self, new_content: str) -> None:
        """
        Update message content and flag as edited.

        Args:
            new_content: Replacement content string.

        Raises:
            ValidationError: If new_content is empty or exceeds max length.
        """
        if self.is_deleted:
            raise ValidationError(
                {"content": [_("Cannot edit a deleted message.")]}
            )
        if not new_content or not new_content.strip():
            raise ValidationError(
                {"content": [_("Edited content must not be empty.")]}
            )
        if len(new_content) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                {"content": [_(f"Content exceeds maximum length of {MAX_MESSAGE_LENGTH}.")]}
            )

        now = timezone.now()
        ChatMessage.objects.filter(pk=self.pk).update(
            content=new_content.strip(),
            is_edited=True,
            edited_at=now,
            updated_at=now,
        )
        self.content = new_content.strip()
        self.is_edited = True
        self.edited_at = now
        logger.debug("ChatMessage %s edited.", self.id)


# ---------------------------------------------------------------------------
# AdminBroadcast
# ---------------------------------------------------------------------------

class AdminBroadcast(TimestampedModel):
    """
    A message broadcast by an admin to a large audience.

    State machine:
        DRAFT → SCHEDULED → SENDING → SENT
                         ↘ FAILED
        DRAFT → CANCELLED
        SCHEDULED → CANCELLED

    The broadcast stores a snapshot of the recipient count at send time
    in `recipient_count`. Actual delivery tracking is in UserInbox records.
    """

    VALID_TRANSITIONS: dict[str, list[str]] = {
        BroadcastStatus.DRAFT: [BroadcastStatus.SCHEDULED, BroadcastStatus.SENDING, BroadcastStatus.CANCELLED],
        BroadcastStatus.SCHEDULED: [BroadcastStatus.SENDING, BroadcastStatus.CANCELLED],
        BroadcastStatus.SENDING: [BroadcastStatus.SENT, BroadcastStatus.FAILED],
        BroadcastStatus.SENT: [],
        BroadcastStatus.FAILED: [BroadcastStatus.DRAFT],  # allow retry from FAILED
        BroadcastStatus.CANCELLED: [],
    }

    title = models.CharField(
        max_length=MAX_BROADCAST_TITLE_LENGTH,
        verbose_name=_("Title"),
    )
    body = models.TextField(
        max_length=MAX_BROADCAST_BODY_LENGTH,
        verbose_name=_("Body"),
        help_text=_("Markdown or plain text body of the broadcast."),
    )
    status = models.CharField(
        max_length=15,
        choices=BroadcastStatus.choices,
        default=BroadcastStatus.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
    )
    audience_type = models.CharField(
        max_length=20,
        choices=BroadcastAudienceType.choices,
        default=BroadcastAudienceType.ALL_USERS,
        verbose_name=_("Audience Type"),
    )
    audience_filter = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Audience Filter"),
        help_text=_("Optional filter criteria for ACTIVE_USERS or USER_GROUP audience types."),
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Scheduled At"),
        help_text=_("If set, the broadcast will be sent at this UTC datetime."),
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent At"),
    )
    recipient_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Recipient Count"),
        help_text=_("Snapshot of delivery target count at send time."),
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Delivered Count"),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_broadcasts",
        verbose_name=_("Created By"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
    )

    objects: AdminBroadcastManager = AdminBroadcastManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Admin Broadcast")
        verbose_name_plural = _("Admin Broadcasts")
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="msg_ab_status_sched_idx"),
            models.Index(fields=["created_by", "status"], name="msg_ab_creator_status_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=Q(delivered_count__lte=F("recipient_count")) | Q(recipient_count=0),
                name="msg_ab_delivered_lte_rcpt",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.get_status_display()}]"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def delivery_rate(self) -> Optional[float]:
        """Delivery percentage (0.0–100.0), or None if not yet sent."""
        if self.recipient_count == 0:
            return None
        return round((self.delivered_count / self.recipient_count) * 100, 2)

    @property
    def is_editable(self) -> bool:
        return self.status in (BroadcastStatus.DRAFT, BroadcastStatus.FAILED)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}

        if not self.title or not self.title.strip():
            errors.setdefault("title", []).append(_("title must not be empty."))

        if not self.body or not self.body.strip():
            errors.setdefault("body", []).append(_("body must not be empty."))

        if self.scheduled_at and self.status == BroadcastStatus.SCHEDULED:
            if self.scheduled_at <= timezone.now():
                errors.setdefault("scheduled_at", []).append(
                    _("scheduled_at must be in the future.")
                )

        self._validate_metadata(self.audience_filter, "audience_filter")
        self._validate_metadata(self.metadata)

        if errors:
            raise ValidationError(errors)

    def _validate_metadata(self, value: dict, field_name: str = "metadata") -> None:
        import json as _json
        if not isinstance(value, dict):
            raise ValidationError({field_name: [_("Must be a JSON object.")]})
        try:
            encoded = _json.dumps(value).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError({field_name: [_(f"Not serialisable: {exc}")]})
        if len(encoded) > _MAX_META_BYTES:
            raise ValidationError({field_name: [_(f"Exceeds max {_MAX_META_BYTES} bytes.")]})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition_to(self, new_status: str, *, actor=None) -> None:
        """
        Advance the broadcast to *new_status*.

        Raises:
            BroadcastStateError: If the transition is not permitted.
        """
        if new_status not in BroadcastStatus.values:
            raise BroadcastStateError(
                f"Unknown broadcast status '{new_status}'."
            )
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise BroadcastStateError(
                f"Cannot transition AdminBroadcast from '{self.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        old = self.status
        self.status = new_status

        update_fields = ["status", "updated_at"]
        if new_status == BroadcastStatus.SENT:
            self.sent_at = timezone.now()
            update_fields.append("sent_at")

        AdminBroadcast.objects.filter(pk=self.pk).update(
            **{f: getattr(self, f) for f in update_fields}
        )
        logger.info(
            "AdminBroadcast %s: %s → %s (actor=%s)",
            self.id, old, new_status, getattr(actor, "pk", "system"),
        )

    def mark_failed(self, error: str) -> None:
        """Transition to FAILED with an error message."""
        if not isinstance(error, str) or not error.strip():
            error = "Unknown error."
        self.error_message = error[:4096]
        self.status = BroadcastStatus.FAILED
        AdminBroadcast.objects.filter(pk=self.pk).update(
            status=BroadcastStatus.FAILED,
            error_message=self.error_message,
            updated_at=timezone.now(),
        )
        logger.error("AdminBroadcast %s FAILED: %s", self.id, error)


# ---------------------------------------------------------------------------
# SupportThread
# ---------------------------------------------------------------------------

class SupportThread(TimestampedModel):
    """
    A user-initiated support conversation with the admin/support team.

    - Users create threads; agents respond.
    - Priority can be escalated by agents.
    - Threads go through: OPEN → IN_PROGRESS → WAITING_USER → RESOLVED → CLOSED
    - Messages are stored in SupportMessage (separate model).
    """

    AGENT_TRANSITIONS: dict[str, list[str]] = {
        SupportThreadStatus.OPEN: [SupportThreadStatus.IN_PROGRESS, SupportThreadStatus.CLOSED],
        SupportThreadStatus.IN_PROGRESS: [
            SupportThreadStatus.WAITING_USER,
            SupportThreadStatus.RESOLVED,
            SupportThreadStatus.CLOSED,
        ],
        SupportThreadStatus.WAITING_USER: [
            SupportThreadStatus.IN_PROGRESS,
            SupportThreadStatus.RESOLVED,
            SupportThreadStatus.CLOSED,
        ],
        SupportThreadStatus.RESOLVED: [SupportThreadStatus.OPEN, SupportThreadStatus.CLOSED],
        SupportThreadStatus.CLOSED: [],
    }

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="support_threads",
        db_index=True,
        verbose_name=_("User"),
    )
    assigned_agent = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_threads",
        verbose_name=_("Assigned Agent"),
    )
    subject = models.CharField(
        max_length=MAX_SUBJECT_LENGTH,
        verbose_name=_("Subject"),
    )
    status = models.CharField(
        max_length=15,
        choices=SupportThreadStatus.choices,
        default=SupportThreadStatus.OPEN,
        db_index=True,
        verbose_name=_("Status"),
    )
    priority = models.CharField(
        max_length=10,
        choices=SupportThreadPriority.choices,
        default=SupportThreadPriority.NORMAL,
        db_index=True,
        verbose_name=_("Priority"),
    )
    last_reply_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Last Reply At"),
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Resolved At"),
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Closed At"),
    )
    agent_note = models.TextField(
        blank=True,
        default="",
        max_length=MAX_THREAD_NOTE_LENGTH,
        verbose_name=_("Agent Note"),
        help_text=_("Internal note visible only to support agents."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
    )

    objects: SupportThreadManager = SupportThreadManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Support Thread")
        verbose_name_plural = _("Support Threads")
        indexes = [
            models.Index(fields=["user", "status"], name="msg_st_user_status_idx"),
            models.Index(fields=["status", "priority"], name="msg_st_status_priority_idx"),
            models.Index(fields=["assigned_agent", "status"], name="msg_st_agent_status_idx"),
            models.Index(fields=["last_reply_at"], name="msg_st_last_reply_idx"),
        ]

    def __str__(self) -> str:
        return f"Support: {self.subject[:50]} [{self.get_status_display()}] (user={self.user_id})"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self.status == SupportThreadStatus.CLOSED

    @property
    def is_resolved(self) -> bool:
        return self.status == SupportThreadStatus.RESOLVED

    @property
    def is_open_for_reply(self) -> bool:
        return self.status not in (SupportThreadStatus.CLOSED,)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}

        if not self.subject or not self.subject.strip():
            errors.setdefault("subject", []).append(_("subject must not be empty."))

        if self.resolved_at and self.status not in (
            SupportThreadStatus.RESOLVED, SupportThreadStatus.CLOSED
        ):
            errors.setdefault("resolved_at", []).append(
                _("resolved_at should only be set when status is RESOLVED or CLOSED.")
            )

        if self.closed_at and self.status != SupportThreadStatus.CLOSED:
            errors.setdefault("closed_at", []).append(
                _("closed_at should only be set when status is CLOSED.")
            )

        self._validate_metadata(self.metadata)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def assert_open_for_reply(self) -> None:
        """Raise SupportThreadClosedError if not open for new messages."""
        if not self.is_open_for_reply:
            raise SupportThreadClosedError(
                f"SupportThread id={self.id} is '{self.status}' and cannot accept new messages."
            )

    def transition_to(self, new_status: str, *, agent=None) -> None:
        """
        Advance thread status via the agent state machine.

        Raises:
            ValueError:              If new_status is unknown.
            SupportThreadClosedError: If transition is not permitted.
        """
        if new_status not in SupportThreadStatus.values:
            raise ValueError(f"Unknown support thread status '{new_status}'.")

        allowed = self.AGENT_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise SupportThreadClosedError(
                f"Cannot transition SupportThread from '{self.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        old = self.status
        self.status = new_status
        now = timezone.now()
        update_fields = ["status", "updated_at"]

        if new_status == SupportThreadStatus.RESOLVED:
            self.resolved_at = now
            update_fields.append("resolved_at")
        elif new_status == SupportThreadStatus.CLOSED:
            self.closed_at = now
            update_fields.append("closed_at")

        SupportThread.objects.filter(pk=self.pk).update(
            **{f: getattr(self, f) for f in update_fields}
        )
        logger.info(
            "SupportThread %s: %s → %s (agent=%s)",
            self.id, old, new_status, getattr(agent, "pk", "system"),
        )


# ---------------------------------------------------------------------------
# SupportMessage
# ---------------------------------------------------------------------------

class SupportMessage(TimestampedModel):
    """
    A single message within a SupportThread (from user or agent).
    """

    thread = models.ForeignKey(
        SupportThread,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
        verbose_name=_("Thread"),
    )
    sender = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages",
        verbose_name=_("Sender"),
    )
    content = models.TextField(
        max_length=MAX_MESSAGE_LENGTH,
        verbose_name=_("Content"),
    )
    is_agent_reply = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Agent Reply"),
        help_text=_("True if sent by a support agent, False if by the user."),
    )
    attachments = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Attachments"),
    )
    is_internal_note = models.BooleanField(
        default=False,
        verbose_name=_("Is Internal Note"),
        help_text=_("Internal notes are visible only to agents."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Support Message")
        verbose_name_plural = _("Support Messages")
        indexes = [
            models.Index(fields=["thread", "created_at"], name="msg_sm_thread_created_idx"),
        ]

    def __str__(self) -> str:
        kind = "Agent" if self.is_agent_reply else "User"
        return f"{kind} message in thread {self.thread_id}"

    def clean(self) -> None:
        errors: dict = {}
        if not self.content or not self.content.strip():
            errors.setdefault("content", []).append(_("content must not be empty."))
        if isinstance(self.attachments, list):
            if len(self.attachments) > MAX_ATTACHMENTS_PER_MESSAGE:
                errors.setdefault("attachments", []).append(
                    _(f"Max {MAX_ATTACHMENTS_PER_MESSAGE} attachments allowed.")
                )
        else:
            errors.setdefault("attachments", []).append(_("attachments must be a list."))
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# UserInbox
# ---------------------------------------------------------------------------

class UserInbox(TimestampedModel):
    """
    A fan-out inbox record per user for all incoming messages.

    Every chat message, broadcast, and support reply creates one UserInbox
    record per recipient. This enables O(1) unread count queries and
    per-user notification preferences.

    Immutability:
    - Once is_read=True, it must not revert to False.
    - item_type and user cannot change after creation.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inbox_items",
        db_index=True,
        verbose_name=_("User"),
    )
    item_type = models.CharField(
        max_length=20,
        choices=InboxItemType.choices,
        db_index=True,
        verbose_name=_("Item Type"),
    )
    # Generic FK references (store as UUID strings to avoid polymorphic FK complexity)
    source_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Source ID"),
        help_text=_("PK of the source object (ChatMessage, AdminBroadcast, or SupportMessage)."),
    )
    title = models.CharField(
        max_length=MAX_BROADCAST_TITLE_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Title"),
        help_text=_("Denormalized title shown in the inbox list."),
    )
    preview = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Preview"),
        help_text=_("Short content preview."),
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Read"),
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Read At"),
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Archived"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
    )

    objects: UserInboxManager = UserInboxManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Inbox Item")
        verbose_name_plural = _("User Inbox Items")
        indexes = [
            models.Index(
                fields=["user", "is_read", "created_at"],
                name="msg_ui_user_read_created_idx",
            ),
            models.Index(
                fields=["user", "item_type", "created_at"],
                name="msg_ui_user_type_created_idx",
            ),
            models.Index(
                fields=["source_id", "item_type"],
                name="msg_ui_source_type_idx",
            ),
        ]
        constraints = [
            CheckConstraint(
                check=Q(is_read=False) | Q(read_at__isnull=False),
                name="msg_ui_read_needs_read_at",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Inbox[{self.item_type}] for user={self.user_id} "
            f"read={self.is_read} title={self.title!r}"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_unread(self) -> bool:
        return not self.is_read

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict = {}

        if self.item_type not in InboxItemType.values:
            errors.setdefault("item_type", []).append(
                _(f"Invalid item_type '{self.item_type}'.")
            )

        if self.is_read and not self.read_at:
            errors.setdefault("read_at", []).append(
                _("read_at must be set when is_read is True.")
            )

        # Immutability: once read, cannot un-read
        if self.pk:
            try:
                original = UserInbox.objects.get(pk=self.pk)
                if original.is_read and not self.is_read:
                    errors.setdefault("is_read", []).append(
                        _("Cannot mark an already-read inbox item as unread.")
                    )
                # user and item_type are immutable
                for field in ("user_id", "item_type"):
                    if getattr(original, field) != getattr(self, field):
                        errors.setdefault(field, []).append(
                            _(f"'{field}' cannot be changed after creation.")
                        )
            except UserInbox.DoesNotExist:
                pass

        self._validate_metadata(self.metadata)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def mark_read(self) -> None:
        """Mark this inbox item as read. Idempotent."""
        if self.is_read:
            return
        now = timezone.now()
        UserInbox.objects.filter(pk=self.pk).update(
            is_read=True, read_at=now, updated_at=now
        )
        self.is_read = True
        self.read_at = now
        logger.debug("UserInbox %s marked read for user=%s.", self.id, self.user_id)

    def archive(self) -> None:
        """Archive (hide) this inbox item without deleting it. Idempotent."""
        if self.is_archived:
            return
        UserInbox.objects.filter(pk=self.pk).update(
            is_archived=True, updated_at=timezone.now()
        )
        self.is_archived = True
