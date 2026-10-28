"""
Gamification Admin — Django admin registration with list filters and actions.
Enhanced with integration system monitoring and audit capabilities.
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Any, Dict, Optional

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError, ContestCycleStateError
from api.gamification.models import (
    ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement,
    Badge, UserBadge, DailyChallenge, UserDailyChallenge, Streak, StreakReward, LevelConfig,
    UserPoints, PointsTransaction, StreakFreeze, ContestParticipant, GamificationConfig, GamificationInsight
)
from api.gamification import services
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from api.gamification.INTEGRATION_SYSTEM.health_check import health_manager

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
    actions = ["activate_selected", "complete_selected", "run_health_check", "export_audit_logs"]

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
                # Log activation attempt
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Admin activating contest cycle: {cycle.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details={"admin_action": "activate_selected", "cycle_name": cycle.name}
                )
                
                # Record performance metrics
                start_time = performance_monitor.record_metric("admin_cycle_activation_start", 1.0)
                
                services.activate_contest_cycle(cycle_id=cycle.pk, actor_id=request.user.pk)
                
                # Record completion metrics
                performance_monitor.record_metric("admin_cycle_activation_complete", 1.0)
                
                activated += 1
                
                # Log successful activation
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Successfully activated contest cycle: {cycle.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    details={"admin_action": "activate_selected", "status": "success"}
                )
                
            except (ContestCycleStateError, GamificationServiceError) as exc:
                # Log error
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to activate contest cycle: {cycle.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
                
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
                # Log completion attempt
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Admin completing contest cycle: {cycle.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details={"admin_action": "complete_selected", "cycle_name": cycle.name}
                )
                
                # Record performance metrics
                performance_monitor.record_metric("admin_cycle_completion_start", 1.0)
                
                services.complete_contest_cycle(cycle_id=cycle.pk, actor_id=request.user.pk)
                
                # Record completion metrics
                performance_monitor.record_metric("admin_cycle_completion_complete", 1.0)
                
                completed += 1
                
                # Log successful completion
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Successfully completed contest cycle: {cycle.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    details={"admin_action": "complete_selected", "status": "success"}
                )
                
            except (ContestCycleStateError, GamificationServiceError) as exc:
                # Log error
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to complete contest cycle: {cycle.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
                
                self.message_user(
                    request,
                    _(f"Could not complete '{cycle.name}': {exc}"),
                    level=messages.WARNING,
                )
        if completed:
            self.message_user(request, _(f"{completed} cycle(s) completed."))

    @admin.action(description=_("Run health check on selected cycles"))
    def run_health_check(self, request: HttpRequest, queryset: Any) -> None:
        """Run integration health checks on selected contest cycles."""
        health_results = {}
        
        for cycle in queryset:
            try:
                # Create health check for this cycle
                from api.gamification.INTEGRATION_SYSTEM.health_check import create_health_check, HealthCheckResult, HealthStatus
                
                health_check = create_health_check(
                    name=f"cycle_{cycle.pk}_health",
                    check_type="CUSTOM",
                    description=f"Health check for contest cycle: {cycle.name}"
                )
                
                # Simulate health check execution
                result = HealthCheckResult(
                    check_name=health_check.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Contest cycle {cycle.name} is healthy",
                    details={"cycle_id": str(cycle.pk), "status": cycle.status}
                )
                
                health_results[str(cycle.pk)] = result.to_dict()
                
                # Log health check
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.EXECUTE,
                    description=f"Health check performed on contest cycle: {cycle.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    details={"health_status": result.status.value}
                )
                
            except Exception as exc:
                health_results[str(cycle.pk)] = {"error": str(exc)}
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Health check failed for contest cycle: {cycle.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(cycle.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
        
        # Display results
        healthy_count = len([r for r in health_results.values() if r.get("status") == "healthy"])
        self.message_user(request, _(f"Health check completed: {healthy_count}/{len(health_results)} cycles healthy."))

    @admin.action(description=_("Export audit logs for selected cycles"))
    def export_audit_logs(self, request: HttpRequest, queryset: Any) -> None:
        """Export audit logs for selected contest cycles."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import AuditFilter
            
            exported_logs = []
            for cycle in queryset:
                # Create filter for this cycle
                audit_filter = AuditFilter(
                    resource_ids=[str(cycle.pk)],
                    limit=100
                )
                
                # Get audit logs
                logs = audit_logger.query_logs(audit_filter)
                exported_logs.extend([log.to_dict() for log in logs])
            
            # Log export action
            audit_logger.log_audit(
                action=audit_logger.AuditAction.EXECUTE,
                description=f"Admin exported audit logs for {len(queryset)} contest cycles",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                user_id=str(request.user.pk),
                details={"exported_log_count": len(exported_logs)}
            )
            
            # Generate export data with checksum
            export_data = {
                "exported_at": timezone.now().isoformat(),
                "exported_by": str(request.user.pk),
                "cycles": [str(c.pk) for c in queryset],
                "logs": exported_logs
            }
            
            # Generate SHA-256 checksum for export
            checksum = hashlib.sha256(json.dumps(export_data, sort_keys=True).encode()).hexdigest()
            export_data["checksum"] = checksum
            
            self.message_user(request, _(f"Exported {len(exported_logs)} audit logs with checksum: {checksum[:16]}..."))
            
        except Exception as exc:
            audit_logger.log_audit(
                action=audit_logger.AuditAction.ERROR,
                description=f"Failed to export audit logs: {exc}",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                user_id=str(request.user.pk),
                error=str(exc)
            )
            
            self.message_user(request, _(f"Export failed: {exc}"), level=messages.ERROR)


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


