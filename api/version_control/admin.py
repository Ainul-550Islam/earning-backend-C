# =============================================================================
# version_control/admin.py
# =============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect


@admin.register(AppUpdatePolicy)
class AppUpdatePolicyAdmin(admin.ModelAdmin):
    list_display  = [
        "platform", "min_version", "target_version",
        "update_type_badge", "status", "is_effective_required_display",
        "created_at",
    ]
    list_filter   = ["platform", "update_type", "status"]
    search_fields = ["min_version", "target_version", "max_version"]
    raw_id_fields = ["created_by"]
    readonly_fields = [
        "id", "created_at", "updated_at", "is_effective_required_display"
    ]
    date_hierarchy = "created_at"
    ordering       = ["-created_at"]

    fieldsets = [
        (_("Identity"),  {"fields": ["id", "platform", "status", "created_by"]}),
        (_("Versions"), {
            "fields": ["min_version", "max_version", "target_version", "update_type"]
        }),
        (_("Content"), {
            "fields": ["release_notes", "release_notes_url", "force_update_after"]
        }),
        (_("Meta"),   {"fields": ["metadata", "created_at", "updated_at",
                                   "is_effective_required_display"]}),
    ]

    @admin.display(description="Update Type")
    def update_type_badge(self, obj: AppUpdatePolicy) -> str:
        color = {
            "optional": "#27ae60",
            "required": "#f39c12",
            "critical": "#e74c3c",
        }.get(obj.update_type, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.update_type.upper(),
        )

    @admin.display(description="Effectively Required?", boolean=True)
    def is_effective_required_display(self, obj: AppUpdatePolicy) -> bool:
        return obj.is_effective_required


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display  = [
        "title", "status_badge", "platforms_display",
        "scheduled_start", "scheduled_end", "duration_minutes",
    ]
    list_filter   = ["status"]
    search_fields = ["title", "description"]
    readonly_fields = [
        "id", "actual_start", "actual_end",
        "duration_minutes", "created_at", "updated_at",
    ]
    date_hierarchy = "scheduled_start"
    ordering       = ["-scheduled_start"]

    fieldsets = [
        (_("Identity"),   {"fields": ["id", "title", "description"]}),
        (_("Schedule"), {
            "fields": [
                "status", "platforms",
                "scheduled_start", "scheduled_end",
                "actual_start", "actual_end", "duration_minutes",
            ]
        }),
        (_("Settings"), {"fields": ["notify_users", "bypass_token"]}),
        (_("Timestamps"), {"fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="Status")
    def status_badge(self, obj: MaintenanceSchedule) -> str:
        color = {
            "scheduled": "#3498db",
            "active":    "#e74c3c",
            "completed": "#27ae60",
            "cancelled": "#999",
        }.get(obj.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description="Platforms")
    def platforms_display(self, obj: MaintenanceSchedule) -> str:
        if obj.affects_all_platforms:
            return "ALL"
        return ", ".join(obj.platforms)


@admin.register(PlatformRedirect)
class PlatformRedirectAdmin(admin.ModelAdmin):
    list_display  = [
        "platform", "redirect_type", "url_short", "is_active", "updated_at"
    ]
    list_filter   = ["platform", "redirect_type", "is_active"]
    search_fields = ["url", "platform"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering        = ["platform"]

    @admin.display(description="URL")
    def url_short(self, obj: PlatformRedirect) -> str:
        return obj.url[:80]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
