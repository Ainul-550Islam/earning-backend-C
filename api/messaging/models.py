"""
Messaging Models — World-class update.
Existing: InternalChat, ChatParticipant, ChatMessage, AdminBroadcast,
          SupportThread, SupportMessage, UserInbox
New:      MessageReaction, UserPresence, CallSession, AnnouncementChannel,
          ChannelMember, ScheduledMessage, MessagePin, PollVote,
          BotConfig, BotResponse, MessagingWebhook, MessageTranslation,
          ThreadReply, MessageForward, UserBlock
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
    ReactionEmoji,
    CallStatus,
    CallType,
    NotificationPreference,
    PresenceStatus,
    ChannelType,
    BotTriggerType,
    MessagePriority,
    WebhookEventType,
    ScheduledMessageStatus,
    CPANotificationType,
    NotificationPriority,
    CPABroadcastAudienceFilter,
    MessageTemplateCategory,
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
    MAX_REACTION_CUSTOM_LENGTH,
    MAX_BOT_RESPONSE_LENGTH,
    MAX_CHANNEL_DESCRIPTION,
    MAX_POLL_QUESTION_LENGTH,
    MAX_POLL_OPTION_LENGTH,
    MAX_POLL_OPTIONS,
    MAX_PINNED_MESSAGES,
    MAX_WEBHOOK_URL_LENGTH,
    CALL_MAX_DURATION_SECONDS,
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

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"

    def _validate_metadata(self, value: dict, field_name: str = "metadata") -> None:
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
# InternalChat  (EXISTING — unchanged)
# ---------------------------------------------------------------------------

class InternalChat(TimestampedModel):
    name = models.CharField(
        max_length=MAX_CHAT_NAME_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Chat Name"),
        help_text=_("Optional name for group chats. Leave blank for direct messages."),
    )
    is_group = models.BooleanField(default=False, verbose_name=_("Is Group Chat"))
    status = models.CharField(
        max_length=20,
        choices=ChatStatus.choices,
        default=ChatStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
    )
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_chats",
        verbose_name=_("Created By"),
    )
    last_message_at = models.DateTimeField(
        null=True, blank=True,
        db_index=True,
        verbose_name=_("Last Message At"),
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    # NEW fields
    avatar = models.URLField(
        max_length=500, blank=True, null=True,
        verbose_name=_("Group Avatar URL"),
    )
    description = models.CharField(
        max_length=500, blank=True, default="",
        verbose_name=_("Group Description"),
    )
    is_encrypted = models.BooleanField(
        default=False,
        verbose_name=_("End-to-End Encrypted"),
    )
    max_participants = models.PositiveIntegerField(
        default=256,
        verbose_name=_("Max Participants"),
    )
    notification_preference = models.CharField(
        max_length=10,
        choices=NotificationPreference.choices,
        default=NotificationPreference.ALL,
        verbose_name=_("Default Notification Preference"),
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

    @property
    def is_active(self) -> bool:
        return self.status == ChatStatus.ACTIVE

    def clean(self) -> None:
        errors: dict = {}
        if self.is_group and not self.name.strip():
            errors.setdefault("name", []).append(_("Group chats must have a name."))
        self._validate_metadata(self.metadata)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def archive(self) -> None:
        if self.status == ChatStatus.ARCHIVED:
            return
        if self.status == ChatStatus.DELETED:
            raise ChatArchivedError(f"Cannot archive a DELETED chat (id={self.id}).")
        self.status = ChatStatus.ARCHIVED
        InternalChat.objects.filter(pk=self.pk).update(
            status=ChatStatus.ARCHIVED, updated_at=timezone.now()
        )
        logger.info("InternalChat %s archived.", self.id)

    def soft_delete(self) -> None:
        self.status = ChatStatus.DELETED
        InternalChat.objects.filter(pk=self.pk).update(
            status=ChatStatus.DELETED, updated_at=timezone.now()
        )
        logger.info("InternalChat %s soft-deleted.", self.id)

    def assert_active(self) -> None:
        if self.status != ChatStatus.ACTIVE:
            raise ChatArchivedError(
                f"Chat id={self.id} is '{self.status}' and cannot receive messages."
            )

    def touch(self) -> None:
        now = timezone.now()
        InternalChat.objects.filter(pk=self.pk).update(
            last_message_at=now, updated_at=now
        )
        self.last_message_at = now


# ---------------------------------------------------------------------------
# ChatParticipant  (EXISTING — + new fields)
# ---------------------------------------------------------------------------

class ChatParticipant(TimestampedModel):
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
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Read At"))
    is_muted = models.BooleanField(default=False, verbose_name=_("Is Muted"))
    joined_at = models.DateTimeField(default=timezone.now, verbose_name=_("Joined At"))
    left_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Left At"))

    # NEW fields
    notification_preference = models.CharField(
        max_length=10,
        choices=NotificationPreference.choices,
        default=NotificationPreference.ALL,
        verbose_name=_("Notification Preference"),
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name=_("Chat Pinned"),
        help_text=_("User has pinned this chat to the top of inbox."),
    )
    nickname = models.CharField(
        max_length=100, blank=True, default="",
        verbose_name=_("Nickname"),
        help_text=_("Custom nickname the user gave this contact in this chat."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Chat Participant")
        verbose_name_plural = _("Chat Participants")
        constraints = [
            UniqueConstraint(fields=["chat", "user"], name="msg_cp_unique_chat_user"),
        ]
        indexes = [
            models.Index(fields=["user", "chat"], name="msg_cp_user_chat_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in Chat {self.chat_id} [{self.role}]"

    def clean(self) -> None:
        if self.left_at and self.joined_at and self.left_at < self.joined_at:
            raise ValidationError({"left_at": [_("left_at cannot be before joined_at.")]})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_read(self) -> None:
        now = timezone.now()
        ChatParticipant.objects.filter(pk=self.pk).update(
            last_read_at=now, updated_at=now
        )
        self.last_read_at = now


# ---------------------------------------------------------------------------
# ChatMessage  (EXISTING — + new fields)
# ---------------------------------------------------------------------------

class ChatMessage(TimestampedModel):
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
        verbose_name=_("Chat"),
    )
    sender = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_messages",
        verbose_name=_("Sender"),
    )
    content = models.TextField(
        blank=True, default="",
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
        default=list, blank=True,
        verbose_name=_("Attachments"),
    )
    reply_to = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
        verbose_name=_("Reply To"),
    )
    is_edited = models.BooleanField(default=False, verbose_name=_("Is Edited"))
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Edited At"))
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Deleted At"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    # NEW fields
    priority = models.CharField(
        max_length=10,
        choices=MessagePriority.choices,
        default=MessagePriority.NORMAL,
        verbose_name=_("Priority"),
    )
    is_forwarded = models.BooleanField(
        default=False, verbose_name=_("Is Forwarded"),
    )
    forwarded_from = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="forward_instances",
        verbose_name=_("Forwarded From"),
    )
    mentions = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Mentions"),
        help_text=_("List of user PKs mentioned in this message (@mentions)."),
    )
    thread_id = models.UUIDField(
        null=True, blank=True,
        db_index=True,
        verbose_name=_("Thread ID"),
        help_text=_("If set, this message belongs to a thread reply chain."),
    )
    thread_reply_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Thread Reply Count"),
    )
    delivery_receipts = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Delivery Receipts"),
        help_text=_("{user_pk: delivered_at_iso} mapping."),
    )
    read_receipts = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Read Receipts"),
        help_text=_("{user_pk: read_at_iso} mapping."),
    )
    # For POLL type
    poll_data = models.JSONField(
        null=True, blank=True,
        verbose_name=_("Poll Data"),
        help_text=_("{question, options:[{id,text}], multiple_choice, expires_at}"),
    )
    # For LOCATION type
    location_data = models.JSONField(
        null=True, blank=True,
        verbose_name=_("Location Data"),
        help_text=_("{lat, lng, address, name}"),
    )
    # For CALL_LOG type
    call_log_data = models.JSONField(
        null=True, blank=True,
        verbose_name=_("Call Log Data"),
        help_text=_("{call_id, type, status, duration_seconds, caller_id}"),
    )
    # E2E encryption
    encrypted_content = models.BinaryField(
        null=True, blank=True,
        verbose_name=_("Encrypted Content"),
    )
    encryption_key_id = models.CharField(
        max_length=128, blank=True, null=True,
        verbose_name=_("Encryption Key ID"),
    )

    objects: ChatMessageManager = ChatMessageManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Chat Message")
        verbose_name_plural = _("Chat Messages")
        indexes = [
            models.Index(fields=["chat", "created_at"], name="msg_cm_chat_created_idx"),
            models.Index(fields=["sender", "created_at"], name="msg_cm_sender_created_idx"),
            models.Index(fields=["status", "created_at"], name="msg_cm_status_created_idx"),
            models.Index(fields=["thread_id"], name="msg_cm_thread_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=Q(message_type="TEXT") | Q(content__gt=""),
                name="msg_cm_text_needs_content",
            ),
        ]

    def __str__(self) -> str:
        preview = (self.content[:40] + "...") if len(self.content) > 40 else self.content
        return f"Message [{self.message_type}] from {self.sender_id}: {preview!r}"

    @property
    def is_deleted(self) -> bool:
        return self.status == MessageStatus.DELETED

    @property
    def is_visible(self) -> bool:
        return self.status != MessageStatus.DELETED

    def clean(self) -> None:
        errors: dict = {}

        if self.message_type == MessageType.TEXT and not (self.content or "").strip():
            errors.setdefault("content", []).append(
                _("Text messages must have non-empty content.")
            )
        if self.message_type == MessageType.SYSTEM and self.sender_id is not None:
            errors.setdefault("sender", []).append(
                _("System messages must not have a sender.")
            )
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

    def soft_delete(self, *, deleted_by_id: Optional[int] = None) -> None:
        if self.is_deleted:
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
        logger.info("ChatMessage %s soft-deleted by user=%s.", self.id, deleted_by_id)

    def mark_edited(self, new_content: str) -> None:
        if self.is_deleted:
            raise ValidationError({"content": [_("Cannot edit a deleted message.")]})
        if not new_content or not new_content.strip():
            raise ValidationError({"content": [_("Edited content must not be empty.")]})
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


# ---------------------------------------------------------------------------
# AdminBroadcast  (EXISTING — unchanged)
# ---------------------------------------------------------------------------

class AdminBroadcast(TimestampedModel):
    VALID_TRANSITIONS: dict[str, list[str]] = {
        BroadcastStatus.DRAFT: [BroadcastStatus.SCHEDULED, BroadcastStatus.SENDING, BroadcastStatus.CANCELLED],
        BroadcastStatus.SCHEDULED: [BroadcastStatus.SENDING, BroadcastStatus.CANCELLED],
        BroadcastStatus.SENDING: [BroadcastStatus.SENT, BroadcastStatus.FAILED],
        BroadcastStatus.SENT: [],
        BroadcastStatus.FAILED: [BroadcastStatus.DRAFT],
        BroadcastStatus.CANCELLED: [],
    }

    title = models.CharField(max_length=MAX_BROADCAST_TITLE_LENGTH, verbose_name=_("Title"))
    body = models.TextField(max_length=MAX_BROADCAST_BODY_LENGTH, verbose_name=_("Body"))
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
    audience_filter = models.JSONField(default=dict, blank=True, verbose_name=_("Audience Filter"))
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Scheduled At"))
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent At"))
    recipient_count = models.PositiveIntegerField(default=0, verbose_name=_("Recipient Count"))
    delivered_count = models.PositiveIntegerField(default=0, verbose_name=_("Delivered Count"))
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_broadcasts",
        verbose_name=_("Created By"),
    )
    error_message = models.TextField(blank=True, default="", verbose_name=_("Error Message"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

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

    @property
    def delivery_rate(self) -> Optional[float]:
        if self.recipient_count == 0:
            return None
        return round((self.delivered_count / self.recipient_count) * 100, 2)

    @property
    def is_editable(self) -> bool:
        return self.status in (BroadcastStatus.DRAFT, BroadcastStatus.FAILED)

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

    def transition_to(self, new_status: str, *, actor=None) -> None:
        if new_status not in BroadcastStatus.values:
            raise BroadcastStateError(f"Unknown broadcast status '{new_status}'.")
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
        logger.info("AdminBroadcast %s: %s → %s (actor=%s)", self.id, old, new_status, getattr(actor, "pk", "system"))

    def mark_failed(self, error: str) -> None:
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
# SupportThread  (EXISTING — unchanged)
# ---------------------------------------------------------------------------

class SupportThread(TimestampedModel):
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
        User, on_delete=models.CASCADE,
        related_name="support_threads",
        db_index=True, verbose_name=_("User"),
    )
    assigned_agent = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_threads",
        verbose_name=_("Assigned Agent"),
    )
    subject = models.CharField(max_length=MAX_SUBJECT_LENGTH, verbose_name=_("Subject"))
    status = models.CharField(
        max_length=15,
        choices=SupportThreadStatus.choices,
        default=SupportThreadStatus.OPEN,
        db_index=True, verbose_name=_("Status"),
    )
    priority = models.CharField(
        max_length=10,
        choices=SupportThreadPriority.choices,
        default=SupportThreadPriority.NORMAL,
        db_index=True, verbose_name=_("Priority"),
    )
    last_reply_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Last Reply At"))
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Resolved At"))
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Closed At"))
    agent_note = models.TextField(
        blank=True, default="",
        max_length=MAX_THREAD_NOTE_LENGTH,
        verbose_name=_("Agent Note"),
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

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

    @property
    def is_closed(self) -> bool:
        return self.status == SupportThreadStatus.CLOSED

    @property
    def is_resolved(self) -> bool:
        return self.status == SupportThreadStatus.RESOLVED

    @property
    def is_open_for_reply(self) -> bool:
        return self.status not in (SupportThreadStatus.CLOSED,)

    def clean(self) -> None:
        errors: dict = {}
        if not self.subject or not self.subject.strip():
            errors.setdefault("subject", []).append(_("subject must not be empty."))
        if self.resolved_at and self.status not in (SupportThreadStatus.RESOLVED, SupportThreadStatus.CLOSED):
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

    def assert_open_for_reply(self) -> None:
        if not self.is_open_for_reply:
            raise SupportThreadClosedError(
                f"SupportThread id={self.id} is '{self.status}' and cannot accept new messages."
            )

    def transition_to(self, new_status: str, *, agent=None) -> None:
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
        logger.info("SupportThread %s: %s → %s (agent=%s)", self.id, old, new_status, getattr(agent, "pk", "system"))


# ---------------------------------------------------------------------------
# SupportMessage  (EXISTING — unchanged)
# ---------------------------------------------------------------------------

class SupportMessage(TimestampedModel):
    thread = models.ForeignKey(
        SupportThread,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True, verbose_name=_("Thread"),
    )
    sender = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages",
        verbose_name=_("Sender"),
    )
    content = models.TextField(max_length=MAX_MESSAGE_LENGTH, verbose_name=_("Content"))
    is_agent_reply = models.BooleanField(default=False, db_index=True, verbose_name=_("Is Agent Reply"))
    attachments = models.JSONField(default=list, blank=True, verbose_name=_("Attachments"))
    is_internal_note = models.BooleanField(default=False, verbose_name=_("Is Internal Note"))

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
# UserInbox  (EXISTING — unchanged)
# ---------------------------------------------------------------------------

class UserInbox(TimestampedModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="inbox_items",
        db_index=True, verbose_name=_("User"),
    )
    item_type = models.CharField(
        max_length=20,
        choices=InboxItemType.choices,
        db_index=True, verbose_name=_("Item Type"),
    )
    source_id = models.UUIDField(null=True, blank=True, db_index=True, verbose_name=_("Source ID"))
    title = models.CharField(max_length=MAX_BROADCAST_TITLE_LENGTH, blank=True, default="", verbose_name=_("Title"))
    preview = models.CharField(max_length=200, blank=True, default="", verbose_name=_("Preview"))
    is_read = models.BooleanField(default=False, db_index=True, verbose_name=_("Is Read"))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Read At"))
    is_archived = models.BooleanField(default=False, db_index=True, verbose_name=_("Is Archived"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    objects: UserInboxManager = UserInboxManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Inbox Item")
        verbose_name_plural = _("User Inbox Items")
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"], name="msg_ui_user_read_created_idx"),
            models.Index(fields=["user", "item_type", "created_at"], name="msg_ui_user_type_created_idx"),
            models.Index(fields=["source_id", "item_type"], name="msg_ui_source_type_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=Q(is_read=False) | Q(read_at__isnull=False),
                name="msg_ui_read_needs_read_at",
            ),
        ]

    def __str__(self) -> str:
        return f"Inbox[{self.item_type}] for user={self.user_id} read={self.is_read} title={self.title!r}"

    @property
    def is_unread(self) -> bool:
        return not self.is_read

    def clean(self) -> None:
        errors: dict = {}
        if self.item_type not in InboxItemType.values:
            errors.setdefault("item_type", []).append(_(f"Invalid item_type '{self.item_type}'."))
        if self.is_read and not self.read_at:
            errors.setdefault("read_at", []).append(_("read_at must be set when is_read is True."))
        if self.pk:
            try:
                original = UserInbox.objects.get(pk=self.pk)
                if original.is_read and not self.is_read:
                    errors.setdefault("is_read", []).append(
                        _("Cannot mark an already-read inbox item as unread.")
                    )
                for field in ("user_id", "item_type"):
                    if getattr(original, field) != getattr(self, field):
                        errors.setdefault(field, []).append(_(f"'{field}' cannot be changed after creation."))
            except UserInbox.DoesNotExist:
                pass
        self._validate_metadata(self.metadata)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_read(self) -> None:
        if self.is_read:
            return
        now = timezone.now()
        UserInbox.objects.filter(pk=self.pk).update(is_read=True, read_at=now, updated_at=now)
        self.is_read = True
        self.read_at = now

    def archive(self) -> None:
        if self.is_archived:
            return
        UserInbox.objects.filter(pk=self.pk).update(is_archived=True, updated_at=timezone.now())
        self.is_archived = True


# ===========================================================================
# NEW MODELS
# ===========================================================================

# ---------------------------------------------------------------------------
# MessageReaction  (NEW — Slack/WhatsApp style emoji reactions)
# ---------------------------------------------------------------------------

class MessageReaction(TimestampedModel):
    """
    Emoji reaction on a ChatMessage.
    One user can react with one emoji per message (unique constraint).
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="reactions",
        verbose_name=_("Message"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="message_reactions",
        verbose_name=_("User"),
    )
    emoji = models.CharField(
        max_length=10,
        choices=ReactionEmoji.choices,
        verbose_name=_("Emoji"),
    )
    custom_emoji = models.CharField(
        max_length=MAX_REACTION_CUSTOM_LENGTH,
        blank=True, null=True,
        verbose_name=_("Custom Emoji Code"),
        help_text=_("Used when emoji=CUSTOM. E.g. ':party_blob:'."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Reaction")
        verbose_name_plural = _("Message Reactions")
        constraints = [
            UniqueConstraint(
                fields=["message", "user", "emoji"],
                name="msg_mr_unique_message_user_emoji",
            ),
        ]
        indexes = [
            models.Index(fields=["message", "emoji"], name="msg_mr_msg_emoji_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} reacted {self.emoji} on msg {self.message_id}"

    def clean(self) -> None:
        if self.emoji == ReactionEmoji.CUSTOM and not self.custom_emoji:
            raise ValidationError(
                {"custom_emoji": [_("custom_emoji is required when emoji=CUSTOM.")]}
            )


# ---------------------------------------------------------------------------
# UserPresence  (NEW — Online/Away/Offline status)
# ---------------------------------------------------------------------------

class UserPresence(TimestampedModel):
    """
    Real-time presence tracking. One record per user (upserted on connect/disconnect).
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="presence",
        verbose_name=_("User"),
    )
    status = models.CharField(
        max_length=10,
        choices=PresenceStatus.choices,
        default=PresenceStatus.OFFLINE,
        db_index=True,
        verbose_name=_("Presence Status"),
    )
    last_seen_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Last Seen At"),
    )
    last_seen_on = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name=_("Last Seen On"),
        help_text=_("Platform: web, android, ios, desktop."),
    )
    custom_status = models.CharField(
        max_length=128, blank=True, default="",
        verbose_name=_("Custom Status"),
        help_text=_("User-set status message e.g. 'In a meeting'."),
    )
    custom_status_emoji = models.CharField(
        max_length=10, blank=True, default="",
        verbose_name=_("Custom Status Emoji"),
    )
    custom_status_expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Custom Status Expires At"),
    )
    is_invisible = models.BooleanField(
        default=False,
        verbose_name=_("Invisible Mode"),
        help_text=_("User appears offline to others even when active."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Presence")
        verbose_name_plural = _("User Presences")
        indexes = [
            models.Index(fields=["status", "last_seen_at"], name="msg_up_status_lastseen_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} — {self.status} (last seen {self.last_seen_at})"

    @property
    def effective_status(self) -> str:
        if self.is_invisible:
            return PresenceStatus.OFFLINE
        return self.status

    def go_online(self, platform: str = "web") -> None:
        now = timezone.now()
        UserPresence.objects.filter(pk=self.pk).update(
            status=PresenceStatus.ONLINE,
            last_seen_at=now,
            last_seen_on=platform,
            updated_at=now,
        )
        self.status = PresenceStatus.ONLINE
        self.last_seen_at = now

    def go_offline(self) -> None:
        now = timezone.now()
        UserPresence.objects.filter(pk=self.pk).update(
            status=PresenceStatus.OFFLINE,
            last_seen_at=now,
            updated_at=now,
        )
        self.status = PresenceStatus.OFFLINE
        self.last_seen_at = now


# ---------------------------------------------------------------------------
# CallSession  (NEW — WebRTC voice/video calls)
# ---------------------------------------------------------------------------

class CallSession(TimestampedModel):
    """
    Voice or video call session between participants.
    Signaling data (SDP offers/answers, ICE candidates) flows via WebSocket.
    """
    call_type = models.CharField(
        max_length=10,
        choices=CallType.choices,
        default=CallType.AUDIO,
        verbose_name=_("Call Type"),
    )
    status = models.CharField(
        max_length=10,
        choices=CallStatus.choices,
        default=CallStatus.RINGING,
        db_index=True,
        verbose_name=_("Call Status"),
    )
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="calls",
        verbose_name=_("Related Chat"),
    )
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="initiated_calls",
        verbose_name=_("Caller"),
    )
    participants = models.ManyToManyField(
        User,
        related_name="call_sessions",
        blank=True,
        verbose_name=_("Participants"),
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Started At"))
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Ended At"))
    duration_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Duration (seconds)"),
    )
    room_id = models.CharField(
        max_length=128, unique=True,
        verbose_name=_("WebRTC Room ID"),
    )
    is_recorded = models.BooleanField(default=False, verbose_name=_("Is Recorded"))
    recording_url = models.URLField(null=True, blank=True, verbose_name=_("Recording URL"))
    ice_servers = models.JSONField(
        default=list, blank=True,
        verbose_name=_("ICE Servers"),
        help_text=_("STUN/TURN server config [{urls, username, credential}]."),
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Call Session")
        verbose_name_plural = _("Call Sessions")
        indexes = [
            models.Index(fields=["status", "created_at"], name="msg_cs_status_created_idx"),
            models.Index(fields=["initiated_by", "status"], name="msg_cs_caller_status_idx"),
            models.Index(fields=["room_id"], name="msg_cs_room_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.call_type} call [{self.status}] by {self.initiated_by_id} room={self.room_id}"

    def end_call(self, status: str = CallStatus.ENDED) -> None:
        now = timezone.now()
        if self.started_at:
            self.duration_seconds = int((now - self.started_at).total_seconds())
        self.ended_at = now
        self.status = status
        CallSession.objects.filter(pk=self.pk).update(
            status=status,
            ended_at=now,
            duration_seconds=self.duration_seconds,
            updated_at=now,
        )
        logger.info("CallSession %s ended with status=%s duration=%ds", self.id, status, self.duration_seconds)


# ---------------------------------------------------------------------------
# AnnouncementChannel  (NEW — Telegram-style one-way broadcast channels)
# ---------------------------------------------------------------------------

class AnnouncementChannel(TimestampedModel):
    """
    One-way broadcast channel (like Telegram channels).
    Only admins can post; members can only read.
    """
    name = models.CharField(max_length=MAX_CHAT_NAME_LENGTH, verbose_name=_("Channel Name"))
    slug = models.SlugField(
        max_length=100, unique=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly identifier e.g. 'company-updates'."),
    )
    description = models.CharField(
        max_length=MAX_CHANNEL_DESCRIPTION,
        blank=True, default="",
        verbose_name=_("Description"),
    )
    channel_type = models.CharField(
        max_length=10,
        choices=ChannelType.choices,
        default=ChannelType.PUBLIC,
        verbose_name=_("Channel Type"),
    )
    avatar = models.URLField(max_length=500, null=True, blank=True, verbose_name=_("Avatar URL"))
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="owned_channels",
        verbose_name=_("Created By"),
    )
    is_verified = models.BooleanField(default=False, verbose_name=_("Is Verified"))
    subscriber_count = models.PositiveIntegerField(default=0, verbose_name=_("Subscriber Count"))
    post_count = models.PositiveIntegerField(default=0, verbose_name=_("Post Count"))
    last_post_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Post At"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Announcement Channel")
        verbose_name_plural = _("Announcement Channels")
        indexes = [
            models.Index(fields=["channel_type", "subscriber_count"], name="msg_ac_type_subs_idx"),
            models.Index(fields=["slug"], name="msg_ac_slug_idx"),
        ]

    def __str__(self) -> str:
        return f"Channel: {self.name} ({self.channel_type})"


# ---------------------------------------------------------------------------
# ChannelMember  (NEW)
# ---------------------------------------------------------------------------

class ChannelMember(TimestampedModel):
    channel = models.ForeignKey(
        AnnouncementChannel,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name=_("Channel"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="channel_memberships",
        verbose_name=_("User"),
    )
    is_admin = models.BooleanField(default=False, verbose_name=_("Is Admin"))
    notification_preference = models.CharField(
        max_length=10,
        choices=NotificationPreference.choices,
        default=NotificationPreference.ALL,
        verbose_name=_("Notification Preference"),
    )
    joined_at = models.DateTimeField(default=timezone.now, verbose_name=_("Joined At"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Channel Member")
        verbose_name_plural = _("Channel Members")
        constraints = [
            UniqueConstraint(fields=["channel", "user"], name="msg_cm_unique_channel_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in channel {self.channel_id}"


# ---------------------------------------------------------------------------
# ScheduledMessage  (NEW — Send a message at a future time)
# ---------------------------------------------------------------------------

class ScheduledMessage(TimestampedModel):
    """
    A message scheduled to be sent at a specific time.
    """
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="scheduled_messages",
        verbose_name=_("Chat"),
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="my_scheduled_messages",
        verbose_name=_("Sender"),
    )
    content = models.TextField(max_length=MAX_MESSAGE_LENGTH, verbose_name=_("Content"))
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        verbose_name=_("Message Type"),
    )
    attachments = models.JSONField(default=list, blank=True, verbose_name=_("Attachments"))
    scheduled_for = models.DateTimeField(db_index=True, verbose_name=_("Scheduled For"))
    status = models.CharField(
        max_length=10,
        choices=ScheduledMessageStatus.choices,
        default=ScheduledMessageStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    sent_message = models.ForeignKey(
        ChatMessage,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="scheduled_origin",
        verbose_name=_("Sent Message"),
    )
    error = models.TextField(blank=True, default="", verbose_name=_("Error"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Scheduled Message")
        verbose_name_plural = _("Scheduled Messages")
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="msg_schm_status_sched_idx"),
            models.Index(fields=["sender", "status"], name="msg_schm_sender_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Scheduled msg by {self.sender_id} for {self.scheduled_for} [{self.status}]"

    def clean(self) -> None:
        if self.pk is None and self.scheduled_for and self.scheduled_for <= timezone.now():
            raise ValidationError({"scheduled_for": [_("scheduled_for must be in the future.")]})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# MessagePin  (NEW — Pin important messages in a chat)
# ---------------------------------------------------------------------------

class MessagePin(TimestampedModel):
    """
    A pinned message in a chat. Max MAX_PINNED_MESSAGES per chat.
    """
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="pinned_messages",
        verbose_name=_("Chat"),
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="pins",
        verbose_name=_("Message"),
    )
    pinned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pinned_messages",
        verbose_name=_("Pinned By"),
    )
    pinned_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Pinned At"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Pin")
        verbose_name_plural = _("Message Pins")
        constraints = [
            UniqueConstraint(fields=["chat", "message"], name="msg_mp_unique_chat_message"),
        ]
        ordering = ["-pinned_at"]

    def __str__(self) -> str:
        return f"Pinned msg {self.message_id} in chat {self.chat_id}"

    def clean(self) -> None:
        existing_count = MessagePin.objects.filter(chat=self.chat).exclude(pk=self.pk).count()
        if existing_count >= MAX_PINNED_MESSAGES:
            raise ValidationError(
                _(f"Cannot pin more than {MAX_PINNED_MESSAGES} messages in a chat.")
            )


# ---------------------------------------------------------------------------
# PollVote  (NEW — Vote on a poll message)
# ---------------------------------------------------------------------------

class PollVote(TimestampedModel):
    """
    A user's vote on a poll message.
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="poll_votes",
        verbose_name=_("Poll Message"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="poll_votes",
        verbose_name=_("Voter"),
    )
    option_id = models.CharField(
        max_length=50,
        verbose_name=_("Option ID"),
        help_text=_("ID of the selected poll option."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Poll Vote")
        verbose_name_plural = _("Poll Votes")
        constraints = [
            UniqueConstraint(
                fields=["message", "user", "option_id"],
                name="msg_pv_unique_msg_user_opt",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} voted '{self.option_id}' on poll {self.message_id}"

    def clean(self) -> None:
        if self.message.message_type != MessageType.POLL:
            raise ValidationError({"message": [_("Can only vote on POLL type messages.")]})


# ---------------------------------------------------------------------------
# BotConfig  (NEW — Auto-reply bot configuration)
# ---------------------------------------------------------------------------

class BotConfig(TimestampedModel):
    """
    Auto-reply bot for a chat or globally.
    Supports keyword matching, regex, greeting for new users.
    """
    name = models.CharField(max_length=100, verbose_name=_("Bot Name"))
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="bot_configs",
        verbose_name=_("Chat"),
        help_text=_("Leave blank for a global bot."),
    )
    trigger_type = models.CharField(
        max_length=10,
        choices=BotTriggerType.choices,
        default=BotTriggerType.KEYWORD,
        verbose_name=_("Trigger Type"),
    )
    trigger_value = models.CharField(
        max_length=500, blank=True, default="",
        verbose_name=_("Trigger Value"),
        help_text=_("Keyword or regex pattern. Empty for ALWAYS/NEW_USER triggers."),
    )
    response_template = models.TextField(
        max_length=MAX_BOT_RESPONSE_LENGTH,
        verbose_name=_("Response Template"),
        help_text=_("Supports {user_name}, {chat_name} placeholders."),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    priority = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Priority"),
        help_text=_("Higher = checked first."),
    )
    delay_seconds = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Response Delay (seconds)"),
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="created_bots",
        verbose_name=_("Created By"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Bot Config")
        verbose_name_plural = _("Bot Configs")
        ordering = ["-priority", "name"]
        indexes = [
            models.Index(fields=["trigger_type", "is_active"], name="msg_bc_trigger_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Bot: {self.name} [{self.trigger_type}] active={self.is_active}"


# ---------------------------------------------------------------------------
# BotResponse  (NEW — Log of bot responses)
# ---------------------------------------------------------------------------

class BotResponse(TimestampedModel):
    bot = models.ForeignKey(
        BotConfig,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("Bot"),
    )
    trigger_message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        null=True,
        related_name="bot_trigger_responses",
        verbose_name=_("Trigger Message"),
    )
    sent_message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bot_sent_response",
        verbose_name=_("Sent Message"),
    )
    was_successful = models.BooleanField(default=True, verbose_name=_("Was Successful"))
    error = models.TextField(blank=True, default="", verbose_name=_("Error"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Bot Response")
        verbose_name_plural = _("Bot Responses")

    def __str__(self) -> str:
        return f"BotResponse bot={self.bot_id} success={self.was_successful}"


# ---------------------------------------------------------------------------
# MessagingWebhook  (NEW — Outbound webhooks to external systems)
# ---------------------------------------------------------------------------

class MessagingWebhook(TimestampedModel):
    """
    Outbound webhook registration. When events occur (message sent, call ended, etc.),
    this webhook URL is called with signed payloads.
    """
    name = models.CharField(max_length=200, verbose_name=_("Webhook Name"))
    url = models.URLField(
        max_length=MAX_WEBHOOK_URL_LENGTH,
        verbose_name=_("Endpoint URL"),
    )
    secret = models.CharField(
        max_length=256,
        verbose_name=_("Signing Secret"),
        help_text=_("HMAC-SHA256 signing secret. Never expose to clients."),
    )
    events = models.JSONField(
        default=list,
        verbose_name=_("Subscribed Events"),
        help_text=_("List of WebhookEventType values to subscribe to."),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="messaging_webhooks",
        verbose_name=_("Created By"),
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Triggered At"))
    failure_count = models.PositiveSmallIntegerField(default=0, verbose_name=_("Failure Count"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Messaging Webhook")
        verbose_name_plural = _("Messaging Webhooks")
        indexes = [
            models.Index(fields=["is_active", "created_at"], name="msg_wh_active_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Webhook: {self.name} → {self.url}"

    def sign_payload(self, body: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload."""
        import hmac as _hmac
        sig = _hmac.new(self.secret.encode(), body.encode(), hashlib.sha256)
        return sig.hexdigest()


# ---------------------------------------------------------------------------
# WebhookDelivery  (NEW — Log every webhook delivery attempt)
# ---------------------------------------------------------------------------

class WebhookDelivery(TimestampedModel):
    webhook = models.ForeignKey(
        MessagingWebhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name=_("Webhook"),
    )
    event_type = models.CharField(
        max_length=30,
        choices=WebhookEventType.choices,
        verbose_name=_("Event Type"),
    )
    payload = models.JSONField(verbose_name=_("Payload"))
    response_status = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name=_("Response HTTP Status"),
    )
    response_body = models.TextField(blank=True, default="", verbose_name=_("Response Body"))
    attempt_count = models.PositiveSmallIntegerField(default=1, verbose_name=_("Attempt Count"))
    is_successful = models.BooleanField(default=False, verbose_name=_("Is Successful"))
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Delivered At"))
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Next Retry At"))
    error = models.TextField(blank=True, default="", verbose_name=_("Error"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Webhook Delivery")
        verbose_name_plural = _("Webhook Deliveries")
        indexes = [
            models.Index(fields=["webhook", "is_successful"], name="msg_wd_wh_success_idx"),
            models.Index(fields=["next_retry_at", "is_successful"], name="msg_wd_retry_idx"),
        ]

    def __str__(self) -> str:
        return f"Delivery {self.event_type} to {self.webhook_id} status={self.response_status}"


# ---------------------------------------------------------------------------
# MessageTranslation  (NEW — Auto-translate messages)
# ---------------------------------------------------------------------------

class MessageTranslation(TimestampedModel):
    """
    Cached translation of a ChatMessage into a target language.
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Message"),
    )
    target_language = models.CharField(
        max_length=10,
        verbose_name=_("Target Language"),
        help_text=_("ISO 639-1 code e.g. 'bn', 'en', 'ar'."),
    )
    translated_content = models.TextField(verbose_name=_("Translated Content"))
    source_language = models.CharField(
        max_length=10, blank=True, default="",
        verbose_name=_("Detected Source Language"),
    )
    provider = models.CharField(
        max_length=50, blank=True, default="google",
        verbose_name=_("Translation Provider"),
    )
    is_auto_detected = models.BooleanField(
        default=True,
        verbose_name=_("Language Auto-Detected"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Translation")
        verbose_name_plural = _("Message Translations")
        constraints = [
            UniqueConstraint(
                fields=["message", "target_language"],
                name="msg_mt_unique_msg_lang",
            ),
        ]

    def __str__(self) -> str:
        return f"Translation of msg {self.message_id} → {self.target_language}"


# ---------------------------------------------------------------------------
# UserBlock  (NEW — Block a user from messaging you)
# ---------------------------------------------------------------------------

class UserBlock(TimestampedModel):
    """
    A blocks B: B cannot send messages to A.
    """
    blocker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_users",
        verbose_name=_("Blocker"),
    )
    blocked = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_by_users",
        verbose_name=_("Blocked User"),
    )
    reason = models.CharField(
        max_length=200, blank=True, default="",
        verbose_name=_("Reason"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Block")
        verbose_name_plural = _("User Blocks")
        constraints = [
            UniqueConstraint(fields=["blocker", "blocked"], name="msg_ub_unique_blocker_blocked"),
        ]

    def __str__(self) -> str:
        return f"{self.blocker_id} blocked {self.blocked_id}"

    def clean(self) -> None:
        if self.blocker_id == self.blocked_id:
            raise ValidationError({"blocked": [_("Cannot block yourself.")]})


# ---------------------------------------------------------------------------
# DeviceToken  (NEW — Push notification device registration)
# ---------------------------------------------------------------------------

class DeviceToken(TimestampedModel):
    """
    FCM/APNs/Expo push notification device token.
    """
    PLATFORM_CHOICES = (
        ("android", "Android (FCM)"),
        ("ios", "iOS (APNs)"),
        ("web", "Web (WebPush)"),
        ("expo", "Expo"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="messaging_device_tokens",
        verbose_name=_("User"),
    )
    token = models.CharField(
        max_length=512, unique=True,
        verbose_name=_("Device Token"),
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default="android",
        verbose_name=_("Platform"),
    )
    device_name = models.CharField(
        max_length=200, blank=True, default="",
        verbose_name=_("Device Name"),
    )
    app_version = models.CharField(
        max_length=20, blank=True, default="",
        verbose_name=_("App Version"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    last_used_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Last Used At"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Device Token")
        verbose_name_plural = _("Device Tokens")
        indexes = [
            models.Index(fields=["user", "platform", "is_active"], name="msg_dt_user_platform_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.platform} token for user={self.user_id}"


# ===========================================================================
# FINAL 6% — Remaining World-Class Features
# ===========================================================================

# ---------------------------------------------------------------------------
# MessageEditHistory  (NEW — Slack-style edit audit log)
# ---------------------------------------------------------------------------

class MessageEditHistory(TimestampedModel):
    """
    Full audit log of every edit made to a ChatMessage.
    Immutable — records are never updated or deleted.
    Allows users to see previous versions of edited messages.
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="edit_history",
        verbose_name=_("Message"),
    )
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="message_edits",
        verbose_name=_("Edited By"),
    )
    previous_content = models.TextField(
        verbose_name=_("Previous Content"),
        help_text=_("The content before this edit was made."),
    )
    previous_attachments = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Previous Attachments"),
    )
    edit_reason = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name=_("Edit Reason"),
        help_text=_("Optional user-provided reason for editing."),
    )
    edit_number = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Edit Number"),
        help_text=_("Sequential edit count for this message (1st edit, 2nd edit, ...)."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Edit History")
        verbose_name_plural = _("Message Edit Histories")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["message", "created_at"], name="msg_meh_msg_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Edit #{self.edit_number} of msg {self.message_id} by {self.edited_by_id}"


# ---------------------------------------------------------------------------
# DisappearingMessageConfig  (NEW — WhatsApp/Telegram disappearing messages)
# ---------------------------------------------------------------------------

class DisappearingMessageConfig(TimestampedModel):
    """
    Configure disappearing messages for a chat.
    When enabled, messages are automatically soft-deleted after `ttl_seconds`.
    Per-chat setting. Only one config per chat.
    """
    TTL_CHOICES = (
        (3_600,      "1 hour"),
        (86_400,     "24 hours"),
        (604_800,    "7 days"),
        (2_592_000,  "30 days"),
        (7_776_000,  "90 days"),
    )

    chat = models.OneToOneField(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="disappearing_config",
        verbose_name=_("Chat"),
    )
    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Enabled"),
    )
    ttl_seconds = models.PositiveIntegerField(
        default=604_800,
        choices=TTL_CHOICES,
        verbose_name=_("Time To Live (seconds)"),
        help_text=_("Messages older than this will be auto-deleted."),
    )
    enabled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disappearing_configs_set",
        verbose_name=_("Enabled By"),
    )
    enabled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Enabled At"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Disappearing Message Config")
        verbose_name_plural = _("Disappearing Message Configs")

    def __str__(self) -> str:
        status = "ON" if self.is_enabled else "OFF"
        return f"Disappearing [{status}] chat={self.chat_id} ttl={self.ttl_seconds}s"

    @property
    def ttl_display(self) -> str:
        return dict(self.TTL_CHOICES).get(self.ttl_seconds, f"{self.ttl_seconds}s")


# ---------------------------------------------------------------------------
# UserStory  (NEW — WhatsApp/Instagram Stories / Telegram Status)
# ---------------------------------------------------------------------------

class UserStory(TimestampedModel):
    """
    24-hour story / status post visible to contacts.
    Stories auto-expire after `expires_at` (default 24h).
    Supports text, image, video stories.
    """
    STORY_TYPES = (
        ("text",  "Text"),
        ("image", "Image"),
        ("video", "Video"),
    )

    VISIBILITY_CHOICES = (
        ("all",       "All Contacts"),
        ("close",     "Close Friends Only"),
        ("except",    "All Except..."),
        ("selected",  "Selected Contacts Only"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="stories",
        verbose_name=_("User"),
    )
    story_type = models.CharField(
        max_length=10,
        choices=STORY_TYPES,
        default="text",
        verbose_name=_("Story Type"),
    )
    content = models.TextField(
        blank=True,
        default="",
        max_length=500,
        verbose_name=_("Text Content"),
        help_text=_("For text stories."),
    )
    media_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name=_("Media URL"),
        help_text=_("Image or video URL for media stories."),
    )
    thumbnail_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name=_("Thumbnail URL"),
        help_text=_("Video thumbnail."),
    )
    background_color = models.CharField(
        max_length=7,
        blank=True,
        default="#000000",
        verbose_name=_("Background Color"),
        help_text=_("Hex color for text stories."),
    )
    font_style = models.CharField(
        max_length=50,
        blank=True,
        default="default",
        verbose_name=_("Font Style"),
    )
    duration_seconds = models.PositiveSmallIntegerField(
        default=5,
        verbose_name=_("Duration (seconds)"),
        help_text=_("How long the story shows before auto-advancing."),
    )
    expires_at = models.DateTimeField(
        db_index=True,
        verbose_name=_("Expires At"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
    )
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("View Count"),
    )
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default="all",
        verbose_name=_("Visibility"),
    )
    visibility_user_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Visibility User IDs"),
        help_text=_("For 'except' and 'selected' visibility modes."),
    )
    link_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Link URL"),
        help_text=_("Optional swipe-up link attached to story."),
    )
    link_label = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Link Label"),
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Location Tag"),
    )
    music_track = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Music Track"),
        help_text=_("{title, artist, preview_url, start_seconds}"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Story")
        verbose_name_plural = _("User Stories")
        indexes = [
            models.Index(fields=["user", "is_active", "expires_at"], name="msg_us_user_active_exp_idx"),
            models.Index(fields=["expires_at", "is_active"], name="msg_us_exp_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Story [{self.story_type}] by {self.user_id} expires={self.expires_at}"

    def save(self, *args, **kwargs) -> None:
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()


# ---------------------------------------------------------------------------
# StoryView  (NEW — Track who viewed a story)
# ---------------------------------------------------------------------------

class StoryView(TimestampedModel):
    """One record per (story, viewer) pair. Created when user views a story."""
    story = models.ForeignKey(
        UserStory,
        on_delete=models.CASCADE,
        related_name="views",
        verbose_name=_("Story"),
    )
    viewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="story_views",
        verbose_name=_("Viewer"),
    )
    viewed_at = models.DateTimeField(auto_now_add=True)
    reaction_emoji = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_("Reaction Emoji"),
        help_text=_("Optional quick emoji reaction on the story."),
    )
    reply_text = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Reply Text"),
        help_text=_("Optional direct reply message to the story poster."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Story View")
        verbose_name_plural = _("Story Views")
        constraints = [
            UniqueConstraint(fields=["story", "viewer"], name="msg_sv_unique_story_viewer"),
        ]
        ordering = ["-viewed_at"]

    def __str__(self) -> str:
        return f"{self.viewer_id} viewed story {self.story_id}"


# ---------------------------------------------------------------------------
# StoryHighlight  (NEW — Instagram-style pinned story highlights)
# ---------------------------------------------------------------------------

class StoryHighlight(TimestampedModel):
    """
    A collection of stories pinned permanently to a user's profile.
    Stories in highlights don't expire.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="story_highlights",
        verbose_name=_("User"),
    )
    title = models.CharField(
        max_length=50,
        verbose_name=_("Title"),
    )
    cover_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Cover Image URL"),
    )
    stories = models.ManyToManyField(
        UserStory,
        related_name="highlights",
        blank=True,
        verbose_name=_("Stories"),
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Story Highlight")
        verbose_name_plural = _("Story Highlights")
        ordering = ["order", "created_at"]

    def __str__(self) -> str:
        return f"Highlight: {self.title} by {self.user_id}"


# ---------------------------------------------------------------------------
# VoiceMessageTranscription  (NEW — Auto-transcribe voice messages)
# ---------------------------------------------------------------------------

class VoiceMessageTranscription(TimestampedModel):
    """
    Auto-transcription of AUDIO type ChatMessages.
    Uses Whisper/Google STT to convert voice messages to text.
    Cached permanently once transcribed.
    """
    message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="transcription",
        verbose_name=_("Message"),
    )
    transcribed_text = models.TextField(
        verbose_name=_("Transcribed Text"),
    )
    language = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name=_("Detected Language"),
    )
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Confidence Score"),
        help_text=_("0.0 to 1.0 confidence from the STT provider."),
    )
    provider = models.CharField(
        max_length=50,
        blank=True,
        default="whisper",
        verbose_name=_("STT Provider"),
        help_text=_("whisper, google, azure"),
    )
    duration_seconds = models.FloatField(
        default=0.0,
        verbose_name=_("Audio Duration (seconds)"),
    )
    waveform_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Waveform Data"),
        help_text=_("Array of amplitude values for UI waveform display [0.0..1.0]."),
    )
    is_processing = models.BooleanField(
        default=False,
        verbose_name=_("Is Processing"),
    )
    error = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Voice Message Transcription")
        verbose_name_plural = _("Voice Message Transcriptions")

    def __str__(self) -> str:
        return f"Transcription of msg {self.message_id} ({self.duration_seconds:.1f}s)"


# ---------------------------------------------------------------------------
# LinkPreview  (NEW — iMessage/Telegram link metadata preview)
# ---------------------------------------------------------------------------

class LinkPreview(TimestampedModel):
    """
    Cached OG/Twitter card metadata for URLs found in messages.
    Fetched once and cached permanently per URL.
    """
    url = models.URLField(
        max_length=2000,
        unique=True,
        verbose_name=_("URL"),
    )
    title = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Title"),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Description"),
    )
    image_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("Image URL"),
    )
    favicon_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Favicon URL"),
    )
    site_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Site Name"),
    )
    domain = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Domain"),
        db_index=True,
    )
    content_type = models.CharField(
        max_length=50,
        blank=True,
        default="website",
        verbose_name=_("Content Type"),
        help_text=_("website, article, video, music, profile, etc."),
    )
    video_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("Video URL"),
        help_text=_("For video OG cards."),
    )
    is_safe = models.BooleanField(
        default=True,
        verbose_name=_("Is Safe"),
        help_text=_("False if URL flagged by safe browsing check."),
    )
    fetch_error = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name=_("Fetch Error"),
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fetched At"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Link Preview")
        verbose_name_plural = _("Link Previews")
        indexes = [
            models.Index(fields=["domain"], name="msg_lp_domain_idx"),
        ]

    def __str__(self) -> str:
        return f"LinkPreview: {self.domain} — {self.title[:50]}"


# ---------------------------------------------------------------------------
# MessageLinkPreview  (NEW — Link a preview to a specific message)
# ---------------------------------------------------------------------------

class MessageLinkPreview(TimestampedModel):
    """Many-to-many between ChatMessage and LinkPreview (one message can have multiple links)."""
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="link_previews",
        verbose_name=_("Message"),
    )
    preview = models.ForeignKey(
        LinkPreview,
        on_delete=models.CASCADE,
        related_name="message_links",
        verbose_name=_("Link Preview"),
    )
    position = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Position"),
        help_text=_("Order the URL appears in the message."),
    )
    is_dismissed = models.BooleanField(
        default=False,
        verbose_name=_("Is Dismissed"),
        help_text=_("User manually dismissed this preview."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Link Preview")
        verbose_name_plural = _("Message Link Previews")
        ordering = ["position"]
        constraints = [
            UniqueConstraint(fields=["message", "preview"], name="msg_mlp_unique_msg_preview"),
        ]

    def __str__(self) -> str:
        return f"LinkPreview {self.preview_id} on msg {self.message_id}"


# ===========================================================================
# WORLD-CLASS ADDITIONAL MODELS
# ===========================================================================

# ---------------------------------------------------------------------------
# MediaAttachment  — Track every uploaded file with processing state
# ---------------------------------------------------------------------------

class MediaAttachment(TimestampedModel):
    """
    Every uploaded file (image, video, audio, document) is tracked here.
    Processing pipeline: PENDING → PROCESSING → READY / FAILED
    Allows retry on failure, NSFW check, virus scan, compression status.
    """
    STATUS_PENDING    = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_READY      = "ready"
    STATUS_FAILED     = "failed"
    STATUS_BLOCKED    = "blocked"

    STATUS_CHOICES = (
        (STATUS_PENDING,    "Pending Upload"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_READY,      "Ready"),
        (STATUS_FAILED,     "Failed"),
        (STATUS_BLOCKED,    "Blocked (NSFW/Virus)"),
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="media_attachments",
        verbose_name=_("Uploaded By"),
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_records",
        verbose_name=_("Associated Message"),
    )
    original_filename = models.CharField(
        max_length=500,
        verbose_name=_("Original Filename"),
    )
    file_key = models.CharField(
        max_length=1000,
        unique=True,
        verbose_name=_("Storage Key"),
        help_text=_("S3 object key or local path."),
    )
    original_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("Original CDN URL"),
    )
    compressed_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("Compressed URL"),
    )
    thumbnail_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("Thumbnail URL"),
    )
    webp_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        verbose_name=_("WebP URL"),
    )
    mimetype = models.CharField(
        max_length=100,
        verbose_name=_("MIME Type"),
    )
    file_size = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_("File Size (bytes)"),
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Width (px)"),
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Height (px)"),
    )
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)"),
        help_text=_("For audio/video files."),
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name=_("Processing Status"),
    )
    is_nsfw = models.BooleanField(
        default=False,
        verbose_name=_("Is NSFW"),
    )
    nsfw_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("NSFW Score"),
    )
    is_virus_scanned = models.BooleanField(
        default=False,
        verbose_name=_("Virus Scanned"),
    )
    is_virus_free = models.BooleanField(
        default=True,
        verbose_name=_("Virus Free"),
    )
    processing_error = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Processing Error"),
    )
    blurhash = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("BlurHash"),
        help_text=_("Compact image placeholder for progressive loading."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("EXIF data, video codec info, etc."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Media Attachment")
        verbose_name_plural = _("Media Attachments")
        indexes = [
            models.Index(fields=["uploaded_by", "status"], name="msg_ma_uploader_status_idx"),
            models.Index(fields=["message", "status"], name="msg_ma_message_status_idx"),
            models.Index(fields=["mimetype", "status"], name="msg_ma_mime_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Media: {self.original_filename} [{self.status}] by {self.uploaded_by_id}"

    @property
    def best_url(self) -> Optional[str]:
        """Return best URL for display (compressed > original)."""
        return self.compressed_url or self.webp_url or self.original_url

    @property
    def is_image(self) -> bool:
        return self.mimetype.startswith("image/")

    @property
    def is_video(self) -> bool:
        return self.mimetype.startswith("video/")

    @property
    def is_audio(self) -> bool:
        return self.mimetype.startswith("audio/")


# ---------------------------------------------------------------------------
# MessageReport  — User reports abusive messages
# ---------------------------------------------------------------------------

class MessageReport(TimestampedModel):
    """
    User-submitted report for an abusive/spam message.
    Feeds into the moderation queue.
    """
    REASON_SPAM       = "spam"
    REASON_ABUSE      = "abuse"
    REASON_HARASSMENT = "harassment"
    REASON_NSFW       = "nsfw"
    REASON_MISINFORM  = "misinformation"
    REASON_OTHER      = "other"

    REASON_CHOICES = (
        (REASON_SPAM,       "Spam"),
        (REASON_ABUSE,      "Abusive Content"),
        (REASON_HARASSMENT, "Harassment"),
        (REASON_NSFW,       "NSFW / Explicit"),
        (REASON_MISINFORM,  "Misinformation"),
        (REASON_OTHER,      "Other"),
    )

    STATUS_PENDING  = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_RESOLVED = "resolved"
    STATUS_DISMISSED= "dismissed"

    STATUS_CHOICES = (
        (STATUS_PENDING,   "Pending Review"),
        (STATUS_REVIEWED,  "Under Review"),
        (STATUS_RESOLVED,  "Resolved — Action Taken"),
        (STATUS_DISMISSED, "Dismissed — No Action"),
    )

    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name=_("Reported Message"),
    )
    reported_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
        verbose_name=_("Reported By"),
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name=_("Reason"),
    )
    details = models.TextField(
        blank=True,
        default="",
        max_length=1000,
        verbose_name=_("Additional Details"),
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name=_("Review Status"),
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
        verbose_name=_("Reviewed By"),
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed At"),
    )
    moderator_note = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Moderator Note"),
    )
    action_taken = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Action Taken"),
        help_text=_("e.g. 'message deleted', 'user warned', 'user banned'"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Report")
        verbose_name_plural = _("Message Reports")
        constraints = [
            UniqueConstraint(
                fields=["message", "reported_by"],
                name="msg_mr2_unique_msg_reporter",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="msg_mrpt_status_created_idx"),
            models.Index(fields=["reason", "status"], name="msg_mrpt_reason_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Report [{self.reason}] msg={self.message_id} by={self.reported_by_id} [{self.status}]"


# ---------------------------------------------------------------------------
# UserDevice  — Detailed device tracking (beyond DeviceToken)
# ---------------------------------------------------------------------------

class UserDevice(TimestampedModel):
    """
    Detailed device record for security & multi-device management.
    Tracks login history, trusted status, and suspicious activity.
    Separate from DeviceToken (which is just push token).
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="registered_devices",
        verbose_name=_("User"),
    )
    device_id = models.CharField(
        max_length=256,
        verbose_name=_("Device ID"),
        help_text=_("Unique hardware ID or fingerprint."),
    )
    device_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Device Name"),
        help_text=_("e.g. 'Rafi iPhone 14', 'Work Laptop'"),
    )
    platform = models.CharField(
        max_length=20,
        verbose_name=_("Platform"),
        help_text=_("android, ios, web, desktop"),
    )
    os_version = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("OS Version"),
    )
    app_version = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name=_("App Version"),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("Last IP Address"),
    )
    location_city = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Last Location City"),
    )
    location_country = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Last Location Country"),
    )
    is_trusted = models.BooleanField(
        default=True,
        verbose_name=_("Is Trusted"),
        help_text=_("Untrusted devices require re-verification."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("False = user logged out from this device."),
    )
    first_login_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("First Login At"),
    )
    last_active_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Last Active At"),
    )
    session_key = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name=_("Session Key"),
        help_text=_("JWT or session token reference for this device."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Device")
        verbose_name_plural = _("User Devices")
        constraints = [
            UniqueConstraint(fields=["user", "device_id"], name="msg_ud_unique_user_device"),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="msg_ud_user_active_idx"),
            models.Index(fields=["last_active_at"], name="msg_ud_last_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.device_name or self.device_id} ({self.platform}) — {self.user_id}"


# ---------------------------------------------------------------------------
# ChatMention  — Fast lookup for @mentions
# ---------------------------------------------------------------------------

class ChatMention(TimestampedModel):
    """
    Denormalized mention record for fast @mention queries.
    Created alongside UserInbox MENTION items.
    Allows instant 'mentioned messages' feed without full-text scan.
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="mention_records",
        verbose_name=_("Message"),
    )
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="mentions",
        verbose_name=_("Chat"),
    )
    mentioned_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_mentions",
        verbose_name=_("Mentioned User"),
    )
    mentioned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_mentions",
        verbose_name=_("Mentioned By"),
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Read"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Chat Mention")
        verbose_name_plural = _("Chat Mentions")
        constraints = [
            UniqueConstraint(
                fields=["message", "mentioned_user"],
                name="msg_cm2_unique_msg_user",
            ),
        ]
        indexes = [
            models.Index(fields=["mentioned_user", "is_read"], name="msg_cm2_user_read_idx"),
        ]

    def __str__(self) -> str:
        return f"@{self.mentioned_user_id} in msg {self.message_id}"