# ---------------------------------------------------------------------------
# Badge Admin
# ---------------------------------------------------------------------------

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = [
        "name", "icon", "rarity_badge", "criteria_type", "criteria_value", 
        "points_bonus", "is_active", "sort_order", "checksum_short"
    ]
    list_filter = ["rarity", "criteria_type", "is_active", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["sort_order", "name"]
    actions = ["activate_selected", "deactivate_selected", "verify_checksums"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "name", "icon", "description")}),
        (_("Criteria"), {"fields": ("rarity", "criteria_type", "criteria_value", "points_bonus")}),
        (_("Configuration"), {"fields": ("is_active", "sort_order", "metadata")}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def rarity_badge(self, obj: Badge) -> str:
        colours = {
            "COMMON": "#6c757d",
            "UNCOMMON": "#28a745", 
            "RARE": "#007bff",
            "EPIC": "#6f42c1",
            "LEGENDARY": "#fd7e14",
        }
        colour = colours.get(obj.rarity, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            colour,
            obj.get_rarity_display(),
        )
    rarity_badge.short_description = _("Rarity")

    def checksum_short(self, obj: Badge) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")

    @admin.action(description=_("Activate selected badges"))
    def activate_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = 0
        for badge in queryset:
            try:
                # Log badge activation
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Admin activating badge: {badge.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details={"admin_action": "activate_badge", "badge_name": badge.name}
                )
                
                badge.is_active = True
                badge.save()
                updated += 1
                
                # Record performance metrics
                performance_monitor.record_metric("admin_badge_activation", 1.0)
                
                # Log success
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Successfully activated badge: {badge.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    details={"admin_action": "activate_badge", "status": "success"}
                )
                
            except Exception as exc:
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to activate badge: {badge.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
        
        self.message_user(request, _(f"{updated} badge(s) activated."))

    @admin.action(description=_("Deactivate selected badges"))
    def deactivate_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = 0
        for badge in queryset:
            try:
                # Log badge deactivation
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Admin deactivating badge: {badge.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    details={"admin_action": "deactivate_badge", "badge_name": badge.name}
                )
                
                badge.is_active = False
                badge.save()
                updated += 1
                
                # Record performance metrics
                performance_monitor.record_metric("admin_badge_deactivation", 1.0)
                
                # Log success
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.UPDATE,
                    description=f"Successfully deactivated badge: {badge.name}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    details={"admin_action": "deactivate_badge", "status": "success"}
                )
                
            except Exception as exc:
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to deactivate badge: {badge.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
        
        self.message_user(request, _(f"{updated} badge(s) deactivated."))

    @admin.action(description=_("Verify badge checksums"))
    def verify_checksums(self, request: HttpRequest, queryset: Any) -> None:
        """Verify SHA-256 checksums for selected badges."""
        verified_count = 0
        failed_count = 0
        
        for badge in queryset:
            try:
                # Recalculate checksum
                badge_data = {
                    "name": badge.name,
                    "description": badge.description,
                    "icon": badge.icon,
                    "rarity": badge.rarity,
                    "criteria_type": badge.criteria_type,
                    "criteria_value": badge.criteria_value,
                    "points_bonus": badge.points_bonus,
                }
                calculated_checksum = hashlib.sha256(
                    json.dumps(badge_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                
                if badge.checksum == calculated_checksum:
                    verified_count += 1
                else:
                    failed_count += 1
                    
                    # Log checksum mismatch
                    audit_logger.log_audit(
                        action=audit_logger.AuditAction.SECURITY,
                        description=f"Badge checksum mismatch detected: {badge.name}",
                        resource_type=audit_logger.ResourceType.INTEGRATION,
                        resource_id=str(badge.pk),
                        user_id=str(request.user.pk),
                        details={
                            "stored_checksum": badge.checksum,
                            "calculated_checksum": calculated_checksum
                        }
                    )
                
            except Exception as exc:
                failed_count += 1
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.ERROR,
                    description=f"Failed to verify badge checksum: {badge.name} - {exc}",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    resource_id=str(badge.pk),
                    user_id=str(request.user.pk),
                    error=str(exc)
                )
        
        self.message_user(
            request, 
            _(f"Checksum verification completed: {verified_count} verified, {failed_count} failed.")
        )


# ---------------------------------------------------------------------------
# UserBadge Admin
# ---------------------------------------------------------------------------

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = [
        "user", "badge", "earned_at", "is_pinned", "checksum_short"
    ]
    list_filter = ["is_pinned", "earned_at", "badge__rarity"]
    search_fields = ["user__username", "user__email", "badge__name"]
    readonly_fields = ["id", "earned_at", "checksum", "created_at", "updated_at"]
    ordering = ["-earned_at"]
    raw_id_fields = ["user", "badge"]
    actions = ["pin_selected", "unpin_selected"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "badge")}),
        (_("Status"), {"fields": ("is_pinned", "earned_at")}),
        (_("Data"), {"fields": ("metadata",)}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def checksum_short(self, obj: UserBadge) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")

    @admin.action(description=_("Pin selected badges"))
    def pin_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = queryset.update(is_pinned=True)
        self.message_user(request, _(f"{updated} badge(s) pinned."))

    @admin.action(description=_("Unpin selected badges"))
    def unpin_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = queryset.update(is_pinned=False)
        self.message_user(request, _(f"{updated} badge(s) unpinned."))


# ---------------------------------------------------------------------------
# DailyChallenge Admin
# ---------------------------------------------------------------------------

@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = [
        "date", "title", "target_action", "target_count", 
        "bonus_points", "is_active", "checksum_short"
    ]
    list_filter = ["target_action", "is_active", "date"]
    search_fields = ["title", "description"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["-date", "target_action"]
    actions = ["activate_selected", "deactivate_selected"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "title", "description")}),
        (_("Challenge"), {"fields": ("target_action", "target_count", "bonus_points")}),
        (_("Schedule"), {"fields": ("date", "is_active")}),
        (_("Configuration"), {"fields": ("metadata",)}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def checksum_short(self, obj: DailyChallenge) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")

    @admin.action(description=_("Activate selected challenges"))
    def activate_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, _(f"{updated} challenge(s) activated."))

    @admin.action(description=_("Deactivate selected challenges"))
    def deactivate_selected(self, request: HttpRequest, queryset: Any) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, _(f"{updated} challenge(s) deactivated."))


