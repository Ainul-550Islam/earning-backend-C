"""
Messaging Admin — Django admin registration.
"""
from __future__ import annotations
import logging
from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from .models import InternalChat, ChatParticipant, ChatMessage, AdminBroadcast, SupportThread, SupportMessage, UserInbox
from . import services

logger = logging.getLogger(__name__)


class ChatParticipantInline(admin.TabularInline):
    model = ChatParticipant
    extra = 0
    readonly_fields = ["joined_at", "last_read_at"]


@admin.register(InternalChat)
class InternalChatAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "is_group", "status", "last_message_at", "created_at"]
    list_filter = ["status", "is_group"]
    search_fields = ["name", "id"]
    readonly_fields = ["id", "created_at", "updated_at", "last_message_at"]
    inlines = [ChatParticipantInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "chat", "sender", "message_type", "status", "is_edited", "created_at"]
    list_filter = ["message_type", "status"]
    search_fields = ["content", "sender__username"]
    readonly_fields = ["id", "created_at", "updated_at"]


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ["created_at", "sender"]


@admin.register(AdminBroadcast)
class AdminBroadcastAdmin(admin.ModelAdmin):
    list_display = [
        "title", "status", "audience_type", "recipient_count",
        "delivered_count", "delivery_rate_display", "scheduled_at", "sent_at",
    ]
    list_filter = ["status", "audience_type"]
    search_fields = ["title"]
    readonly_fields = ["id", "status", "recipient_count", "delivered_count", "sent_at", "error_message", "created_at", "updated_at"]
    actions = ["send_selected"]

    def delivery_rate_display(self, obj: AdminBroadcast) -> str:
        rate = obj.delivery_rate
        return f"{rate:.1f}%" if rate is not None else "—"
    delivery_rate_display.short_description = _("Delivery Rate")

    @admin.action(description=_("Send selected broadcasts"))
    def send_selected(self, request, queryset):
        for broadcast in queryset:
            try:
                services.send_broadcast(broadcast_id=broadcast.pk, actor_id=request.user.pk)
                self.message_user(request, _(f"'{broadcast.title}' sent."))
            except Exception as exc:
                self.message_user(request, _(f"Error: {exc}"), level=messages.ERROR)


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = ["subject", "user", "assigned_agent", "status", "priority", "last_reply_at", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["subject", "user__username"]
    readonly_fields = ["id", "resolved_at", "closed_at", "last_reply_at", "created_at", "updated_at"]
    inlines = [SupportMessageInline]
    raw_id_fields = ["user", "assigned_agent"]


@admin.register(UserInbox)
class UserInboxAdmin(admin.ModelAdmin):
    list_display = ["user", "item_type", "title", "is_read", "is_archived", "created_at"]
    list_filter = ["item_type", "is_read", "is_archived"]
    search_fields = ["user__username", "title"]
    readonly_fields = ["id", "read_at", "created_at", "updated_at"]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
