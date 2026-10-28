# engagement/admin/social_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.social import FeedItem, FeedLike, FeedComment, Friendship, UserFollow
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(FeedItem)
class FeedItemAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "type_badge", "title_short", "like_count",
                     "comment_count", "is_public", "created_at"]
    list_filter   = ["type", "is_public"]
    search_fields = ["user__username", "title"]
    ordering      = ["-created_at"]
    readonly_fields = ["like_count", "comment_count", "created_at", "updated_at"]

    def type_badge(self, obj):
        colors = {
            "checkin": "#4CAF50", "achievement": "#FF9800",
            "level_up": "#9C27B0", "streak_milestone": "#F44336",
            "quest_complete": "#2196F3", "challenge_win": "#FFD700",
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.type, "#888"), obj.type.replace("_", " "),
        )
    type_badge.short_description = "Type"

    def title_short(self, obj):
        return obj.title[:60] + ("…" if len(obj.title) > 60 else "")
    title_short.short_description = "Title"

    actions = ["make_private", "delete_selected"]

    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f"Made {updated} items private.")
    make_private.short_description = "Make selected items private"


@admin.register(Friendship)
class FriendshipAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["requester_name", "receiver_name", "status_badge", "accepted_at", "created_at"]
    list_filter   = ["status"]
    search_fields = ["requester__username", "receiver__username"]
    ordering      = ["-created_at"]
    readonly_fields = ["accepted_at", "created_at", "updated_at"]

    def requester_name(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">👤 {}</a>',
                           obj.requester.pk, obj.requester.username)
    requester_name.short_description = "Requester"

    def receiver_name(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">👤 {}</a>',
                           obj.receiver.pk, obj.receiver.username)
    receiver_name.short_description = "Receiver"

    def status_badge(self, obj):
        colors = {"pending": "#FF9800", "accepted": "#4CAF50", "blocked": "#F44336"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"


@admin.register(FeedComment)
class FeedCommentAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "body_short", "is_deleted", "created_at"]
    list_filter   = ["is_deleted"]
    search_fields = ["user__username", "body"]
    ordering      = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    def body_short(self, obj):
        return obj.body[:80] + ("…" if len(obj.body) > 80 else "")
    body_short.short_description = "Comment"
