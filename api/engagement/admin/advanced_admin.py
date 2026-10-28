# engagement/admin/advanced_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.prestige import PrestigeLevel, UserPrestige, Milestone, UserMilestone, UserTitle
from ..models.anti_cheat import AntiCheatRule, AntiCheatLog, UserRiskScore, IPReputation
from ..models.campaign import UserSegment, Campaign, FeatureFlag, ABTest, ABTestVariant
from ..models.analytics import EngagementEvent, DailyPlatformMetric, RetentionCohort
from ..models.webhook import WebhookEndpoint, WebhookDelivery
from ..models.combo import ComboConfig, UserCombo, EnergyConfig, EnergyCost, UserEnergy
from .mixins import TenantFilterMixin, UserLinkMixin


# ── Prestige & Milestones ─────────────────────────────────────────────────────

@admin.register(PrestigeLevel)
class PrestigeLevelAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["level_badge", "name", "required_level",
                     "coin_multiplier", "xp_multiplier", "spin_bonus"]
    ordering      = ["level"]
    readonly_fields = ["created_at", "updated_at"]

    def level_badge(self, obj):
        icons = {1: "🥉", 2: "🥈", 3: "🥇", 4: "💎", 5: "👑"}
        icon  = icons.get(obj.level, "⭐")
        return format_html(
            '<span style="background:#FF9800;color:#fff;padding:3px 10px;border-radius:12px;">'
            '{} P{}</span>', icon, obj.level,
        )
    level_badge.short_description = "Prestige"


@admin.register(UserPrestige)
class UserPrestigeAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "prestige_level", "level_at_prestige",
                     "coin_multiplier", "xp_multiplier", "prestiged_at"]
    list_filter   = ["prestige_level"]
    search_fields = ["user__username"]
    ordering      = ["-prestiged_at"]
    readonly_fields = ["prestiged_at", "created_at", "updated_at"]


@admin.register(Milestone)
class MilestoneAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "metric", "threshold", "coin_reward", "xp_reward",
                     "title_reward", "is_active", "order"]
    list_filter   = ["metric", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["metric", "order", "threshold"]
    readonly_fields = ["created_at", "updated_at"]

    actions = ["check_milestones_all"]

    def check_milestones_all(self, request, queryset):
        from ..services.prestige_service import MilestoneService
        from django.contrib.auth import get_user_model
        User   = get_user_model()
        total  = 0
        for user in User.objects.filter(is_active=True).iterator(chunk_size=100):
            unlocked = MilestoneService.check_all(user)
            total   += len(unlocked)
        self.message_user(request, f"Unlocked {total} milestones across all users.")
    check_milestones_all.short_description = "Run milestone checks for all users"


@admin.register(UserMilestone)
class UserMilestoneAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "milestone_name", "reward_claimed", "unlocked_at"]
    list_filter   = ["reward_claimed"]
    search_fields = ["user__username", "milestone__name"]
    readonly_fields = ["unlocked_at", "created_at", "updated_at"]

    def milestone_name(self, obj):
        return obj.milestone.name
    milestone_name.short_description = "Milestone"


# ── Anti-Cheat ─────────────────────────────────────────────────────────────────

@admin.register(AntiCheatRule)
class AntiCheatRuleAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "rule_type", "severity_badge", "threshold",
                     "window_seconds", "action_badge", "is_active"]
    list_filter   = ["rule_type", "severity", "action", "is_active"]
    search_fields = ["name", "slug"]
    ordering      = ["-severity", "slug"]
    readonly_fields = ["created_at", "updated_at"]

    def severity_badge(self, obj):
        colors = {1: "#4CAF50", 2: "#FF9800", 3: "#F44336", 4: "#9C27B0"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}★</span>',
            colors.get(obj.severity, "#888"), obj.severity,
        )
    severity_badge.short_description = "Severity"

    def action_badge(self, obj):
        colors = {"flag": "#FF9800", "warn": "#2196F3", "suspend": "#F44336", "ban": "#9C27B0"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.action, "#888"), obj.action.upper(),
        )
    action_badge.short_description = "Action"


