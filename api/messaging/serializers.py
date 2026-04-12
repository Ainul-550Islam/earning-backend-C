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


# ============================================================================
# NEW SERIALIZERS (appended — existing serializers unchanged above)
# ============================================================================

from .models import (
    MessageReaction, UserPresence, CallSession,
    AnnouncementChannel, ScheduledMessage, MessagePin,
    BotConfig, MessagingWebhook, UserBlock, MessageTranslation, DeviceToken,
)


class MessageReactionSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = MessageReaction
        fields = ["id", "message", "user", "user_name", "emoji", "custom_emoji", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_user_name(self, obj) -> str:
        try:
            return obj.user.get_full_name() or obj.user.username
        except Exception:
            return ""


class UserPresenceSerializer(serializers.ModelSerializer):
    effective_status = serializers.ReadOnlyField()

    class Meta:
        model = UserPresence
        fields = [
            "user", "status", "effective_status", "last_seen_at",
            "last_seen_on", "custom_status", "custom_status_emoji",
            "custom_status_expires_at", "is_invisible",
        ]
        read_only_fields = ["last_seen_at", "effective_status"]


class CallSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSession
        fields = [
            "id", "call_type", "status", "chat", "initiated_by", "room_id",
            "started_at", "ended_at", "duration_seconds", "is_recorded", "created_at",
        ]
        read_only_fields = ["id", "room_id", "created_at"]


class AnnouncementChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementChannel
        fields = [
            "id", "name", "slug", "description", "channel_type",
            "avatar", "is_verified", "subscriber_count", "post_count",
            "last_post_at", "created_at",
        ]
        read_only_fields = ["id", "slug", "subscriber_count", "post_count", "created_at"]


class ScheduledMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledMessage
        fields = [
            "id", "chat", "sender", "content", "message_type",
            "attachments", "scheduled_for", "status", "created_at",
        ]
        read_only_fields = ["id", "sender", "status", "created_at"]


class MessagePinSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessagePin
        fields = ["id", "chat", "message", "pinned_by", "pinned_at"]
        read_only_fields = ["id", "pinned_at"]


class BotConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotConfig
        fields = [
            "id", "name", "chat", "trigger_type", "trigger_value",
            "response_template", "is_active", "priority",
            "delay_seconds", "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class MessagingWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessagingWebhook
        fields = [
            "id", "name", "url", "events", "is_active",
            "failure_count", "last_triggered_at", "created_at",
        ]
        read_only_fields = ["id", "failure_count", "last_triggered_at", "created_at"]


class UserBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBlock
        fields = ["id", "blocker", "blocked", "reason", "created_at"]
        read_only_fields = ["id", "blocker", "created_at"]


class MessageTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTranslation
        fields = [
            "id", "message", "target_language", "translated_content",
            "source_language", "provider", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "platform", "device_name", "app_version", "is_active", "last_used_at"]
        read_only_fields = ["id", "last_used_at"]


# ── Final 6% Serializers ──────────────────────────────────────────────────────

from .models import (
    MessageEditHistory, DisappearingMessageConfig,
    UserStory, StoryView, StoryHighlight,
    VoiceMessageTranscription, LinkPreview, MessageLinkPreview,
)


class MessageEditHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageEditHistory
        fields = ["id", "message", "edited_by", "previous_content",
                  "edit_number", "edit_reason", "created_at"]
        read_only_fields = ["id", "created_at"]


class DisappearingMessageConfigSerializer(serializers.ModelSerializer):
    ttl_display = serializers.ReadOnlyField()

    class Meta:
        model = DisappearingMessageConfig
        fields = ["chat", "is_enabled", "ttl_seconds", "ttl_display",
                  "enabled_by", "enabled_at"]
        read_only_fields = ["enabled_by", "enabled_at", "ttl_display"]


class UserStorySerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = UserStory
        fields = [
            "id", "user", "story_type", "content", "media_url",
            "thumbnail_url", "background_color", "font_style",
            "duration_seconds", "expires_at", "is_active", "view_count",
            "visibility", "link_url", "link_label", "location",
            "music_track", "is_expired", "created_at",
        ]
        read_only_fields = ["id", "view_count", "is_active", "is_expired", "created_at"]


class StoryViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryView
        fields = ["id", "story", "viewer", "viewed_at", "reaction_emoji", "reply_text"]
        read_only_fields = ["id", "viewed_at"]


class VoiceMessageTranscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceMessageTranscription
        fields = [
            "id", "message", "transcribed_text", "language",
            "confidence", "provider", "duration_seconds",
            "waveform_data", "is_processing", "error", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LinkPreviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkPreview
        fields = [
            "id", "url", "title", "description", "image_url",
            "favicon_url", "site_name", "domain", "content_type",
            "video_url", "is_safe", "fetched_at",
        ]
        read_only_fields = ["id", "fetched_at"]


# ── CPA Platform Serializers ──────────────────────────────────────────────────

from .models import CPANotification, CPABroadcast, MessageTemplate, AffiliateConversationThread


class CPANotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CPANotification
        fields = [
            "id", "notification_type", "title", "body", "priority",
            "object_type", "object_id", "action_url", "action_label",
            "payload", "is_read", "read_at", "push_sent", "email_sent",
            "created_at",
        ]
        read_only_fields = ["id", "push_sent", "email_sent", "created_at"]


class CPABroadcastSerializer(serializers.ModelSerializer):
    open_rate  = serializers.ReadOnlyField()
    click_rate = serializers.ReadOnlyField()

    class Meta:
        model = CPABroadcast
        fields = [
            "id", "title", "body", "notification_type", "priority",
            "audience_filter", "audience_params",
            "send_push", "send_email", "send_inbox", "send_sms",
            "action_url", "action_label", "status",
            "scheduled_at", "sent_at",
            "recipient_count", "delivered_count", "opened_count", "clicked_count",
            "open_rate", "click_rate", "created_by", "created_at",
        ]
        read_only_fields = [
            "id", "status", "sent_at", "recipient_count", "delivered_count",
            "opened_count", "clicked_count", "created_by", "created_at",
        ]


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = [
            "id", "name", "category", "subject", "body",
            "tags", "is_active", "usage_count", "created_by", "created_at",
        ]
        read_only_fields = ["id", "usage_count", "created_by", "created_at"]


class AffiliateThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffiliateConversationThread
        fields = [
            "id", "affiliate", "manager", "chat", "status",
            "affiliate_unread", "manager_unread",
            "last_message_at", "last_message_by", "tags", "created_at",
        ]
        read_only_fields = [
            "id", "affiliate_unread", "manager_unread",
            "last_message_at", "last_message_by", "created_at",
        ]