# ---------------------------------------------------------------------------
# MessageSearchIndex  — Fallback search index (when Elasticsearch not available)
# ---------------------------------------------------------------------------

class MessageSearchIndex(TimestampedModel):
    """
    DB-level search index for messages when Elasticsearch is not configured.
    Stores preprocessed, searchable text for fast LIKE queries.
    Updated in background after each message.
    """
    message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="search_index",
        verbose_name=_("Message"),
    )
    chat = models.ForeignKey(
        InternalChat,
        on_delete=models.CASCADE,
        related_name="search_index",
        verbose_name=_("Chat"),
    )
    search_text = models.TextField(
        verbose_name=_("Search Text"),
        help_text=_("Lowercased + stripped version of message content for fast search."),
    )
    indexed_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Indexed At"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Search Index")
        verbose_name_plural = _("Message Search Indices")
        indexes = [
            models.Index(fields=["chat", "indexed_at"], name="msg_msi_chat_indexed_idx"),
        ]

    def __str__(self) -> str:
        return f"Index for msg {self.message_id}"


# ===========================================================================
# CPA PLATFORM MESSAGING MODELS (CPAlead-style)
# ===========================================================================

# ---------------------------------------------------------------------------
# CPANotification — Real-time CPA event notifications
# ---------------------------------------------------------------------------