@admin.register(AntiCheatLog)
class AntiCheatLogAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "rule_name", "severity_badge", "status_badge",
                     "ip_address", "reviewed_by_name", "created_at"]
    list_filter   = ["status", "severity"]
    search_fields = ["user__username", "rule__name", "ip_address"]
    ordering      = ["-created_at"]
    readonly_fields = ["reviewed_at", "created_at", "updated_at"]

    def rule_name(self, obj):
        return obj.rule.name
    rule_name.short_description = "Rule"

    def severity_badge(self, obj):
        colors = {1: "#4CAF50", 2: "#FF9800", 3: "#F44336", 4: "#9C27B0"}
        return format_html(
            '<span style="color:{};">{}★</span>',
            colors.get(obj.severity, "#888"), obj.severity,
        )
    severity_badge.short_description = "Sev."

    def status_badge(self, obj):
        colors = {
            "pending": "#FF9800", "cleared": "#4CAF50",
            "warned": "#2196F3", "suspended": "#F44336", "banned": "#9C27B0",
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"

    def reviewed_by_name(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else "—"
    reviewed_by_name.short_description = "Reviewed By"

    actions = ["clear_selected", "suspend_users"]

    def clear_selected(self, request, queryset):
        queryset.update(status="cleared", reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"Cleared {queryset.count()} flags.")
    clear_selected.short_description = "Clear selected flags"

    def suspend_users(self, request, queryset):
        from ..models.anti_cheat import UserRiskScore
        count = 0
        for log in queryset:
            UserRiskScore.objects.filter(user=log.user).update(
                is_suspended=True, suspended_at=timezone.now(),
                suspension_reason="Admin action"
            )
            log.status      = "suspended"
            log.reviewed_by = request.user
            log.reviewed_at = timezone.now()
            log.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            count += 1
        self.message_user(request, f"Suspended {count} users.")
    suspend_users.short_description = "Suspend users for selected flags"


@admin.register(UserRiskScore)
class UserRiskScoreAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "score_bar", "flag_count", "is_suspended", "last_flag_at"]
    list_filter   = ["is_suspended"]
    search_fields = ["user__username"]
    ordering      = ["-score"]
    readonly_fields = ["last_flag_at", "suspended_at", "created_at", "updated_at"]

    def score_bar(self, obj):
        score = obj.score
        color = "#4CAF50" if score < 30 else "#FF9800" if score < 70 else "#F44336"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:80px;display:inline-block;">'
            '<div style="background:{};width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}',
            color, min(score, 100), score,
        )
    score_bar.short_description = "Risk Score"

    actions = ["unsuspend_users"]

    def unsuspend_users(self, request, queryset):
        updated = queryset.update(is_suspended=False, suspension_reason="")
        self.message_user(request, f"Unsuspended {updated} users.")
    unsuspend_users.short_description = "Unsuspend selected users"


# ── Campaign & Feature Flags ──────────────────────────────────────────────────

@admin.register(UserSegment)
class UserSegmentAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "criteria", "member_count", "is_dynamic", "last_synced"]
    list_filter   = ["criteria", "is_dynamic"]
    search_fields = ["name", "slug"]
    readonly_fields = ["member_count", "last_synced", "created_at", "updated_at"]

    actions = ["sync_segments"]

    def sync_segments(self, request, queryset):
        from ..services.campaign_service import SegmentService
        count = 0
        for segment in queryset:
            SegmentService.sync_segment(segment)
            count += segment.member_count
        self.message_user(request, f"Synced segments. Total members: {count}.")
    sync_segments.short_description = "Sync selected segments"


