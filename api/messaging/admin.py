"""
Messaging Django Admin — Full admin for all 31+ models.
World-class admin with search, filters, list display, and custom actions.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.utils import timezone

from .models import (
    InternalChat, ChatParticipant, ChatMessage, AdminBroadcast,
    SupportThread, SupportMessage, UserInbox,
    MessageReaction, UserPresence, CallSession,
    AnnouncementChannel, ChannelMember, ScheduledMessage,
    MessagePin, PollVote, BotConfig, BotResponse,
    MessagingWebhook, WebhookDelivery, MessageTranslation,
    UserBlock, DeviceToken,
    MessageEditHistory, DisappearingMessageConfig,
    UserStory, StoryView, StoryHighlight,
    VoiceMessageTranscription, LinkPreview, MessageLinkPreview,
    MediaAttachment, MessageReport, UserDevice,
    ChatMention, MessageSearchIndex,
)


# ── Base Admin ────────────────────────────────────────────────────────────────

class ReadOnlyMixin:
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser


# ── InternalChat ──────────────────────────────────────────────────────────────

class ChatParticipantInline(admin.TabularInline):
    model = ChatParticipant
    extra = 0
    readonly_fields = ("user", "role", "joined_at", "last_read_at", "is_muted")
    can_delete = False
    show_change_link = False
    fields = ("user", "role", "is_muted", "joined_at", "last_read_at")


@admin.register(InternalChat)
class InternalChatAdmin(admin.ModelAdmin):
    list_display  = ("id_short", "name_or_direct", "is_group", "status", "participant_count",
                     "is_encrypted", "last_message_at", "created_at")
    list_filter   = ("status", "is_group", "is_encrypted")
    search_fields = ("id", "name", "created_by__username", "created_by__email")
    readonly_fields = ("id", "created_at", "updated_at", "last_message_at")
    raw_id_fields = ("created_by", "tenant")
    inlines       = [ChatParticipantInline]
    ordering      = ("-last_message_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "name", "is_group", "status", "created_by")}),
        ("Settings", {"fields": ("is_encrypted", "max_participants", "description", "avatar",
                                  "notification_preference")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_message_at")}),
        ("Tenant", {"fields": ("tenant", "metadata")}),
    )

    def id_short(self, obj): return str(obj.id)[:8]
    id_short.short_description = "ID"

    def name_or_direct(self, obj): return obj.name or "(Direct)"
    name_or_direct.short_description = "Name"

    def participant_count(self, obj):
        return obj.participants.filter(left_at__isnull=True).count()
    participant_count.short_description = "Participants"

    actions = ["archive_chats", "delete_chats"]

    def archive_chats(self, request, qs):
        from .choices import ChatStatus
        qs.filter(status=ChatStatus.ACTIVE).update(status=ChatStatus.ARCHIVED)
        self.message_user(request, f"Archived {qs.count()} chats.")
    archive_chats.short_description = "Archive selected chats"

    def delete_chats(self, request, qs):
        from .choices import ChatStatus
        qs.update(status=ChatStatus.DELETED)
        self.message_user(request, f"Soft-deleted {qs.count()} chats.")
    delete_chats.short_description = "Soft-delete selected chats"


# ── ChatMessage ───────────────────────────────────────────────────────────────

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ("id_short", "chat_link", "sender_link", "message_type",
                     "status", "content_preview", "is_edited", "created_at")
    list_filter   = ("message_type", "status", "is_edited", "is_forwarded", "priority")
    search_fields = ("id", "content", "sender__username", "sender__email", "chat__id")
    readonly_fields = ("id", "created_at", "updated_at", "edited_at", "deleted_at",
                       "thread_reply_count", "delivery_receipts", "read_receipts")
    raw_id_fields  = ("chat", "sender", "reply_to", "forwarded_from", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "chat", "sender", "message_type", "status", "priority")}),
        ("Content", {"fields": ("content", "attachments", "mentions",
                                 "poll_data", "location_data", "call_log_data")}),
        ("Threading", {"fields": ("reply_to", "thread_id", "thread_reply_count",
                                   "is_forwarded", "forwarded_from")}),
        ("Edit / Delete", {"fields": ("is_edited", "edited_at", "deleted_at")}),
        ("Receipts", {"fields": ("delivery_receipts", "read_receipts")}),
        ("Encryption", {"fields": ("encrypted_content", "encryption_key_id")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def id_short(self, obj): return str(obj.id)[:8]
    id_short.short_description = "ID"

    def content_preview(self, obj):
        return (obj.content[:60] + "…") if len(obj.content) > 60 else obj.content
    content_preview.short_description = "Content"

    def chat_link(self, obj):
        url = reverse("admin:messaging_internalchat_change", args=[obj.chat_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.chat_id)[:8])
    chat_link.short_description = "Chat"

    def sender_link(self, obj):
        if not obj.sender_id:
            return "—"
        return format_html("<b>{}</b>", obj.sender.username if obj.sender else obj.sender_id)
    sender_link.short_description = "Sender"

    actions = ["soft_delete_messages"]

    def soft_delete_messages(self, request, qs):
        for msg in qs:
            msg.soft_delete(deleted_by_id=request.user.pk)
        self.message_user(request, f"Soft-deleted {qs.count()} messages.")
    soft_delete_messages.short_description = "Soft-delete selected messages"


# ── AdminBroadcast ────────────────────────────────────────────────────────────

@admin.register(AdminBroadcast)
class AdminBroadcastAdmin(admin.ModelAdmin):
    list_display  = ("title", "status", "audience_type", "recipient_count",
                     "delivered_count", "delivery_rate", "scheduled_at", "sent_at", "created_by")
    list_filter   = ("status", "audience_type")
    search_fields = ("title", "body", "created_by__username")
    readonly_fields = ("id", "created_at", "updated_at", "sent_at",
                       "recipient_count", "delivered_count", "delivery_rate")
    raw_id_fields  = ("created_by", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"

    def delivery_rate(self, obj):
        rate = obj.delivery_rate
        return f"{rate:.1f}%" if rate is not None else "—"
    delivery_rate.short_description = "Delivery Rate"

    actions = ["send_now"]

    def send_now(self, request, qs):
        from .tasks import send_broadcast_async
        for b in qs:
            send_broadcast_async.delay(str(b.id), actor_id=request.user.pk)
        self.message_user(request, f"Queued {qs.count()} broadcasts.")
    send_now.short_description = "Send selected broadcasts now"


# ── SupportThread ─────────────────────────────────────────────────────────────

class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("sender", "content", "is_agent_reply", "is_internal_note", "created_at")
    fields = ("sender", "content", "is_agent_reply", "is_internal_note", "created_at")
    can_delete = False
    ordering   = ("created_at",)


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display  = ("subject_short", "user", "status", "priority", "assigned_agent",
                     "last_reply_at", "created_at")
    list_filter   = ("status", "priority")
    search_fields = ("subject", "user__username", "user__email", "assigned_agent__username")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at", "closed_at", "last_reply_at")
    raw_id_fields  = ("user", "assigned_agent", "tenant")
    inlines        = [SupportMessageInline]
    ordering       = ("-last_reply_at",)

    def subject_short(self, obj):
        return obj.subject[:60]
    subject_short.short_description = "Subject"

    actions = ["close_threads", "assign_to_me"]

    def close_threads(self, request, qs):
        from .choices import SupportThreadStatus
        for t in qs:
            try:
                t.transition_to(SupportThreadStatus.CLOSED, agent=request.user)
            except Exception:
                pass
        self.message_user(request, f"Closed {qs.count()} threads.")
    close_threads.short_description = "Close selected threads"

    def assign_to_me(self, request, qs):
        qs.update(assigned_agent=request.user)
        self.message_user(request, f"Assigned {qs.count()} threads to you.")
    assign_to_me.short_description = "Assign to me"


# ── UserInbox ─────────────────────────────────────────────────────────────────

@admin.register(UserInbox)
class UserInboxAdmin(admin.ModelAdmin):
    list_display  = ("user", "item_type", "title_short", "is_read", "is_archived", "created_at")
    list_filter   = ("item_type", "is_read", "is_archived")
    search_fields = ("user__username", "title", "preview")
    readonly_fields = ("id", "created_at", "updated_at", "read_at")
    raw_id_fields  = ("user", "tenant")
    ordering       = ("-created_at",)

    def title_short(self, obj): return obj.title[:50]
    title_short.short_description = "Title"


# ── MessageReaction ───────────────────────────────────────────────────────────

@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display  = ("message_id_short", "user", "emoji", "custom_emoji", "created_at")
    list_filter   = ("emoji",)
    search_fields = ("user__username", "message__id")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields  = ("message", "user", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"


# ── UserPresence ──────────────────────────────────────────────────────────────

@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display  = ("user", "status", "effective_status", "last_seen_at",
                     "last_seen_on", "is_invisible", "custom_status")
    list_filter   = ("status", "is_invisible", "last_seen_on")
    search_fields = ("user__username", "user__email", "custom_status")
    readonly_fields = ("id", "created_at", "updated_at", "effective_status")
    raw_id_fields  = ("user", "tenant")
    ordering       = ("-last_seen_at",)


# ── CallSession ───────────────────────────────────────────────────────────────

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display  = ("room_id", "call_type", "status", "initiated_by",
                     "duration_seconds", "is_recorded", "created_at")
    list_filter   = ("call_type", "status", "is_recorded")
    search_fields = ("room_id", "initiated_by__username")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "ended_at", "duration_seconds")
    raw_id_fields  = ("chat", "initiated_by", "tenant")
    filter_horizontal = ("participants",)
    ordering       = ("-created_at",)


# ── AnnouncementChannel ───────────────────────────────────────────────────────

@admin.register(AnnouncementChannel)
class AnnouncementChannelAdmin(admin.ModelAdmin):
    list_display  = ("name", "slug", "channel_type", "subscriber_count",
                     "post_count", "is_verified", "created_by", "created_at")
    list_filter   = ("channel_type", "is_verified")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("id", "created_at", "updated_at", "subscriber_count", "post_count")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields  = ("created_by", "tenant")

    actions = ["verify_channels"]

    def verify_channels(self, request, qs):
        qs.update(is_verified=True)
        self.message_user(request, f"Verified {qs.count()} channels.")
    verify_channels.short_description = "Mark as verified"


# ── ScheduledMessage ──────────────────────────────────────────────────────────

@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display  = ("sender", "chat_id_short", "content_preview", "scheduled_for",
                     "status", "created_at")
    list_filter   = ("status", "message_type")
    search_fields = ("sender__username", "content")
    readonly_fields = ("id", "created_at", "updated_at", "sent_message", "error")
    raw_id_fields  = ("chat", "sender", "sent_message", "tenant")
    ordering       = ("scheduled_for",)

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"

    def content_preview(self, obj): return obj.content[:60]
    content_preview.short_description = "Content"


# ── MessagePin ────────────────────────────────────────────────────────────────

@admin.register(MessagePin)
class MessagePinAdmin(admin.ModelAdmin):
    list_display  = ("chat_id_short", "message_id_short", "pinned_by", "pinned_at")
    search_fields = ("chat__id", "message__id")
    readonly_fields = ("id", "created_at", "updated_at", "pinned_at")
    raw_id_fields  = ("chat", "message", "pinned_by", "tenant")

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"


# ── BotConfig ─────────────────────────────────────────────────────────────────

@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display  = ("name", "trigger_type", "trigger_value_short", "is_active",
                     "priority", "delay_seconds", "created_by", "created_at")
    list_filter   = ("trigger_type", "is_active")
    search_fields = ("name", "trigger_value", "response_template")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields  = ("chat", "created_by", "tenant")
    ordering       = ("-priority",)

    def trigger_value_short(self, obj): return obj.trigger_value[:40]
    trigger_value_short.short_description = "Trigger"

    actions = ["activate_bots", "deactivate_bots"]

    def activate_bots(self, request, qs):
        qs.update(is_active=True)
        self.message_user(request, f"Activated {qs.count()} bots.")
    activate_bots.short_description = "Activate selected bots"

    def deactivate_bots(self, request, qs):
        qs.update(is_active=False)
        self.message_user(request, f"Deactivated {qs.count()} bots.")
    deactivate_bots.short_description = "Deactivate selected bots"


# ── MessagingWebhook ──────────────────────────────────────────────────────────

@admin.register(MessagingWebhook)
class MessagingWebhookAdmin(admin.ModelAdmin):
    list_display  = ("name", "url_short", "is_active", "events_count",
                     "failure_count", "last_triggered_at", "created_at")
    list_filter   = ("is_active",)
    search_fields = ("name", "url")
    readonly_fields = ("id", "created_at", "updated_at", "failure_count", "last_triggered_at")
    raw_id_fields  = ("created_by", "tenant")

    def url_short(self, obj): return obj.url[:60]
    url_short.short_description = "URL"

    def events_count(self, obj): return len(obj.events)
    events_count.short_description = "Events"

    actions = ["reset_failure_count", "deactivate_webhooks"]

    def reset_failure_count(self, request, qs):
        qs.update(failure_count=0)
        self.message_user(request, "Reset failure counts.")
    reset_failure_count.short_description = "Reset failure counts"

    def deactivate_webhooks(self, request, qs):
        qs.update(is_active=False)
        self.message_user(request, f"Deactivated {qs.count()} webhooks.")
    deactivate_webhooks.short_description = "Deactivate"


# ── MediaAttachment ───────────────────────────────────────────────────────────

@admin.register(MediaAttachment)
class MediaAttachmentAdmin(admin.ModelAdmin):
    list_display  = ("original_filename_short", "uploaded_by", "mimetype",
                     "file_size_display", "status", "is_nsfw", "is_virus_free", "created_at")
    list_filter   = ("status", "is_nsfw", "is_virus_scanned")
    search_fields = ("original_filename", "uploaded_by__username", "file_key")
    readonly_fields = ("id", "created_at", "updated_at", "original_url", "compressed_url",
                       "thumbnail_url", "webp_url", "is_nsfw", "nsfw_score",
                       "is_virus_scanned", "is_virus_free", "processing_error")
    raw_id_fields  = ("uploaded_by", "message", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"

    def original_filename_short(self, obj): return obj.original_filename[:50]
    original_filename_short.short_description = "Filename"

    def file_size_display(self, obj):
        if obj.file_size > 1_000_000:
            return f"{obj.file_size / 1_000_000:.1f} MB"
        elif obj.file_size > 1_000:
            return f"{obj.file_size / 1_000:.1f} KB"
        return f"{obj.file_size} B"
    file_size_display.short_description = "Size"

    actions = ["reprocess_media", "block_nsfw"]

    def reprocess_media(self, request, qs):
        from .tasks import process_image_task, process_video_task
        for m in qs:
            if m.is_image:
                process_image_task.delay(str(m.id))
            elif m.is_video:
                process_video_task.delay(str(m.id))
        self.message_user(request, f"Queued {qs.count()} for reprocessing.")
    reprocess_media.short_description = "Reprocess selected media"

    def block_nsfw(self, request, qs):
        qs.update(status=MediaAttachment.STATUS_BLOCKED, is_nsfw=True)
        self.message_user(request, f"Blocked {qs.count()} media items.")
    block_nsfw.short_description = "Block as NSFW"


# ── MessageReport ─────────────────────────────────────────────────────────────

@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display  = ("reason", "status", "reported_by", "message_id_short",
                     "reviewed_by", "reviewed_at", "created_at")
    list_filter   = ("reason", "status")
    search_fields = ("reported_by__username", "details", "action_taken")
    readonly_fields = ("id", "created_at", "updated_at", "message", "reported_by")
    raw_id_fields  = ("reviewed_by", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"

    actions = ["mark_reviewed", "mark_dismissed", "delete_reported_message"]

    def mark_reviewed(self, request, qs):
        qs.update(status=MessageReport.STATUS_REVIEWED, reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"Marked {qs.count()} reports as under review.")
    mark_reviewed.short_description = "Mark as under review"

    def mark_dismissed(self, request, qs):
        qs.update(status=MessageReport.STATUS_DISMISSED, reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"Dismissed {qs.count()} reports.")
    mark_dismissed.short_description = "Dismiss reports"

    def delete_reported_message(self, request, qs):
        for report in qs:
            report.message.soft_delete(deleted_by_id=request.user.pk)
            report.status = MessageReport.STATUS_RESOLVED
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.action_taken = "message deleted by admin"
            report.save()
        self.message_user(request, f"Deleted messages for {qs.count()} reports.")
    delete_reported_message.short_description = "Delete reported messages"


# ── UserDevice ────────────────────────────────────────────────────────────────

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display  = ("user", "device_name", "platform", "is_trusted",
                     "is_active", "ip_address", "location_country", "last_active_at")
    list_filter   = ("platform", "is_trusted", "is_active")
    search_fields = ("user__username", "device_name", "device_id", "ip_address")
    readonly_fields = ("id", "created_at", "updated_at", "first_login_at")
    raw_id_fields  = ("user", "tenant")
    ordering       = ("-last_active_at",)

    actions = ["revoke_devices", "trust_devices"]

    def revoke_devices(self, request, qs):
        qs.update(is_active=False)
        self.message_user(request, f"Revoked {qs.count()} devices.")
    revoke_devices.short_description = "Revoke (logout) selected devices"

    def trust_devices(self, request, qs):
        qs.update(is_trusted=True)
        self.message_user(request, f"Trusted {qs.count()} devices.")
    trust_devices.short_description = "Mark as trusted"


# ── DeviceToken ───────────────────────────────────────────────────────────────

@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display  = ("user", "platform", "device_name", "is_active", "last_used_at", "created_at")
    list_filter   = ("platform", "is_active")
    search_fields = ("user__username", "device_name", "token")
    readonly_fields = ("id", "created_at", "updated_at", "last_used_at")
    raw_id_fields  = ("user", "tenant")


# ── UserBlock ─────────────────────────────────────────────────────────────────

@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display  = ("blocker", "blocked", "reason_short", "created_at")
    search_fields = ("blocker__username", "blocked__username", "reason")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields  = ("blocker", "blocked", "tenant")
    ordering       = ("-created_at",)

    def reason_short(self, obj): return obj.reason[:50]
    reason_short.short_description = "Reason"


# ── UserStory ─────────────────────────────────────────────────────────────────

@admin.register(UserStory)
class UserStoryAdmin(admin.ModelAdmin):
    list_display  = ("user", "story_type", "content_preview", "view_count",
                     "is_active", "visibility", "expires_at", "created_at")
    list_filter   = ("story_type", "is_active", "visibility")
    search_fields = ("user__username", "content", "location")
    readonly_fields = ("id", "created_at", "updated_at", "view_count", "is_expired")
    raw_id_fields  = ("user", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"

    def content_preview(self, obj): return (obj.content[:50] + "…") if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content"

    actions = ["expire_stories", "deactivate_stories"]

    def expire_stories(self, request, qs):
        from django.utils import timezone
        qs.update(expires_at=timezone.now(), is_active=False)
        self.message_user(request, f"Expired {qs.count()} stories.")
    expire_stories.short_description = "Expire selected stories now"

    def deactivate_stories(self, request, qs):
        qs.update(is_active=False)
        self.message_user(request, f"Deactivated {qs.count()} stories.")
    deactivate_stories.short_description = "Deactivate"


# ── LinkPreview ───────────────────────────────────────────────────────────────

@admin.register(LinkPreview)
class LinkPreviewAdmin(admin.ModelAdmin):
    list_display  = ("domain", "title_short", "is_safe", "content_type", "fetched_at")
    list_filter   = ("is_safe", "content_type")
    search_fields = ("url", "domain", "title")
    readonly_fields = ("id", "created_at", "updated_at", "fetched_at")
    ordering       = ("-fetched_at",)

    def title_short(self, obj): return obj.title[:60]
    title_short.short_description = "Title"

    actions = ["mark_unsafe", "refetch"]

    def mark_unsafe(self, request, qs):
        qs.update(is_safe=False)
        self.message_user(request, f"Marked {qs.count()} as unsafe.")
    mark_unsafe.short_description = "Mark as unsafe"

    def refetch(self, request, qs):
        from .utils.link_preview import fetch_link_preview
        for lp in qs:
            data = fetch_link_preview(lp.url)
            lp.title = data.get("title", "")[:500]
            lp.description = data.get("description", "")
            lp.image_url = data.get("image_url")
            lp.is_safe = data.get("is_safe", True)
            lp.save()
        self.message_user(request, f"Refetched {qs.count()} previews.")
    refetch.short_description = "Refetch metadata"


# ── WebhookDelivery (read-only log) ──────────────────────────────────────────

@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("webhook", "event_type", "is_successful", "response_status",
                     "attempt_count", "created_at")
    list_filter   = ("is_successful", "event_type")
    search_fields = ("webhook__name", "event_type")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields  = ("webhook", "tenant")
    ordering       = ("-created_at",)
    date_hierarchy = "created_at"


# ── VoiceMessageTranscription ─────────────────────────────────────────────────

@admin.register(VoiceMessageTranscription)
class VoiceTranscriptionAdmin(admin.ModelAdmin):
    list_display  = ("message_id_short", "language", "confidence_pct",
                     "duration_display", "provider", "is_processing", "created_at")
    list_filter   = ("provider", "is_processing", "language")
    search_fields = ("transcribed_text",)
    readonly_fields = ("id", "created_at", "updated_at", "waveform_data")
    raw_id_fields  = ("message", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"

    def confidence_pct(self, obj): return f"{obj.confidence * 100:.0f}%"
    confidence_pct.short_description = "Confidence"

    def duration_display(self, obj): return f"{obj.duration_seconds:.1f}s"
    duration_display.short_description = "Duration"

    actions = ["retranscribe"]

    def retranscribe(self, request, qs):
        from .tasks import process_voice_message_task
        for t in qs:
            process_voice_message_task.delay(str(t.message_id))
        self.message_user(request, f"Queued {qs.count()} for retranscription.")
    retranscribe.short_description = "Retranscribe selected"


# ── DisappearingMessageConfig ─────────────────────────────────────────────────

@admin.register(DisappearingMessageConfig)
class DisappearingConfigAdmin(admin.ModelAdmin):
    list_display  = ("chat_id_short", "is_enabled", "ttl_display", "enabled_by", "enabled_at")
    list_filter   = ("is_enabled",)
    readonly_fields = ("id", "created_at", "updated_at", "enabled_at", "ttl_display")
    raw_id_fields  = ("chat", "enabled_by", "tenant")

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"


# ── Simple registrations (less complex models) ────────────────────────────────

@admin.register(ChatParticipant)
class ChatParticipantAdmin(admin.ModelAdmin):
    list_display  = ("user", "chat_id_short", "role", "is_muted",
                     "is_pinned", "joined_at", "left_at")
    list_filter   = ("role", "is_muted", "is_pinned")
    search_fields = ("user__username", "chat__id")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields  = ("chat", "user", "tenant")

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"


@admin.register(SupportMessage)
class SupportMessageAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("thread_id_short", "sender", "is_agent_reply", "is_internal_note",
                     "content_preview", "created_at")
    list_filter   = ("is_agent_reply", "is_internal_note")
    search_fields = ("sender__username", "content")
    raw_id_fields  = ("thread", "sender", "tenant")

    def thread_id_short(self, obj): return str(obj.thread_id)[:8]
    thread_id_short.short_description = "Thread"

    def content_preview(self, obj): return obj.content[:60]
    content_preview.short_description = "Content"


@admin.register(MessageEditHistory)
class MessageEditHistoryAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("message_id_short", "edited_by", "edit_number", "edit_reason_short", "created_at")
    search_fields = ("message__id", "edited_by__username")
    raw_id_fields  = ("message", "edited_by", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"

    def edit_reason_short(self, obj): return obj.edit_reason[:40]
    edit_reason_short.short_description = "Reason"


@admin.register(PollVote)
class PollVoteAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("message_id_short", "user", "option_id", "created_at")
    search_fields = ("user__username", "message__id")
    raw_id_fields  = ("message", "user", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Poll Message"


@admin.register(ChatMention)
class ChatMentionAdmin(admin.ModelAdmin):
    list_display  = ("mentioned_user", "mentioned_by", "chat_id_short", "is_read", "created_at")
    list_filter   = ("is_read",)
    search_fields = ("mentioned_user__username", "mentioned_by__username")
    raw_id_fields  = ("message", "chat", "mentioned_user", "mentioned_by", "tenant")

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"


@admin.register(ChannelMember)
class ChannelMemberAdmin(admin.ModelAdmin):
    list_display  = ("user", "channel", "is_admin", "joined_at")
    list_filter   = ("is_admin",)
    search_fields = ("user__username", "channel__name")
    raw_id_fields  = ("channel", "user", "tenant")


@admin.register(BotResponse)
class BotResponseAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("bot", "was_successful", "trigger_message_short", "created_at")
    list_filter   = ("was_successful",)
    raw_id_fields  = ("bot", "trigger_message", "sent_message", "tenant")

    def trigger_message_short(self, obj): return str(obj.trigger_message_id)[:8] if obj.trigger_message_id else "—"
    trigger_message_short.short_description = "Trigger Msg"


@admin.register(MessageTranslation)
class MessageTranslationAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("message_id_short", "target_language", "source_language", "provider", "created_at")
    list_filter   = ("target_language", "provider")
    raw_id_fields  = ("message", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"


@admin.register(StoryView)
class StoryViewAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("story_id_short", "viewer", "reaction_emoji", "reply_short", "viewed_at")
    search_fields = ("viewer__username",)
    raw_id_fields  = ("story", "viewer", "tenant")

    def story_id_short(self, obj): return str(obj.story_id)[:8]
    story_id_short.short_description = "Story"

    def reply_short(self, obj): return obj.reply_text[:40]
    reply_short.short_description = "Reply"


@admin.register(StoryHighlight)
class StoryHighlightAdmin(admin.ModelAdmin):
    list_display  = ("title", "user", "order", "created_at")
    search_fields = ("title", "user__username")
    raw_id_fields  = ("user", "tenant")
    filter_horizontal = ("stories",)


@admin.register(MessageLinkPreview)
class MessageLinkPreviewAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("message_id_short", "preview_domain", "position", "is_dismissed")
    search_fields = ("message__id", "preview__domain")
    raw_id_fields  = ("message", "preview", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"

    def preview_domain(self, obj): return obj.preview.domain
    preview_domain.short_description = "Domain"


@admin.register(MessageSearchIndex)
class MessageSearchIndexAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display  = ("message_id_short", "chat_id_short", "search_text_preview", "indexed_at")
    search_fields = ("search_text",)
    raw_id_fields  = ("message", "chat", "tenant")

    def message_id_short(self, obj): return str(obj.message_id)[:8]
    message_id_short.short_description = "Message"

    def chat_id_short(self, obj): return str(obj.chat_id)[:8]
    chat_id_short.short_description = "Chat"

    def search_text_preview(self, obj): return obj.search_text[:60]
    search_text_preview.short_description = "Search Text"