class CPANotification(TimestampedModel):
    """
    Business-event-driven notifications for CPA affiliate platform.
    Created automatically when business events occur:
    - Offer approved/rejected
    - Conversion received/approved
    - Payout processed
    - Account status changes
    - Milestones reached

    Different from UserInbox (general messages) — these are typed,
    structured, and tied to specific business objects.
    """
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cpa_notifications",
        db_index=True,
        verbose_name=_("Recipient"),
    )
    notification_type = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name=_("Notification Type"),
        help_text=_("CPANotificationType value."),
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
    )
    body = models.TextField(
        verbose_name=_("Body"),
    )
    priority = models.CharField(
        max_length=10,
        default="NORMAL",
        verbose_name=_("Priority"),
    )
    # Reference to the business object that triggered this notification
    object_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Object Type"),
        help_text=_("e.g. 'offer', 'conversion', 'payout', 'affiliate'"),
    )
    object_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Object ID"),
        help_text=_("ID of the business object (offer_id, payout_id, etc.)"),
    )
    action_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Action URL"),
        help_text=_("Deep link or URL for CTA button in notification."),
    )
    action_label = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Action Label"),
        help_text=_("e.g. 'View Offer', 'Check Payment', 'Appeal Decision'"),
    )
    # Rich data payload for frontend rendering
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Payload"),
        help_text=_("Structured data for rich notification rendering (offer details, amount, etc.)"),
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
    is_dismissed = models.BooleanField(
        default=False,
        verbose_name=_("Is Dismissed"),
    )
    # Delivery tracking
    push_sent    = models.BooleanField(default=False, verbose_name=_("Push Sent"))
    email_sent   = models.BooleanField(default=False, verbose_name=_("Email Sent"))
    sms_sent     = models.BooleanField(default=False, verbose_name=_("SMS Sent"))
    push_sent_at = models.DateTimeField(null=True, blank=True)
    email_sent_at= models.DateTimeField(null=True, blank=True)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("CPA Notification")
        verbose_name_plural = _("CPA Notifications")
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"],   name="msg_cpan_rcpt_read_idx"),
            models.Index(fields=["recipient", "notification_type"],        name="msg_cpan_rcpt_type_idx"),
            models.Index(fields=["notification_type", "created_at"],       name="msg_cpan_type_created_idx"),
            models.Index(fields=["object_type", "object_id"],              name="msg_cpan_obj_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.notification_type}] → {self.recipient_id}: {self.title[:50]}"

    def mark_read(self) -> None:
        if self.is_read:
            return
        now = timezone.now()
        CPANotification.objects.filter(pk=self.pk).update(is_read=True, read_at=now)
        self.is_read = True
        self.read_at = now


# ---------------------------------------------------------------------------
# MessageTemplate — Reusable message templates for admins
# ---------------------------------------------------------------------------

class MessageTemplate(TimestampedModel):
    """
    Pre-written message templates admins can reuse for common scenarios.
    Supports variable substitution: {affiliate_name}, {offer_name}, {amount}, etc.
    Like CPAlead's "quick reply" templates for account managers.
    """
    name = models.CharField(
        max_length=200,
        verbose_name=_("Template Name"),
        help_text=_("Internal name, e.g. 'Payout Processed - Standard'"),
    )
    category = models.CharField(
        max_length=15,
        default="custom",
        verbose_name=_("Category"),
    )
    subject = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name=_("Subject / Title"),
    )
    body = models.TextField(
        verbose_name=_("Body Template"),
        help_text=_(
            "Supports placeholders: {affiliate_name}, {offer_name}, {amount}, "
            "{payout_date}, {manager_name}, {platform_name}, {action_url}"
        ),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    usage_count = models.PositiveIntegerField(default=0, verbose_name=_("Times Used"))
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="messaging_created_templates",
        verbose_name=_("Created By"),
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("e.g. ['payout', 'urgent', 'approved']"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Message Template")
        verbose_name_plural = _("Message Templates")
        ordering = ["-usage_count", "name"]

    def __str__(self) -> str:
        return f"Template: {self.name} [{self.category}]"

    def render(self, context: dict) -> tuple[str, str]:
        """
        Render template with context variables.
        Returns (rendered_subject, rendered_body).
        """
        subject = self.subject
        body    = self.body
        for key, value in context.items():
            placeholder = "{" + key + "}"
            subject = subject.replace(placeholder, str(value))
            body    = body.replace(placeholder, str(value))
        # Increment usage count
        MessageTemplate.objects.filter(pk=self.pk).update(usage_count=self.usage_count + 1)
        return subject, body


# ---------------------------------------------------------------------------
# CPABroadcast — CPA-specific targeted broadcast
# ---------------------------------------------------------------------------

class CPABroadcast(TimestampedModel):
    """
    Targeted broadcast for CPA platform with audience filtering.
    Extends AdminBroadcast concept with CPA-specific audience targeting:
    - All affiliates running a specific offer
    - Affiliates in a specific vertical/GEO
    - Top performers
    - New affiliates
    - By account tier

    Unlike AdminBroadcast (general), CPABroadcast is tightly integrated
    with the affiliate database for precise targeting.
    """
    title = models.CharField(max_length=300, verbose_name=_("Title"))
    body  = models.TextField(verbose_name=_("Body"))
    notification_type = models.CharField(
        max_length=40,
        blank=True,
        default="system.announcement",
        verbose_name=_("Notification Type"),
    )
    priority = models.CharField(
        max_length=10,
        default="NORMAL",
        verbose_name=_("Priority"),
    )
    # Audience targeting
    audience_filter = models.CharField(
        max_length=20,
        default="all",
        verbose_name=_("Audience Filter"),
    )
    audience_params = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Audience Parameters"),
        help_text=_(
            "Filter params: {offer_id, vertical, country, tier, manager_id, "
            "min_earnings, max_earnings}"
        ),
    )
    # Delivery options
    send_push     = models.BooleanField(default=True,  verbose_name=_("Send Push Notification"))
    send_email    = models.BooleanField(default=False, verbose_name=_("Send Email"))
    send_inbox    = models.BooleanField(default=True,  verbose_name=_("Create Inbox Item"))
    send_sms      = models.BooleanField(default=False, verbose_name=_("Send SMS"))
    action_url    = models.CharField(max_length=500, blank=True, default="", verbose_name=_("CTA URL"))
    action_label  = models.CharField(max_length=100, blank=True, default="", verbose_name=_("CTA Label"))
    template      = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="broadcasts",
        verbose_name=_("Template Used"),
    )
    # Status
    status = models.CharField(
        max_length=15,
        default="DRAFT",
        db_index=True,
        verbose_name=_("Status"),
    )
    scheduled_at    = models.DateTimeField(null=True, blank=True, verbose_name=_("Scheduled At"))
    sent_at         = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent At"))
    recipient_count = models.PositiveIntegerField(default=0, verbose_name=_("Recipients"))
    delivered_count = models.PositiveIntegerField(default=0, verbose_name=_("Delivered"))
    opened_count    = models.PositiveIntegerField(default=0, verbose_name=_("Opened"))
    clicked_count   = models.PositiveIntegerField(default=0, verbose_name=_("CTA Clicked"))
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cpa_broadcasts",
        verbose_name=_("Created By"),
    )
    error_message = models.TextField(blank=True, default="", verbose_name=_("Error"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("CPA Broadcast")
        verbose_name_plural = _("CPA Broadcasts")
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="msg_cpab_status_sched_idx"),
        ]

    def __str__(self) -> str:
        return f"CPABroadcast: {self.title[:60]} [{self.status}]"

    @property
    def open_rate(self) -> Optional[float]:
        if not self.delivered_count:
            return None
        return round(self.opened_count / self.delivered_count * 100, 1)

    @property
    def click_rate(self) -> Optional[float]:
        if not self.delivered_count:
            return None
        return round(self.clicked_count / self.delivered_count * 100, 1)


