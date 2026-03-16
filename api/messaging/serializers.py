"""
Messaging Serializers — DRF serializers with full validation.
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import (
    MessageType,
    BroadcastAudienceType,
    SupportThreadPriority,
    InboxItemType,
)
from .constants import MAX_MESSAGE_LENGTH, MAX_BROADCAST_BODY_LENGTH
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


# ---------------------------------------------------------------------------
# ChatParticipant
# ---------------------------------------------------------------------------

class ChatParticipantSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ChatParticipant
        fields = ["id", "user", "user_display_name", "role", "last_read_at", "is_muted", "joined_at"]
        read_only_fields = ["id", "joined_at"]

    def get_user_display_name(self, obj: ChatParticipant) -> str:
        user = obj.user
        if not user:
            return ""
        try:
            full = f"{user.first_name or ''} {user.last_name or ''}".strip()
            return full or getattr(user, "username", str(user.pk))
        except Exception:
            return str(obj.user_id)


# ---------------------------------------------------------------------------
# InternalChat
# ---------------------------------------------------------------------------

class InternalChatSerializer(serializers.ModelSerializer):
    participants = ChatParticipantSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = InternalChat
        fields = [
            "id", "name", "is_group", "status", "status_display",
            "is_active", "last_message_at", "participants", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        if self.initial_data.get("is_group") and not (value or "").strip():
            raise serializers.ValidationError(_("Group chats must have a name."))
        return (value or "").strip()

    def validate_metadata(self, value: dict) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("metadata must be a JSON object."))
        return value


class InternalChatListSerializer(serializers.ModelSerializer):
    """Lightweight for list views."""
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    unread_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InternalChat
        fields = ["id", "name", "is_group", "status", "status_display",
                  "last_message_at", "unread_count"]

    def get_unread_count(self, obj: InternalChat) -> int:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        try:
            participant = obj.participants.get(user=request.user)
            if participant.last_read_at is None:
                return obj.messages.visible().count()
            return obj.messages.visible().filter(
                created_at__gt=participant.last_read_at
            ).exclude(sender=request.user).count()
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            "id", "chat", "sender", "sender_name", "content", "message_type",
            "status", "attachments", "reply_to", "is_edited", "edited_at",
            "is_deleted", "metadata", "created_at",
        ]
        read_only_fields = ["id", "status", "is_edited", "edited_at", "created_at"]

    def get_sender_name(self, obj: ChatMessage) -> str:
        if not obj.sender:
            return "System"
        try:
            full = f"{obj.sender.first_name or ''} {obj.sender.last_name or ''}".strip()
            return full or getattr(obj.sender, "username", str(obj.sender_id))
        except Exception:
            return str(obj.sender_id)

    def validate_content(self, value: str) -> str:
        if len(value) > MAX_MESSAGE_LENGTH:
            raise serializers.ValidationError(
                _(f"Content exceeds maximum length of {MAX_MESSAGE_LENGTH}.")
            )
        return value

    def validate_message_type(self, value: str) -> str:
        if value not in MessageType.values:
            raise serializers.ValidationError(
                _(f"Invalid message_type. Valid: {MessageType.values}")
            )
        return value


class SendMessageSerializer(serializers.Serializer):
    """Input serializer for send_chat_message endpoint."""
    content = serializers.CharField(max_length=MAX_MESSAGE_LENGTH, required=False, default="")
    message_type = serializers.ChoiceField(choices=MessageType.choices, default=MessageType.TEXT)
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    attachments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        max_length=10,
    )
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, attrs: dict) -> dict:
        if attrs.get("message_type") == MessageType.TEXT and not attrs.get("content", "").strip():
            raise serializers.ValidationError(
                {"content": _("content is required for TEXT messages.")}
            )
        return attrs


# ---------------------------------------------------------------------------
# AdminBroadcast
# ---------------------------------------------------------------------------

class AdminBroadcastSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    delivery_rate = serializers.FloatField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = AdminBroadcast
        fields = [
            "id", "title", "body", "status", "status_display",
            "audience_type", "audience_filter", "scheduled_at",
            "sent_at", "recipient_count", "delivered_count",
            "delivery_rate", "is_editable", "error_message",
            "metadata", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "sent_at", "recipient_count",
            "delivered_count", "error_message", "created_at", "updated_at",
        ]

    def validate_title(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("title must not be empty."))
        return value.strip()

    def validate_body(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("body must not be empty."))
        if len(value) > MAX_BROADCAST_BODY_LENGTH:
            raise serializers.ValidationError(
                _(f"body exceeds max length of {MAX_BROADCAST_BODY_LENGTH}.")
            )
        return value.strip()

    def validate_audience_type(self, value: str) -> str:
        if value not in BroadcastAudienceType.values:
            raise serializers.ValidationError(
                _(f"Invalid audience_type. Valid: {BroadcastAudienceType.values}")
            )
        return value


# ---------------------------------------------------------------------------
# SupportThread
# ---------------------------------------------------------------------------

class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            "id", "thread", "sender", "sender_name", "content",
            "is_agent_reply", "is_internal_note", "attachments", "created_at",
        ]
        read_only_fields = ["id", "is_agent_reply", "created_at"]

    def get_sender_name(self, obj: SupportMessage) -> str:
        if not obj.sender:
            return "System"
        try:
            full = f"{obj.sender.first_name or ''} {obj.sender.last_name or ''}".strip()
            return full or getattr(obj.sender, "username", str(obj.sender_id))
        except Exception:
            return str(obj.sender_id)


class SupportThreadSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    is_open_for_reply = serializers.BooleanField(read_only=True)
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportThread
        fields = [
            "id", "user", "assigned_agent", "subject", "status", "status_display",
            "priority", "priority_display", "is_open_for_reply",
            "last_reply_at", "resolved_at", "closed_at",
            "messages", "metadata", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "resolved_at", "closed_at", "last_reply_at",
            "created_at", "updated_at",
        ]

    def validate_priority(self, value: str) -> str:
        if value not in SupportThreadPriority.values:
            raise serializers.ValidationError(
                _(f"Invalid priority. Valid: {SupportThreadPriority.values}")
            )
        return value


class CreateSupportThreadSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=500)
    initial_message = serializers.CharField(max_length=MAX_MESSAGE_LENGTH)
    priority = serializers.ChoiceField(
        choices=SupportThreadPriority.choices,
        default=SupportThreadPriority.NORMAL,
    )

    def validate_subject(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("subject must not be empty."))
        return value.strip()

    def validate_initial_message(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("initial_message must not be empty."))
        return value.strip()


# ---------------------------------------------------------------------------
# UserInbox
# ---------------------------------------------------------------------------

class UserInboxSerializer(serializers.ModelSerializer):
    item_type_display = serializers.CharField(source="get_item_type_display", read_only=True)
    is_unread = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserInbox
        fields = [
            "id", "item_type", "item_type_display", "source_id",
            "title", "preview", "is_read", "is_unread", "read_at",
            "is_archived", "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at", "read_at"]