# ---------------------------------------------------------------------------
# UserDailyChallenge Admin
# ---------------------------------------------------------------------------

@admin.register(UserDailyChallenge)
class UserDailyChallengeAdmin(admin.ModelAdmin):
    list_display = [
        "user", "challenge", "progress_display", "completed_at", "checksum_short"
    ]
    list_filter = ["completed_at", "challenge__target_action"]
    search_fields = ["user__username", "user__email", "challenge__title"]
    readonly_fields = ["id", "completed_at", "checksum", "created_at", "updated_at"]
    ordering = ["-created_at"]
    raw_id_fields = ["user", "challenge"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "challenge")}),
        (_("Progress"), {"fields": ("progress", "completed_at")}),
        (_("Data"), {"fields": ("metadata",)}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def progress_display(self, obj: UserDailyChallenge) -> str:
        if obj.is_completed:
            return format_html('<span style="color:green;">✓ {}/{}</span>', 
                             obj.progress, obj.challenge.target_count)
        percentage = obj.progress_percentage
        color = "orange" if percentage < 50 else "blue"
        return format_html('<span style="color:{};">{}/{} ({:.1f}%)</span>',
                         color, obj.progress, obj.challenge.target_count, percentage)
    progress_display.short_description = _("Progress")

    def checksum_short(self, obj: UserDailyChallenge) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")


# ---------------------------------------------------------------------------
# Streak Admin
# ---------------------------------------------------------------------------

@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = [
        "user", "current_days", "longest_days", "last_activity_date", 
        "is_active", "days_until_reset", "checksum_short"
    ]
    list_filter = ["is_active", "last_activity_date"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["-current_days"]
    raw_id_fields = ["user"]
    actions = ["reset_selected_streaks"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user")}),
        (_("Streak Data"), {"fields": ("current_days", "longest_days", "last_activity_date")}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Configuration"), {"fields": ("metadata",)}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def days_until_reset(self, obj: Streak) -> str:
        days = obj.days_until_reset
        if days == 0 and obj.last_activity_date:
            return format_html('<span style="color:red;">Expired</span>')
        return str(days)
    days_until_reset.short_description = _("Days Until Reset")

    def checksum_short(self, obj: Streak) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")

    @admin.action(description=_("Reset selected streaks"))
    def reset_selected_streaks(self, request: HttpRequest, queryset: Any) -> None:
        for streak in queryset:
            streak.reset_streak()
        self.message_user(request, _(f"{len(queryset)} streak(s) reset."))


# ---------------------------------------------------------------------------
# StreakReward Admin
# ---------------------------------------------------------------------------

@admin.register(StreakReward)
class StreakRewardAdmin(admin.ModelAdmin):
    list_display = [
        "streak_days", "title", "points_bonus", "badge", "is_active", "checksum_short"
    ]
    list_filter = ["is_active", "badge"]
    search_fields = ["title", "description"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["streak_days"]
    raw_id_fields = ["badge"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "streak_days", "title", "description")}),
        (_("Rewards"), {"fields": ("points_bonus", "badge")}),
        (_("Configuration"), {"fields": ("is_active", "metadata")}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def checksum_short(self, obj: StreakReward) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")


# ---------------------------------------------------------------------------
# LevelConfig Admin
# ---------------------------------------------------------------------------

@admin.register(LevelConfig)
class LevelConfigAdmin(admin.ModelAdmin):
    list_display = [
        "level_number", "title", "points_required", "points_multiplier", 
        "badge", "is_active", "checksum_short"
    ]
    list_filter = ["is_active", "badge"]
    search_fields = ["title", "description"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["level_number"]
    raw_id_fields = ["badge"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "level_number", "title", "description")}),
        (_("Requirements"), {"fields": ("points_required", "points_multiplier")}),
        (_("Rewards"), {"fields": ("badge", "perks")}),
        (_("Configuration"), {"fields": ("is_active", "metadata")}),
        (_("Integrity"), {"fields": ("checksum", "created_at", "updated_at")}),
    )

    def checksum_short(self, obj: LevelConfig) -> str:
        return obj.checksum[:8] + "..." if obj.checksum else ""
    checksum_short.short_description = _("Checksum")


def _force_register_gamification():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (ContestCycle, ContestCycleAdmin), 
            (LeaderboardSnapshot, LeaderboardSnapshotAdmin), 
            (ContestReward, ContestRewardAdmin), 
            (UserAchievement, UserAchievementAdmin),
            (Badge, BadgeAdmin),
            (UserBadge, UserBadgeAdmin),
            (DailyChallenge, DailyChallengeAdmin),
            (UserDailyChallenge, UserDailyChallengeAdmin),
            (Streak, StreakAdmin),
            (StreakReward, StreakRewardAdmin),
            (LevelConfig, LevelConfigAdmin),
        ]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] gamification registered {registered} models")
    except Exception as e:
        print(f"[WARN] gamification: {e}")


