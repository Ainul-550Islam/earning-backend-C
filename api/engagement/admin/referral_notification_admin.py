# engagement/admin/referral_notification_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.referral import Referral, ReferralProgram
from ..models.notification import Notification, UserPushToken
from .mixins import TenantFilterMixin, UserLinkMixin


# ── Referral Admins ───────────────────────────────────────────────────────────

@admin.register(ReferralProgram)
class ReferralProgramAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = [
        "name", "referrer_reward", "referee_reward",
        "referrer_xp", "referee_xp", "max_referrals", "is_active",
        "starts_at", "ends_at",
    ]
    list_filter   = ["is_active"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Program",  {"fields": ("name", "is_active", "tenant")}),
        ("Rewards",  {"fields": ("referrer_reward", "referee_reward", "referrer_xp", "referee_xp")}),
        ("Limits",   {"fields": ("max_referrals", "starts_at", "ends_at")}),
        ("Meta",     {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Referral)
class ReferralAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = [
        "referrer_link", "referee_link", "code",
        "status_badge", "rewarded_at", "created_at",
    ]
    list_filter   = ["status"]
    search_fields = ["referrer__username", "referee__username", "code"]
    ordering      = ["-created_at"]
    readonly_fields = ["rewarded_at", "created_at", "updated_at"]

    fieldsets = (
        ("Parties",  {"fields": ("referrer", "referee", "code", "program", "tenant")}),
        ("Status",   {"fields": ("status", "rewarded_at")}),
        ("Meta",     {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def referrer_link(self, obj):
        url = f"/admin/auth/user/{obj.referrer.pk}/change/"
        return format_html('<a href="{}">👤 {}</a>', url, obj.referrer.username)
    referrer_link.short_description = "Referrer"

    def referee_link(self, obj):
        url = f"/admin/auth/user/{obj.referee.pk}/change/"
        return format_html('<a href="{}">👤 {}</a>', url, obj.referee.username)
    referee_link.short_description = "Referee"

    def status_badge(self, obj):
        colors = {
            "pending":   "#FF9800",
            "confirmed": "#2196F3",
            "rewarded":  "#4CAF50",
            "invalid":   "#F44336",
        }
        color = colors.get(obj.status, "#888")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.status,
        )
    status_badge.short_description = "Status"


# ── Notification Admins ───────────────────────────────────────────────────────

@admin.register(Notification)
class NotificationAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = [
        "user_link", "type_badge", "title_truncated",
        "is_read_icon", "push_sent_icon", "created_at",
    ]
    list_filter   = ["type", "is_read", "push_sent"]
    search_fields = ["user__username", "title", "body"]
    ordering      = ["-created_at"]
    readonly_fields = ["read_at", "push_sent_at", "created_at", "updated_at"]

    fieldsets = (
        ("User",    {"fields": ("user", "tenant")}),
        ("Content", {"fields": ("type", "title", "body", "icon", "data")}),
        ("Status",  {"fields": ("is_read", "read_at", "push_sent", "push_sent_at")}),
        ("Meta",    {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    # Admin action: mark selected as read
    actions = ["mark_as_read"]

    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f"Marked {count} notifications as read.")
    mark_as_read.short_description = "Mark selected as read"

    def type_badge(self, obj):
        colors = {
            "level_up":         "#9C27B0",
            "achievement":      "#FF9800",
            "quest_complete":   "#4CAF50",
            "streak_at_risk":   "#F44336",
            "reward":           "#FFD700",
            "leaderboard":      "#2196F3",
        }
        color = colors.get(obj.type, "#607D8B")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.type.replace("_", " "),
        )
    type_badge.short_description = "Type"

    def title_truncated(self, obj):
        return obj.title[:50] + ("…" if len(obj.title) > 50 else "")
    title_truncated.short_description = "Title"

    def is_read_icon(self, obj):
        return format_html(
            '<span style="color:{};">{}</span>',
            "#4CAF50" if obj.is_read else "#F44336",
            "✔ Read" if obj.is_read else "Unread",
        )
    is_read_icon.short_description = "Read"

    def push_sent_icon(self, obj):
        return format_html("📲") if obj.push_sent else "—"
    push_sent_icon.short_description = "Push"


@admin.register(UserPushToken)
class UserPushTokenAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "platform_badge", "device_id", "is_active", "created_at"]
    list_filter   = ["platform", "is_active"]
    search_fields = ["user__username", "device_id"]
    readonly_fields = ["created_at", "updated_at"]

    def platform_badge(self, obj):
        colors = {"fcm": "#FF9800", "apns": "#2196F3", "web": "#4CAF50"}
        color  = colors.get(obj.platform, "#888")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            color, obj.platform.upper(),
        )
    platform_badge.short_description = "Platform"