# ---------------------------------------------------------------------------
# NotificationRead — Track broadcast open/click (analytics)
# ---------------------------------------------------------------------------

class NotificationRead(TimestampedModel):
    """
    Track when a user opens or clicks a CPA broadcast.
    Used for open rate / click rate analytics.
    """
    broadcast  = models.ForeignKey(
        CPABroadcast,
        on_delete=models.CASCADE,
        related_name="reads",
        verbose_name=_("Broadcast"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_reads",
        verbose_name=_("User"),
    )
    opened_at  = models.DateTimeField(auto_now_add=True, verbose_name=_("Opened At"))
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name=_("CTA Clicked At"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Notification Read")
        verbose_name_plural = _("Notification Reads")
        constraints = [
            UniqueConstraint(fields=["broadcast", "user"], name="msg_nr_unique_broadcast_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} opened broadcast {self.broadcast_id}"


# ---------------------------------------------------------------------------
# AffiliateConversationThread — Direct message thread between affiliate and manager
# ---------------------------------------------------------------------------

class AffiliateConversationThread(TimestampedModel):
    """
    Dedicated conversation thread between an affiliate and their account manager.
    Unlike SupportThread (which is ticket-based), this is an ongoing
    relationship chat — like CPAlead's affiliate ↔ manager inbox.
    """
    STATUS_CHOICES = (
        ("active",   "Active"),
        ("archived", "Archived"),
    )

    affiliate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="affiliate_threads",
        verbose_name=_("Affiliate"),
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="managed_threads",
        verbose_name=_("Account Manager"),
    )
    # Link to the underlying InternalChat
    chat = models.OneToOneField(
        InternalChat,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="affiliate_thread",
        verbose_name=_("Chat"),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
        verbose_name=_("Status"),
    )
    affiliate_unread  = models.PositiveIntegerField(default=0, verbose_name=_("Affiliate Unread"))
    manager_unread    = models.PositiveIntegerField(default=0, verbose_name=_("Manager Unread"))
    last_message_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Message At"))
    last_message_by   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="last_sent_in_threads",
        verbose_name=_("Last Message By"),
    )
    notes = models.TextField(
        blank=True, default="",
        verbose_name=_("Manager Notes"),
        help_text=_("Private notes visible only to the manager."),
    )
    tags = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Tags"),
        help_text=_("e.g. ['vip', 'payment-issue', 'fraud-watch']"),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Affiliate Conversation Thread")
        verbose_name_plural = _("Affiliate Conversation Threads")
        constraints = [
            UniqueConstraint(fields=["affiliate"], name="msg_act_unique_affiliate"),
        ]
        indexes = [
            models.Index(fields=["manager", "status"], name="msg_act_manager_status_idx"),
            models.Index(fields=["last_message_at"],   name="msg_act_last_msg_idx"),
        ]

    def __str__(self) -> str:
        return f"Thread: affiliate={self.affiliate_id} ↔ manager={self.manager_id}"