@admin.register(Campaign)
class CampaignAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "campaign_type_badge", "status_badge", "target_segment",
                     "reach_count", "conversion_rate_display", "starts_at"]
    list_filter   = ["campaign_type", "status"]
    search_fields = ["name", "slug"]
    readonly_fields = ["reach_count", "conversion_count", "created_at", "updated_at"]

    def campaign_type_badge(self, obj):
        return format_html(
            '<span style="background:#2196F3;color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            obj.campaign_type.replace("_", " "),
        )
    campaign_type_badge.short_description = "Type"

    def status_badge(self, obj):
        colors = {"draft": "#888", "scheduled": "#FF9800", "running": "#4CAF50",
                  "completed": "#607D8B", "cancelled": "#F44336"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"

    def conversion_rate_display(self, obj):
        return format_html('<span style="color:#4CAF50;">{}%</span>', obj.conversion_rate)
    conversion_rate_display.short_description = "Conv. Rate"

    actions = ["deliver_now"]

    def deliver_now(self, request, queryset):
        from ..services.campaign_service import CampaignService
        total = 0
        for campaign in queryset.filter(status__in=["draft", "scheduled"]):
            campaign.status = "scheduled"
            campaign.save(update_fields=["status"])
            total += CampaignService.deliver(campaign)
        self.message_user(request, f"Delivered to {total} users.")
    deliver_now.short_description = "Deliver selected campaigns now"


@admin.register(FeatureFlag)
class FeatureFlagAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["slug", "name", "enabled_badge", "rollout_pct_bar", "created_at"]
    list_filter   = ["is_enabled"]
    search_fields = ["slug", "name"]
    readonly_fields = ["created_at", "updated_at"]

    def enabled_badge(self, obj):
        if obj.is_enabled:
            return format_html('<span style="color:#4CAF50;font-weight:600;">ON</span>')
        return format_html('<span style="color:#F44336;font-weight:600;">OFF</span>')
    enabled_badge.short_description = "Enabled"

    def rollout_pct_bar(self, obj):
        pct = obj.rollout_pct
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:80px;display:inline-block;">'
            '<div style="background:#7F77DD;width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}%',
            pct, pct,
        )
    rollout_pct_bar.short_description = "Rollout"


