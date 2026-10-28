# engagement/admin/guild_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.guild import Guild, GuildMember, GuildChallenge, GuildLeaderboard, GuildInvite
from .mixins import TenantFilterMixin, UserLinkMixin, RankBadgeMixin


@admin.register(Guild)
class GuildAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["icon_display", "name", "level_badge", "member_count_display",
                     "total_xp", "is_public", "is_active"]
    list_filter   = ["is_public", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["-total_xp"]
    readonly_fields = ["total_xp", "level", "created_at", "updated_at"]

    fieldsets = (
        ("Guild",    {"fields": ("name", "slug", "description", "icon", "banner_color", "owner", "tenant")}),
        ("Settings", {"fields": ("max_members", "is_public", "min_level_required", "is_active")}),
        ("Stats",    {"fields": ("total_xp", "level")}),
        ("Meta",     {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def icon_display(self, obj):
        return format_html(
            '<span style="font-size:20px;background:{};padding:4px 8px;border-radius:8px;">{}</span>',
            obj.banner_color, obj.icon or "🏰"
        )
    icon_display.short_description = ""

    def level_badge(self, obj):
        return format_html(
            '<span style="background:#534AB7;color:#fff;padding:3px 10px;border-radius:12px;">'
            'Lv.{}</span>', obj.level
        )
    level_badge.short_description = "Level"

    def member_count_display(self, obj):
        count = obj.member_count
        color = "#4CAF50" if count < obj.max_members else "#F44336"
        return format_html(
            '<span style="color:{};">{}/{}</span>', color, count, obj.max_members
        )
    member_count_display.short_description = "Members"

    actions = ["deactivate_guilds"]

    def deactivate_guilds(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} guilds.")
    deactivate_guilds.short_description = "Deactivate selected guilds"


@admin.register(GuildMember)
class GuildMemberAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "guild_name", "role_badge", "status_badge",
                     "contribution_xp", "joined_at"]
    list_filter   = ["role", "status"]
    search_fields = ["user__username", "guild__name"]
    ordering      = ["-contribution_xp"]
    readonly_fields = ["joined_at", "last_active_at", "created_at", "updated_at"]

    def guild_name(self, obj):
        return format_html("<strong>{}</strong>", obj.guild.name)
    guild_name.short_description = "Guild"

    def role_badge(self, obj):
        colors = {"owner": "#FFD700", "admin": "#FF9800", "elder": "#9C27B0", "member": "#2196F3"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.role, "#888"), obj.role,
        )
    role_badge.short_description = "Role"

    def status_badge(self, obj):
        colors = {"active": "#4CAF50", "kicked": "#F44336", "left": "#607D8B", "pending": "#FF9800"}
        return format_html(
            '<span style="color:{};">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"


@admin.register(GuildChallenge)
class GuildChallengeAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["title", "guild_name", "metric", "progress_bar",
                     "is_completed", "starts_at", "ends_at"]
    list_filter   = ["is_completed", "metric"]
    search_fields = ["title", "guild__name"]
    readonly_fields = ["created_at", "updated_at"]

    def guild_name(self, obj):
        return obj.guild.name
    guild_name.short_description = "Guild"

    def progress_bar(self, obj):
        pct   = obj.pct
        color = "#4CAF50" if pct >= 100 else "#2196F3"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:100px;display:inline-block;">'
            '<div style="background:{};width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}/{}',
            color, pct, obj.current, obj.target,
        )
    progress_bar.short_description = "Progress"
