# =============================================================================
# behavior_analytics/admin.py
# =============================================================================
"""
Django admin registrations for behavior_analytics models.

Design:
  - list_display shows the most useful columns at a glance.
  - list_filter + search_fields enable fast lookup without full-table scans.
  - readonly_fields protects auto-generated / computed fields.
  - Raw ID widgets for FK fields (prevents N+1 in admin dropdowns).
  - Inline classes kept short (max 10 items) to avoid slow admin pages.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import ClickMetric, EngagementScore, StayTime, UserPath


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ClickMetricInline(admin.TabularInline):
    model          = ClickMetric
    extra          = 0
    max_num        = 10
    can_delete     = False
    show_change_link = True
    readonly_fields = [
        "id", "page_url", "element_selector", "element_text",
        "category", "clicked_at", "created_at",
    ]
    fields = readonly_fields


class StayTimeInline(admin.TabularInline):
    model           = StayTime
    extra           = 0
    max_num         = 10
    can_delete      = False
    show_change_link = True
    readonly_fields = [
        "id", "page_url", "duration_seconds",
        "is_active_time", "scroll_depth_percent",
    ]
    fields = readonly_fields


# ---------------------------------------------------------------------------
# UserPath
# ---------------------------------------------------------------------------

@admin.register(UserPath)
class UserPathAdmin(admin.ModelAdmin):
    list_display  = [
        "session_id_short", "user", "status",
        "device_type", "depth_display", "created_at",
    ]
    list_filter   = ["status", "device_type", "created_at"]
    search_fields = ["session_id", "user__email", "user__username", "entry_url"]
    raw_id_fields = ["user"]
    readonly_fields = [
        "id", "created_at", "updated_at", "depth_display", "is_bounce_display",
    ]
    inlines       = [ClickMetricInline, StayTimeInline]
    date_hierarchy = "created_at"
    ordering       = ["-created_at"]

    fieldsets = [
        (_("Identity"), {"fields": ["id", "user", "session_id"]}),
        (_("Session"), {
            "fields": [
                "status", "device_type", "entry_url", "exit_url",
                "ip_address", "user_agent",
            ]
        }),
        (_("Path Data"), {"fields": ["nodes", "depth_display", "is_bounce_display"]}),
        (_("Timestamps"), {"fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="Session")
    def session_id_short(self, obj: UserPath) -> str:
        return obj.session_id[:12] + "…"

    @admin.display(description="Depth")
    def depth_display(self, obj: UserPath) -> int:
        return obj.depth

    @admin.display(description="Bounce?", boolean=True)
    def is_bounce_display(self, obj: UserPath) -> bool:
        return obj.is_bounce


# ---------------------------------------------------------------------------
# ClickMetric
# ---------------------------------------------------------------------------

@admin.register(ClickMetric)
class ClickMetricAdmin(admin.ModelAdmin):
    list_display  = [
        "id_short", "path_session", "category",
        "page_url_short", "element_text_short", "clicked_at",
    ]
    list_filter   = ["category", "clicked_at"]
    search_fields = [
        "path__session_id", "page_url",
        "element_selector", "element_text",
    ]
    raw_id_fields  = ["path"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy  = "clicked_at"
    ordering        = ["-clicked_at"]

    @admin.display(description="ID")
    def id_short(self, obj: ClickMetric) -> str:
        return str(obj.pk)[:8] + "…"

    @admin.display(description="Session")
    def path_session(self, obj: ClickMetric) -> str:
        return obj.path.session_id[:12] + "…" if obj.path else "—"

    @admin.display(description="Page URL")
    def page_url_short(self, obj: ClickMetric) -> str:
        return obj.page_url[:60]

    @admin.display(description="Element Text")
    def element_text_short(self, obj: ClickMetric) -> str:
        return (obj.element_text or "")[:40]


# ---------------------------------------------------------------------------
# StayTime
# ---------------------------------------------------------------------------

@admin.register(StayTime)
class StayTimeAdmin(admin.ModelAdmin):
    list_display  = [
        "id_short", "path_session", "page_url_short",
        "duration_seconds", "is_active_time", "is_bounce_display", "created_at",
    ]
    list_filter   = ["is_active_time", "created_at"]
    search_fields = ["path__session_id", "page_url"]
    raw_id_fields  = ["path"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy  = "created_at"
    ordering        = ["-created_at"]

    @admin.display(description="ID")
    def id_short(self, obj: StayTime) -> str:
        return str(obj.pk)[:8] + "…"

    @admin.display(description="Session")
    def path_session(self, obj: StayTime) -> str:
        return obj.path.session_id[:12] + "…" if obj.path else "—"

    @admin.display(description="Page URL")
    def page_url_short(self, obj: StayTime) -> str:
        return obj.page_url[:60]

    @admin.display(description="Bounce?", boolean=True)
    def is_bounce_display(self, obj: StayTime) -> bool:
        return obj.is_bounce


# ---------------------------------------------------------------------------
# EngagementScore
# ---------------------------------------------------------------------------

@admin.register(EngagementScore)
class EngagementScoreAdmin(admin.ModelAdmin):
    list_display  = [
        "user", "date", "score_badge", "tier",
        "click_count", "total_stay_sec", "path_depth", "return_visits",
    ]
    list_filter   = ["tier", "date"]
    search_fields = ["user__email", "user__username"]
    raw_id_fields  = ["user"]
    readonly_fields = [
        "id", "created_at", "updated_at",
        "breakdown_json", "tier",
    ]
    date_hierarchy = "date"
    ordering       = ["-date", "-score"]

    @admin.display(description="Score")
    def score_badge(self, obj: EngagementScore) -> str:
        color = {
            "low":    "#e74c3c",
            "medium": "#f39c12",
            "high":   "#27ae60",
            "elite":  "#2980b9",
        }.get(obj.tier, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>', color, obj.score
        )


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