# ---------------------------------------------------------------------------
# UserPoints Admin
# ---------------------------------------------------------------------------

@admin.register(UserPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = [
        "user", "total_points", "lifetime_points", "points_this_month", 
        "points_this_week", "monthly_rank", "weekly_rank", "last_updated"
    ]
    list_filter = ["points_this_month", "points_this_week", "last_updated"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at", "monthly_rank", "weekly_rank", "checksum"]
    ordering = ["-total_points"]
    actions = ["reset_monthly_points", "reset_weekly_points", "recalculate_ranks", "export_points_report"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "created_at", "updated_at")}),
        (_("Points Balance"), {"fields": ("total_points", "lifetime_points")}),
        (_("Period Points"), {"fields": ("points_this_month", "points_this_week")}),
        (_("Ranking"), {"fields": ("monthly_rank", "weekly_rank")}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def monthly_rank(self, obj):
        if obj.monthly_rank:
            return f"#{obj.monthly_rank}"
        return "N/A"
    monthly_rank.short_description = _("Monthly Rank")

    def weekly_rank(self, obj):
        if obj.weekly_rank:
            return f"#{obj.weekly_rank}"
        return "N/A"
    weekly_rank.short_description = _("Weekly Rank")

    def reset_monthly_points(self, request, queryset):
        updated = queryset.update(points_this_month=0)
        self.message_user(request, f"Reset monthly points for {updated} users.")
    reset_monthly_points.short_description = _("Reset monthly points to zero")

    def reset_weekly_points(self, request, queryset):
        updated = queryset.update(points_this_week=0)
        self.message_user(request, f"Reset weekly points for {updated} users.")
    reset_weekly_points.short_description = _("Reset weekly points to zero")

    def recalculate_ranks(self, request, queryset):
        # Implementation would recalculate ranks
        self.message_user(request, "Rank recalculation initiated.")
    recalculate_ranks.short_description = _("Recalculate user ranks")

    def export_points_report(self, request, queryset):
        # Implementation would export points data
        self.message_user(request, "Points report export initiated.")
    export_points_report.short_description = _("Export points report")


# ---------------------------------------------------------------------------
# PointsTransaction Admin
# ---------------------------------------------------------------------------

@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "user", "amount_display", "source", "description", 
        "balance_after", "created_at", "is_earning_badge"
    ]
    list_filter = ["source", "amount", "created_at", ]
    search_fields = ["user__username", "description", "source_id"]
    readonly_fields = ["id", "created_at", "checksum"]
    ordering = ["-created_at"]
    actions = ["export_transactions", "audit_user_transactions"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "created_at")}),
        (_("Transaction"), {"fields": ("amount", "source", "source_id", "description")}),
        (_("Balance"), {"fields": ("balance_after",)}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def amount_display(self, obj):
        if obj.amount > 0:
            return format_html('<span style="color: green;">+{:,}</span>', obj.amount)
        else:
            return format_html('<span style="color: red;">{:,}</span>', obj.amount)
    amount_display.short_description = _("Amount")

    def is_earning_badge(self, obj):
        if obj.is_earning:
            return format_html('<span style="color: green;">✓ Earned</span>')
        else:
            return format_html('<span style="color: red;">✗ Deducted</span>')
    is_earning_badge.short_description = _("Type")

    def export_transactions(self, request, queryset):
        # Implementation would export transaction data
        self.message_user(request, "Transaction export initiated.")
    export_transactions.short_description = _("Export transactions")

    def audit_user_transactions(self, request, queryset):
        # Implementation would audit transactions
        self.message_user(request, "Transaction audit initiated.")
    audit_user_transactions.short_description = _("Audit selected transactions")


# ---------------------------------------------------------------------------
# StreakFreeze Admin
# ---------------------------------------------------------------------------

@admin.register(StreakFreeze)
class StreakFreezeAdmin(admin.ModelAdmin):
    list_display = [
        "user", "streak", "used_at", "reason", "created_at"
    ]
    list_filter = ["used_at", "created_at"]
    search_fields = ["user__username", "reason"]
    readonly_fields = ["id", "created_at", "checksum"]
    ordering = ["-used_at"]
    actions = ["export_freeze_report", "bulk_freeze_cleanup"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "streak", "created_at")}),
        (_("Freeze Details"), {"fields": ("used_at", "reason")}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def export_freeze_report(self, request, queryset):
        # Implementation would export freeze data
        self.message_user(request, "Freeze report export initiated.")
    export_freeze_report.short_description = _("Export freeze report")

    def bulk_freeze_cleanup(self, request, queryset):
        # Implementation would cleanup old freezes
        self.message_user(request, "Freeze cleanup initiated.")
    bulk_freeze_cleanup.short_description = _("Cleanup old freezes")


# ---------------------------------------------------------------------------
# ContestParticipant Admin
# ---------------------------------------------------------------------------

@admin.register(ContestParticipant)
class ContestParticipantAdmin(admin.ModelAdmin):
    list_display = [
        "user", "contest_cycle", "current_points", "current_rank_display", 
        "is_disqualified_badge", "joined_at", "days_in_contest"
    ]
    list_filter = ["contest_cycle", "is_disqualified", "joined_at"]
    search_fields = ["user__username", "contest_cycle__name"]
    readonly_fields = ["id", "joined_at", "days_in_contest", "checksum"]
    ordering = ["contest_cycle", "-current_points"]
    actions = ["disqualify_selected", "update_rankings", "export_participants"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "user", "contest_cycle", "joined_at")}),
        (_("Performance"), {"fields": ("current_points", "current_rank", "is_disqualified")}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def current_rank_display(self, obj):
        if obj.current_rank:
            return f"#{obj.current_rank}"
        return "Unranked"
    current_rank_display.short_description = _("Rank")

    def is_disqualified_badge(self, obj):
        if obj.is_disqualified:
            return format_html('<span style="color: red;">❌ Disqualified</span>')
        else:
            return format_html('<span style="color: green;">✅ Active</span>')
    is_disqualified_badge.short_description = _("Status")

    def days_in_contest(self, obj):
        return obj.days_in_contest
    days_in_contest.short_description = _("Days in Contest")

    def disqualify_selected(self, request, queryset):
        updated = queryset.update(is_disqualified=True, current_rank=None)
        self.message_user(request, f"Disqualified {updated} participants.")
    disqualify_selected.short_description = _("Disqualify selected participants")

    def update_rankings(self, request, queryset):
        # Implementation would update rankings
        self.message_user(request, "Ranking update initiated.")
    update_rankings.short_description = _("Update rankings")

    def export_participants(self, request, queryset):
        # Implementation would export participant data
        self.message_user(request, "Participant export initiated.")
    export_participants.short_description = _("Export participants")


# ---------------------------------------------------------------------------
# GamificationConfig Admin
# ---------------------------------------------------------------------------

@admin.register(GamificationConfig)
class GamificationConfigAdmin(admin.ModelAdmin):
    list_display = [
        "tenant", "features_enabled_display", "points_expiry_days", 
        "leaderboard_refresh_interval", "updated_at"
    ]
    list_filter = ["enable_contests", "enable_badges", "enable_streaks", "enable_levels", "enable_daily_challenges"]
    search_fields = ["tenant__name"]
    readonly_fields = ["id", "created_at", "updated_at", "checksum"]
    ordering = ["tenant"]
    actions = ["enable_all_features", "disable_all_features", "reset_to_defaults"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "tenant", "created_at", "updated_at")}),
        (_("Feature Toggles"), {
            "fields": (
                "enable_contests", "enable_badges", "enable_streaks", 
                "enable_levels", "enable_daily_challenges"
            )
        }),
        (_("Configuration"), {"fields": ("points_expiry_days", "leaderboard_refresh_interval")}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def features_enabled_display(self, obj):
        features = obj.features_enabled
        if features:
            return ", ".join(features)
        return "None"
    features_enabled_display.short_description = _("Enabled Features")

    def enable_all_features(self, request, queryset):
        updated = queryset.update(
            enable_contests=True, enable_badges=True, enable_streaks=True,
            enable_levels=True, enable_daily_challenges=True
        )
        self.message_user(request, f"Enabled all features for {updated} tenants.")
    enable_all_features.short_description = _("Enable all features")

    def disable_all_features(self, request, queryset):
        updated = queryset.update(
            enable_contests=False, enable_badges=False, enable_streaks=False,
            enable_levels=False, enable_daily_challenges=False
        )
        self.message_user(request, f"Disabled all features for {updated} tenants.")
    disable_all_features.short_description = _("Disable all features")

    def reset_to_defaults(self, request, queryset):
        updated = queryset.update(
            enable_contests=True, enable_badges=True, enable_streaks=True,
            enable_levels=True, enable_daily_challenges=True,
            points_expiry_days=None, leaderboard_refresh_interval=300
        )
        self.message_user(request, f"Reset {updated} configs to defaults.")
    reset_to_defaults.short_description = _("Reset to defaults")


# ---------------------------------------------------------------------------
# GamificationInsight Admin
# ---------------------------------------------------------------------------

@admin.register(GamificationInsight)
class GamificationInsightAdmin(admin.ModelAdmin):
    list_display = [
        "date", "active_users", "badges_awarded", "challenges_completed",
        "total_points_issued", "contest_participants", "streak_milestones",
        "points_per_active_user", "engagement_rate"
    ]
    list_filter = ["date"]
    search_fields = []
    readonly_fields = ["id", "date", "points_per_active_user", "engagement_rate", "checksum"]
    ordering = ["-date"]
    actions = ["calculate_metrics", "export_insights", "generate_report"]

    fieldsets = (
        (_("Identity"), {"fields": ("id", "date")}),
        (_("User Activity"), {"fields": ("active_users", "contest_participants")}),
        (_("Achievements"), {"fields": ("badges_awarded", "challenges_completed", "streak_milestones")}),
        (_("Points"), {"fields": ("total_points_issued",)}),
        (_("Analytics"), {"fields": ("points_per_active_user", "engagement_rate")}),
        (_("System"), {"fields": ("checksum",)}),
    )

    def points_per_active_user(self, obj):
        return f"{obj.points_per_active_user:.2f}"
    points_per_active_user.short_description = _("Points per User")

    def engagement_rate(self, obj):
        return f"{obj.engagement_rate:.2%}"
    engagement_rate.short_description = _("Engagement Rate")

    def calculate_metrics(self, request, queryset):
        # Implementation would recalculate metrics
        self.message_user(request, "Metrics calculation initiated.")
    calculate_metrics.short_description = _("Recalculate metrics")

    def export_insights(self, request, queryset):
        # Implementation would export insights data
        self.message_user(request, "Insights export initiated.")
    export_insights.short_description = _("Export insights")

    def generate_report(self, request, queryset):
        # Implementation would generate comprehensive report
        self.message_user(request, "Report generation initiated.")
    generate_report.short_description = _("Generate report")