@admin.register(ABTest)
class ABTestAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "status_badge", "variant_count", "winner_variant", "starts_at", "ends_at"]
    list_filter   = ["status"]
    search_fields = ["name", "slug"]
    readonly_fields = ["created_at", "updated_at"]

    def status_badge(self, obj):
        colors = {"draft": "#888", "running": "#4CAF50", "concluded": "#607D8B"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"

    def variant_count(self, obj):
        return obj.variants.count()
    variant_count.short_description = "Variants"


# ── Analytics ──────────────────────────────────────────────────────────────────

@admin.register(DailyPlatformMetric)
class DailyPlatformMetricAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["date", "dau", "checkins", "spins", "quests_completed",
                     "shop_purchases", "coins_distributed", "new_users"]
    list_filter   = ["date"]
    date_hierarchy = "date"
    ordering      = ["-date"]
    readonly_fields = [f.name for f in DailyPlatformMetric._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    actions = ["recompute_selected"]

    def recompute_selected(self, request, queryset):
        from ..services.analytics_service import AnalyticsService
        for metric in queryset:
            AnalyticsService.aggregate_daily(metric.date)
        self.message_user(request, f"Recomputed {queryset.count()} daily metrics.")
    recompute_selected.short_description = "Recompute selected dates"


@admin.register(EngagementEvent)
class EngagementEventAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "event_type", "coins_delta_display",
                     "xp_delta", "platform", "device_type", "event_time"]
    list_filter   = ["event_type", "platform", "device_type"]
    search_fields = ["user__username", "session_id"]
    date_hierarchy = "event_time"
    ordering      = ["-event_time"]
    readonly_fields = [f.name for f in EngagementEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def coins_delta_display(self, obj):
        if obj.coins_delta == 0:
            return "—"
        color = "#4CAF50" if obj.coins_delta > 0 else "#F44336"
        sign  = "+" if obj.coins_delta > 0 else ""
        return format_html('<span style="color:{};font-weight:600;">{}{}</span>',
                           color, sign, obj.coins_delta)
    coins_delta_display.short_description = "Δ Coins"


# ── Webhooks ──────────────────────────────────────────────────────────────────

@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["name", "url_short", "events_display", "is_active",
                     "success_count", "failure_count", "last_triggered"]
    list_filter   = ["is_active"]
    search_fields = ["name", "url"]
    readonly_fields = ["success_count", "failure_count", "last_triggered", "created_at", "updated_at"]

    def url_short(self, obj):
        url = obj.url[:50] + ("…" if len(obj.url) > 50 else "")
        return format_html('<a href="{}" target="_blank">{}</a>', obj.url, url)
    url_short.short_description = "URL"

    def events_display(self, obj):
        events = obj.events or []
        return ", ".join(str(e) for e in events[:3]) + ("…" if len(events) > 3 else "")
    events_display.short_description = "Events"

    actions = ["test_webhook"]

    def test_webhook(self, request, queryset):
        from ..services.webhook_service import WebhookService
        for ep in queryset:
            WebhookService.dispatch("test", {"message": "Test from admin"}, ep.tenant)
        self.message_user(request, f"Test payload dispatched to {queryset.count()} endpoints.")
    test_webhook.short_description = "Send test payload"


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["endpoint_name", "event_type", "status_badge",
                     "response_code", "attempt_count", "duration_ms", "created_at"]
    list_filter   = ["status", "event_type"]
    search_fields = ["endpoint__name", "event_type"]
    ordering      = ["-created_at"]
    readonly_fields = [f.name for f in WebhookDelivery._meta.fields]

    def endpoint_name(self, obj):
        return obj.endpoint.name
    endpoint_name.short_description = "Endpoint"

    def status_badge(self, obj):
        colors = {"pending": "#FF9800", "success": "#4CAF50", "failed": "#F44336",
                  "retrying": "#2196F3", "abandoned": "#9C27B0"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.status, "#888"), obj.status,
        )
    status_badge.short_description = "Status"

    actions = ["retry_selected"]

    def retry_selected(self, request, queryset):
        from ..services.webhook_service import WebhookService
        for delivery in queryset.filter(status__in=["failed", "retrying"]):
            WebhookService._deliver(delivery)
        self.message_user(request, f"Retried {queryset.count()} deliveries.")
    retry_selected.short_description = "Retry selected deliveries"


# ── Combo & Energy ────────────────────────────────────────────────────────────

@admin.register(ComboConfig)
class ComboConfigAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["action", "window_seconds", "max_multiplier", "step_multiplier", "is_active"]
    list_filter   = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(UserCombo)
class UserComboAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "action", "combo_streak", "multiplier_badge",
                     "max_streak_ever", "last_action_at"]
    list_filter   = ["action"]
    search_fields = ["user__username"]
    ordering      = ["-combo_streak"]
    readonly_fields = ["last_action_at", "created_at", "updated_at"]

    def multiplier_badge(self, obj):
        m = float(obj.current_multiplier)
        color = "#4CAF50" if m >= 2 else "#FF9800" if m >= 1.5 else "#888"
        return format_html(
            '<span style="color:{};font-weight:600;">×{}</span>', color, m
        )
    multiplier_badge.short_description = "Multiplier"


@admin.register(EnergyConfig)
class EnergyConfigAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["max_energy", "regen_per_hour", "is_active", "created_at"]
    list_filter   = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(UserEnergy)
class UserEnergyAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "energy_bar", "max_energy", "total_spent", "last_regen_at"]
    search_fields = ["user__username"]
    ordering      = ["current_energy"]
    readonly_fields = ["last_regen_at", "created_at", "updated_at"]

    def energy_bar(self, obj):
        pct   = int(obj.compute_current() / obj.max_energy * 100) if obj.max_energy else 0
        color = "#4CAF50" if pct > 50 else "#FF9800" if pct > 20 else "#F44336"
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:80px;display:inline-block;">'
            '<div style="background:{};width:{}%;height:8px;border-radius:4px;"></div></div>'
            ' {}',
            color, min(pct, 100), obj.compute_current(),
        )
    energy_bar.short_description = "Energy"

    actions = ["refill_energy"]

    def refill_energy(self, request, queryset):
        from ..services.combo_service import EnergyService
        for energy in queryset:
            EnergyService.refill(energy.user)
        self.message_user(request, f"Refilled energy for {queryset.count()} users.")
    refill_energy.short_description = "Refill energy for selected users"
