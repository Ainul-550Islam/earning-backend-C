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
            "is_deleted", "is_forwarded", "metadata", "created_at",
            # Part 20 (world-system audit): buttons/select-menus a bot
            # attached to this message, if any. Read-only - written only by
            # services.render_interactive_blocks() inside process_bot_triggers()
            # / process_bot_interaction(), never directly by a client.
            "interactive_blocks",
        ]
        read_only_fields = [
            "id", "status", "is_edited", "edited_at", "created_at",
            "interactive_blocks",
        ]

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

    def validate_audience_filter(self, value):
        """
        Validate audience_filter dict keys and value types.
        Prevents malformed filter dicts from reaching the broadcast service.
        """
        if value is None or value == {}:
            return value or {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("audience_filter must be a JSON object.")

        ALLOWED_KEYS = {
            "countries", "languages", "min_balance", "max_balance",
            "registration_after", "registration_before", "is_verified",
            "tags", "exclude_tags", "affiliate_ids", "exclude_affiliate_ids",
            "min_conversions", "max_conversions", "offer_ids",
        }
        unknown = set(value.keys()) - ALLOWED_KEYS
        if unknown:
            raise serializers.ValidationError(
                f"audience_filter contains unknown keys: {sorted(unknown)}. "
                f"Allowed keys: {sorted(ALLOWED_KEYS)}"
            )
        list_fields = {"countries", "languages", "tags", "exclude_tags",
                       "affiliate_ids", "exclude_affiliate_ids", "offer_ids"}
        for field in list_fields:
            if field in value and not isinstance(value[field], list):
                raise serializers.ValidationError(
                    f"audience_filter.{field} must be a list."
                )
        for field in ("min_balance", "max_balance", "min_conversions", "max_conversions"):
            if field in value:
                try:
                    if float(value[field]) < 0:
                        raise serializers.ValidationError(
                            f"audience_filter.{field} must be non-negative."
                        )
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        f"audience_filter.{field} must be a number."
                    )
        return value

    def validate_scheduled_at(self, value):
        """Reject scheduled_at in the past."""
        if value is not None:
            from django.utils import timezone
            if value <= timezone.now():
                raise serializers.ValidationError(
                    "scheduled_at must be a future datetime."
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
    is_closed = serializers.BooleanField(read_only=True)
    is_resolved = serializers.BooleanField(read_only=True)
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportThread
        fields = [
            "id", "user", "assigned_agent", "subject", "status", "status_display",
            "priority", "priority_display", "is_open_for_reply", "is_closed", "is_resolved",
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
    BotConfig, BotInteraction, MessagingWebhook, UserBlock, MessageTranslation, DeviceToken,
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

    def validate_scheduled_for(self, value):
        """Reject scheduled_for dates in the past."""
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError(
                "scheduled_for must be a future datetime. "
                "Provide a datetime at least 60 seconds from now."
            )
        return value

    def validate_content(self, value):
        """Reject empty content for scheduled messages."""
        if not value or not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return value.strip()


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
            # Part 20 (world-system audit): SLASH_COMMAND arg documentation
            # and interactive response blocks (buttons/select-menus). Both
            # default to [] so existing KEYWORD/REGEX/ALWAYS/NEW_USER bots
            # are completely unaffected - a bot with no response_blocks
            # sends a plain-text reply exactly as it did before Part 20.
            "command_args_schema", "response_blocks",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class BotInteractionSerializer(serializers.ModelSerializer):
    """Part 20 (world-system audit): log entry for one interactive-component
    click (button / select-menu pick) on a bot message. Created by
    services.process_bot_interaction() via BotInteractionView - not
    intended to be created directly through this serializer, but it's
    registered the same way BotResponseSerializer is, for admin/monitoring
    read access via BotInteractionViewSet.
    """

    class Meta:
        model = BotInteraction
        fields = [
            "id", "source_message", "bot", "user",
            "action_id", "value", "resulting_message", "created_at",
        ]
        read_only_fields = ["id", "bot", "resulting_message", "created_at"]


class MessagingWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessagingWebhook
        fields = [
            "id", "name", "url", "events", "is_active",
            "failure_count", "last_triggered_at", "created_at",
        ]
        read_only_fields = ["id", "failure_count", "last_triggered_at", "created_at"]

    def validate_url(self, value):
        """
        Validate webhook URL for:
        1. Must use HTTPS scheme (HTTP is rejected — webhooks carry signed payloads
           but HTTPS prevents MitM interception of webhook content).
        2. SSRF protection — reject requests to private/internal IP ranges,
           loopback addresses, cloud metadata endpoints, and non-routable networks.
        """
        import ipaddress
        from urllib.parse import urlparse

        parsed = urlparse(value)

        # Enforce HTTPS
        if parsed.scheme != "https":
            raise serializers.ValidationError(
                "Webhook URL must use HTTPS. HTTP URLs are not allowed — "
                "webhook payloads contain sensitive data and must be encrypted in transit."
            )

        hostname = parsed.hostname or ""
        if not hostname:
            raise serializers.ValidationError("Webhook URL must have a valid hostname.")

        # SSRF: reject known internal/cloud metadata hostnames
        BLOCKED_HOSTNAMES = {
            "localhost",
            "metadata.google.internal",
            "metadata.internal",
            "169.254.169.254",      # AWS/GCP/Azure instance metadata
            "100.100.100.200",      # Alibaba Cloud metadata
            "instance-data",
        }
        if hostname.lower() in BLOCKED_HOSTNAMES:
            raise serializers.ValidationError(
                f"Webhook URL points to a blocked hostname: {hostname!r}. "
                "Internal and cloud metadata endpoints are not allowed."
            )

        # SSRF: reject private/loopback IP ranges if the hostname looks like an IP
        try:
            ip = ipaddress.ip_address(hostname)
            BLOCKED_RANGES = [
                ipaddress.ip_network("127.0.0.0/8"),     # loopback
                ipaddress.ip_network("10.0.0.0/8"),      # private class A
                ipaddress.ip_network("172.16.0.0/12"),   # private class B
                ipaddress.ip_network("192.168.0.0/16"),  # private class C
                ipaddress.ip_network("169.254.0.0/16"),  # link-local / metadata
                ipaddress.ip_network("::1/128"),         # IPv6 loopback
                ipaddress.ip_network("fc00::/7"),        # IPv6 unique local
                ipaddress.ip_network("fe80::/10"),       # IPv6 link-local
            ]
            for blocked in BLOCKED_RANGES:
                if ip in blocked:
                    raise serializers.ValidationError(
                        f"Webhook URL points to a private or reserved IP address ({ip}). "
                        "Only publicly routable IP addresses are allowed."
                    )
        except ValueError:
            # Not an IP address — hostname will resolve at delivery time.
            # We cannot do full DNS resolution here without blocking the request.
            # The delivery task should implement a post-DNS SSRF check.
            pass

        return value

    def validate_events(self, value):
        """Validate that all subscribed event types are known."""
        VALID_EVENTS = {
            "message.sent", "message.edited", "message.deleted",
            "message.delivered", "message.read", "message.forwarded",
            "reaction.added", "reaction.removed",
            "call.started", "call.ended",
            "broadcast.sent",
            "support.created", "support.resolved",
            "cpa.conversion", "cpa.payout",
        }
        if not isinstance(value, list):
            raise serializers.ValidationError("events must be a list of event type strings.")
        unknown = [e for e in value if e not in VALID_EVENTS]
        if unknown:
            raise serializers.ValidationError(
                f"Unknown event type(s): {unknown}. "
                f"Valid types: {sorted(VALID_EVENTS)}"
            )
        if not value:
            raise serializers.ValidationError(
                "events cannot be empty. Subscribe to at least one event type."
            )
        return value


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


# ── 10 Missing Serializers ────────────────────────────────────────────────────

from .models import (  # noqa: E402  (already imported above, safe to re-import)
    BotResponse,
    ChannelMember,
    ChatMention,
    MediaAttachment,
    MessageReport,
    MessageSearchIndex,
    NotificationRead,
    PollVote,
    UserDevice,
    WebhookDelivery,
)


class BotResponseSerializer(serializers.ModelSerializer):
    """Log entry for every auto-reply the bot sent."""

    class Meta:
        model = BotResponse
        fields = [
            "id",
            "bot",
            "trigger_message",
            "sent_message",
            "was_successful",
            "error",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ChannelMemberSerializer(serializers.ModelSerializer):
    """Membership record linking a User to an AnnouncementChannel."""

    class Meta:
        model = ChannelMember
        fields = [
            "id",
            "channel",
            "user",
            "is_admin",
            "notification_preference",
            "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]


class ChatMentionSerializer(serializers.ModelSerializer):
    """Denormalised @mention record for fast mention-feed queries."""

    class Meta:
        model = ChatMention
        fields = [
            "id",
            "message",
            "chat",
            "mentioned_user",
            "mentioned_by",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MediaAttachmentSerializer(serializers.ModelSerializer):
    """Uploaded file with processing state (pending → ready/failed)."""

    best_url = serializers.ReadOnlyField()
    is_image = serializers.ReadOnlyField()
    is_video = serializers.ReadOnlyField()
    is_audio = serializers.ReadOnlyField()

    class Meta:
        model = MediaAttachment
        fields = [
            "id",
            "uploaded_by",
            "message",
            "original_filename",
            "file_key",
            "original_url",
            "compressed_url",
            "thumbnail_url",
            "webp_url",
            "best_url",
            "mimetype",
            "file_size",
            "width",
            "height",
            "duration_seconds",
            "status",
            "is_nsfw",
            "nsfw_score",
            "is_virus_scanned",
            "is_virus_free",
            "processing_error",
            "blurhash",
            "is_image",
            "is_video",
            "is_audio",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "is_nsfw",
            "nsfw_score",
            "is_virus_scanned",
            "is_virus_free",
            "processing_error",
            "best_url",
            "is_image",
            "is_video",
            "is_audio",
            "created_at",
        ]


class MessageReportSerializer(serializers.ModelSerializer):
    """User-submitted report for an abusive/spam message."""

    class Meta:
        model = MessageReport
        fields = [
            "id",
            "message",
            "reported_by",
            "reason",
            "details",
            "status",
            "reviewed_by",
            "reviewed_at",
            "moderator_note",
            "action_taken",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reported_by",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]

    def validate_reason(self, value: str) -> str:
        valid = [
            MessageReport.REASON_SPAM,
            MessageReport.REASON_ABUSE,
            MessageReport.REASON_HARASSMENT,
            MessageReport.REASON_NSFW,
            MessageReport.REASON_MISINFORM,
            MessageReport.REASON_OTHER,
        ]
        if value not in valid:
            raise serializers.ValidationError(
                _(f"Invalid reason. Valid choices: {valid}")
            )
        return value


class MessageSearchIndexSerializer(serializers.ModelSerializer):
    """DB-level full-text search index entry (Elasticsearch fallback)."""

    class Meta:
        model = MessageSearchIndex
        fields = ["id", "message", "chat", "search_text", "indexed_at"]
        read_only_fields = ["id", "indexed_at"]


class NotificationReadSerializer(serializers.ModelSerializer):
    """Tracks when a user opened or clicked a CPABroadcast."""

    class Meta:
        model = NotificationRead
        fields = ["id", "broadcast", "user", "opened_at", "clicked_at"]
        read_only_fields = ["id", "opened_at"]


class PollVoteSerializer(serializers.ModelSerializer):
    """A single vote cast by a user on a POLL-type ChatMessage."""

    class Meta:
        model = PollVote
        fields = ["id", "message", "user", "option_id", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, attrs: dict) -> dict:
        from .choices import MessageType

        msg = attrs.get("message")
        if msg and msg.message_type != MessageType.POLL:
            raise serializers.ValidationError(
                {"message": _("Can only vote on POLL type messages.")}
            )
        return attrs


class UserDeviceSerializer(serializers.ModelSerializer):
    """Detailed device record for security and multi-device management."""

    class Meta:
        model = UserDevice
        fields = [
            "id",
            "user",
            "device_id",
            "device_name",
            "platform",
            "os_version",
            "app_version",
            "ip_address",
            "location_city",
            "location_country",
            "is_trusted",
            "is_active",
            "first_login_at",
            "last_active_at",
        ]
        read_only_fields = ["id", "user", "first_login_at", "last_active_at"]

    def validate_device_id(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("device_id must not be empty."))
        return value


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Log record for every outbound webhook delivery attempt."""

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "webhook",
            "event_type",
            "payload",
            "response_status",
            "response_body",
            "attempt_count",
            "is_successful",
            "delivered_at",
            "next_retry_at",
            "error",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ── 3 Missing Model Serializers ───────────────────────────────────────────────

class AffiliateConversationThreadSerializer(serializers.ModelSerializer):
    """Direct messaging thread between an affiliate and their manager."""
    class Meta:
        model = AffiliateConversationThread
        fields = [
            "id", "affiliate", "manager", "chat",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MessageLinkPreviewSerializer(serializers.ModelSerializer):
    """Link preview record attached to a specific message position."""
    preview_detail = serializers.SerializerMethodField()

    class Meta:
        model = MessageLinkPreview
        fields = [
            "id", "message", "preview", "preview_detail",
            "position", "is_dismissed",
        ]
        read_only_fields = ["id"]

    def get_preview_detail(self, obj):
        if obj.preview:
            return {
                "url": obj.preview.url,
                "title": obj.preview.title,
                "description": obj.preview.description,
                "image_url": obj.preview.image_url,
                "domain": obj.preview.domain,
                "favicon_url": obj.preview.favicon_url,
                "is_safe": obj.preview.is_safe,
            }
        return None


class StoryHighlightSerializer(serializers.ModelSerializer):
    """Named collection of archived stories shown on a user's profile."""
    story_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
        source="stories",
    )

    class Meta:
        model = StoryHighlight
        fields = [
            "id", "user", "title", "cover_url",
            "order", "story_ids", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ===========================================================================
# Part 21 (world-system audit): Compliance Audit Trail & Retention
# ===========================================================================
from .models import AuditLogEntry, RetentionPolicy, LegalHold


class AuditLogEntrySerializer(serializers.ModelSerializer):
    """Read-only by design - nothing in this app updates or deletes an
    AuditLogEntry after creation. Only ever instantiated by
    AuditLogViewSet below, never used to accept writes."""

    class Meta:
        model = AuditLogEntry
        fields = [
            "id", "actor", "action", "target_type", "target_id",
            "metadata", "created_at",
        ]
        read_only_fields = fields


class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionPolicy
        fields = [
            "id", "chat_message_retention_days", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "updated_by", "created_at", "updated_at"]


class LegalHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalHold
        fields = [
            "id", "chat", "user", "reason", "applied_by",
            "is_active", "released_at", "released_by", "created_at",
        ]
        read_only_fields = ["id", "applied_by", "is_active", "released_at", "released_by", "created_at"]
