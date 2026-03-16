"""
Gamification Admin — Django admin registration with list filters and actions.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .exceptions import GamificationServiceError, ContestCycleStateError
from .models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
from . import services

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ContestCycle Admin
# ---------------------------------------------------------------------------

@admin.register(ContestCycle)
class ContestCycleAdmin(admin.ModelAdmin):
    list_display = [
        "name", "slug", "status_badge", "start_date", "end_date",
        "points_multiplier", "is_featured", "duration_days", "created_at",
    ]
    list_filter = ["status", "is_featured", "start_date"]
    search_fields = ["name", "slug"]
    readonly_fields = ["id", "created_at", "updated_at", "is_active", "is_expired", "duration_days"]
    ordering = ["-created_at"]
    actions = ["activate_selected", "complete_selected"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "name", "slug", "description")}),
        (_("Schedule"), {"fields": ("start_date", "end_date", "duration_days")}),
        (_("Configuration"), {"fields": ("status", "points_multiplier", "is_featured", "max_participants", "metadata")}),
        (_("State"), {"fields": ("is_active", "is_expired")}),
        (_("Audit"), {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def status_badge(self, obj: ContestCycle) -> str:
        colours = {
            "DRAFT": "#6c757d",
            "ACTIVE": "#28a745",
            "COMPLETED": "#007bff",
            "ARCHIVED": "#343a40",
        }
        colour = colours.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            colour,
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    @admin.action(description=_("Activate selected contest cycles"))
    def activate_selected(self, request: HttpRequest, queryset: Any) -> None:
        activated = 0
        for cycle in queryset:
            try:
                services.activate_contest_cycle(cycle_id=cycle.pk, actor_id=request.user.pk)
                activated += 1
            except (ContestCycleStateError, GamificationServiceError) as exc:
                self.message_user(
                    request,
                    _(f"Could not activate '{cycle.name}': {exc}"),
                    level=messages.WARNING,
                )
        if activated:
            self.message_user(request, _(f"{activated} cycle(s) activated."))

    @admin.action(description=_("Complete selected contest cycles"))
    def complete_selected(self, request: HttpRequest, queryset: Any) -> None:
        completed = 0
        for cycle in queryset:
            try:
                services.complete_contest_cycle(cycle_id=cycle.pk, actor_id=request.user.pk)
                completed += 1
            except (ContestCycleStateError, GamificationServiceError) as exc:
                self.message_user(
                    request,
                    _(f"Could not complete '{cycle.name}': {exc}"),
                    level=messages.WARNING,
                )
        if completed:
            self.message_user(request, _(f"{completed} cycle(s) completed."))


# ---------------------------------------------------------------------------
# LeaderboardSnapshot Admin
# ---------------------------------------------------------------------------

@admin.register(LeaderboardSnapshot)
class LeaderboardSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "id", "contest_cycle", "scope", "scope_ref", "status",
        "entry_count_display", "generated_at", "created_at",
    ]
    list_filter = ["status", "scope", "created_at"]
    search_fields = ["contest_cycle__name", "scope_ref"]
    readonly_fields = ["id", "checksum", "entry_count_display", "generated_at", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def entry_count_display(self, obj: LeaderboardSnapshot) -> int:
        return obj.entry_count
    entry_count_display.short_description = _("Entries")


# ---------------------------------------------------------------------------
# ContestReward Admin
# ---------------------------------------------------------------------------

@admin.register(ContestReward)
class ContestRewardAdmin(admin.ModelAdmin):
    list_display = [
        "title", "contest_cycle", "reward_type", "rank_from", "rank_to",
        "reward_value", "total_budget", "issued_count", "is_active", "is_exhausted",
    ]
    list_filter = ["reward_type", "is_active", "contest_cycle"]
    search_fields = ["title", "contest_cycle__name"]
    readonly_fields = ["id", "issued_count", "is_exhausted", "remaining_budget", "created_at", "updated_at"]
    ordering = ["rank_from"]

    def is_exhausted(self, obj: ContestReward) -> bool:
        return obj.is_exhausted
    is_exhausted.boolean = True
    is_exhausted.short_description = _("Exhausted?")

    def remaining_budget(self, obj: ContestReward) -> str:
        rb = obj.remaining_budget
        return str(rb) if rb is not None else _("Unlimited")
    remaining_budget.short_description = _("Remaining Budget")


# ---------------------------------------------------------------------------
# UserAchievement Admin
# ---------------------------------------------------------------------------

@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = [
        "user", "title", "achievement_type", "points_awarded",
        "rank_at_award", "is_awarded", "is_notified", "awarded_at",
    ]
    list_filter = ["is_awarded", "is_notified", "achievement_type", "contest_cycle"]
    search_fields = ["user__username", "user__email", "title"]
    readonly_fields = [
        "id", "is_awarded", "awarded_at", "is_notified", "notified_at",
        "created_at", "updated_at",
    ]
    ordering = ["-awarded_at"]
    raw_id_fields = ["user"]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
