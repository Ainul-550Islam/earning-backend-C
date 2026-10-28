"""admin.py – Django admin for the postback module."""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .choices import PostbackStatus, RejectionReason, ValidatorStatus
from .models import (
    DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog,
    PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit,
    PostbackS2SLog,
)


class LeadValidatorInline(admin.TabularInline):
    model = LeadValidator
    extra = 0
    fields = ("name", "validator_type", "is_blocking", "is_active", "sort_order")
    ordering = ("sort_order",)


@admin.register(NetworkPostbackConfig)
class NetworkPostbackConfigAdmin(admin.ModelAdmin):
    list_display = (
        "name", "network_key", "network_type", "status_badge",
        "signature_algorithm", "rate_limit_per_minute", "created_at",
    )
    list_filter = ("status", "network_type", "signature_algorithm")
    search_fields = ("name", "network_key", "contact_email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [LeadValidatorInline]

    fieldsets = (
        (None, {"fields": ("id", "name", "network_key", "network_type", "status", "contact_email")}),
        (_("Security"), {"fields": (
            "secret_key", "signature_algorithm",
            "ip_whitelist", "trust_forwarded_for", "require_nonce",
        )}),
        (_("Field Mapping"), {"fields": ("field_mapping", "required_fields")}),
        (_("Deduplication"), {"fields": ("dedup_window",)}),
        (_("Rewards"), {"fields": ("reward_rules", "default_reward_points")}),
        (_("Rate Limiting"), {"fields": ("rate_limit_per_minute",)}),
        (_("Notes"), {"fields": ("notes", "metadata"), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colors = {
            ValidatorStatus.ACTIVE: "green",
            ValidatorStatus.INACTIVE: "red",
            ValidatorStatus.TESTING: "orange",
        }
        return format_html(
            '<b style="color:{};">{}</b>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    @admin.action(description=_("Activate selected networks"))
    def activate_networks(self, request, queryset):
        queryset.update(status=ValidatorStatus.ACTIVE)
        self.message_user(request, f"Activated {queryset.count()} network(s).")

    @admin.action(description=_("Deactivate selected networks"))
    def deactivate_networks(self, request, queryset):
        queryset.update(status=ValidatorStatus.INACTIVE)
        self.message_user(request, f"Deactivated {queryset.count()} network(s).")

    actions = ["activate_networks", "deactivate_networks"]


@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "network", "status_badge", "lead_id", "offer_id",
        "source_ip", "signature_verified", "payout",
        "points_awarded", "received_at",
    )
    list_filter = (
        "status", "rejection_reason", "signature_verified",
        "ip_whitelisted", "network",
    )
    search_fields = ("lead_id", "offer_id", "transaction_id", "source_ip")
    readonly_fields = (
        "id", "network", "raw_payload", "request_headers",
        "method", "query_string", "source_ip",
        "signature_verified", "ip_whitelisted",
        "received_at", "processed_at", "retry_count",
    )
    date_hierarchy = "received_at"
    ordering = ("-received_at",)

    fieldsets = (
        (None, {"fields": ("id", "network", "status", "method")}),
        (_("Payload"), {"fields": ("raw_payload", "query_string"), "classes": ("collapse",)}),
        (_("Extracted Fields"), {"fields": (
            "lead_id", "offer_id", "transaction_id", "payout", "currency"
        )}),
        (_("Security"), {"fields": (
            "source_ip", "signature_verified", "ip_whitelisted", "request_headers"
        )}),
        (_("Rejection"), {"fields": ("rejection_reason", "rejection_detail")}),
        (_("Reward"), {"fields": ("points_awarded", "inventory_id", "resolved_user")}),
        (_("Processing"), {"fields": (
            "retry_count", "processing_error", "next_retry_at",
            "received_at", "processed_at",
        )}),
    )

    def status_badge(self, obj):
        color_map = {
            PostbackStatus.REWARDED: "green",
            PostbackStatus.VALIDATED: "lightgreen",
            PostbackStatus.RECEIVED: "blue",
            PostbackStatus.PROCESSING: "orange",
            PostbackStatus.REJECTED: "red",
            PostbackStatus.DUPLICATE: "gray",
            PostbackStatus.FAILED: "darkred",
        }
        return format_html(
            '<b style="color:{};">{}</b>',
            color_map.get(obj.status, "black"),
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    @admin.action(description=_("Re-queue selected FAILED/REJECTED logs"))
    def retry_selected(self, request, queryset):
        from .tasks import process_postback
        queued = 0
        for log in queryset.filter(
            status__in=[PostbackStatus.FAILED, PostbackStatus.REJECTED]
        ):
            process_postback.delay(
                str(log.pk),
                signature="", timestamp_str="", nonce="",
                body_bytes_hex="", path="", query_params={},
            )
            queued += 1
        self.message_user(request, f"Queued {queued} log(s) for reprocessing.")

    actions = ["retry_selected"]


@admin.register(DuplicateLeadCheck)
class DuplicateLeadCheckAdmin(admin.ModelAdmin):
    list_display = ("network", "lead_id", "first_seen_at")
    list_filter = ("network",)
    search_fields = ("lead_id",)
    readonly_fields = ("id", "network", "lead_id", "first_seen_at", "postback_log")


@admin.register(LeadValidator)
class LeadValidatorAdmin(admin.ModelAdmin):
    list_display = (
        "name", "network", "validator_type",
        "is_blocking", "is_active", "sort_order",
    )
    list_filter = ("validator_type", "is_blocking", "is_active", "network")
    search_fields = ("name", "network__name")
    list_editable = ("is_active", "sort_order")


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass


# ── New Model Admin Classes ─────────────────────────────────────────────────────

@admin.register(PostbackInsight)
class PostbackInsightAdmin(admin.ModelAdmin):
    list_display = (
        "network", "date", "received_count", "rewarded_count",
        "health_score_badge", "anomaly_detected", "total_payout"
    )
    list_filter = ("network", "date", "anomaly_detected")
    search_fields = ("network__name", "network__network_key")
    readonly_fields = ("id", "integrity_hash", "created_at", "updated_at")
    date_hierarchy = "date"
    ordering = ("-date", "network")

    fieldsets = (
        (None, {"fields": ("id", "network", "date")}),
        (_("Count Metrics"), {"fields": (
            "received_count", "validated_count", "rewarded_count",
            "rejected_count", "duplicate_count", "failed_count"
        )}),
        (_("Financial Metrics"), {"fields": (
            "total_payout", "total_points_awarded"
        )}),
        (_("Health Metrics"), {"fields": (
            "health_score", "average_processing_time"
        )}),
        (_("Anomaly Detection"), {"fields": (
            "anomaly_detected", "anomaly_details"
        )}),
        (_("Integrity"), {"fields": (
            "integrity_hash",
        ), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def health_score_badge(self, obj):
        if obj.health_score >= 80:
            color = "green"
        elif obj.health_score >= 60:
            color = "orange"
        else:
            color = "red"
        return format_html(
            '<b style="color:{};">{}%</b>',
            color,
            obj.health_score
        )
    health_score_badge.short_description = _("Health Score")

    @admin.action(description=_("Recalculate selected insights"))
    def recalculate_insights(self, request, queryset):
        from .services import PostbackInsightService
        recalc_count = 0
        for insight in queryset:
            try:
                PostbackInsightService.recalculate_daily_insight(insight.network, insight.date)
                recalc_count += 1
            except Exception as e:
                pass
        self.message_user(request, f"Recalculated {recalc_count} insight(s).")

    @admin.action(description=_("Detect anomalies for selected insights"))
    def detect_anomalies(self, request, queryset):
        from .services import PostbackInsightService
        anomaly_count = 0
        for insight in queryset:
            try:
                anomalies = PostbackInsightService.detect_anomalies(insight.network, insight.date)
                if anomalies:
                    anomaly_count += 1
            except Exception as e:
                pass
        self.message_user(request, f"Found anomalies in {anomaly_count} insight(s).")

    actions = ["recalculate_insights", "detect_anomalies"]


@admin.register(PostbackTemplate)
class PostbackTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name", "network", "is_active", "usage_count",
        "last_used_at", "created_at"
    )
    list_filter = ("network", "is_active", "created_at")
    search_fields = ("name", "description", "network__name")
    readonly_fields = ("id", "usage_count", "last_used_at", "integrity_hash", "created_at", "updated_at")
    ordering = ("network", "name")

    fieldsets = (
        (None, {"fields": ("id", "network", "name", "is_active")}),
        (_("Template Content"), {"fields": (
            "template_body", "variables", "required_variables"
        )}),
        (_("Validation"), {"fields": (
            "validation_regex",
        )}),
        (_("Usage Tracking"), {"fields": (
            "usage_count", "last_used_at"
        ), "classes": ("collapse",)}),
        (_("Integrity"), {"fields": (
            "integrity_hash",
        ), "classes": ("collapse",)}),
        (_("Notes"), {"fields": ("description",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.action(description=_("Activate selected templates"))
    def activate_templates(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} template(s).")

    @admin.action(description=_("Deactivate selected templates"))
    def deactivate_templates(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} template(s).")

    actions = ["activate_templates", "deactivate_templates"]


@admin.register(PostbackIPWhitelist)
class PostbackIPWhitelistAdmin(admin.ModelAdmin):
    list_display = (
        "name", "network", "ip_address", "ip_type",
        "is_active", "priority", "usage_count"
    )
    list_filter = ("network", "is_active", "priority")
    search_fields = ("name", "ip_address", "description", "network__name")
    readonly_fields = ("id", "usage_count", "last_used_at", "integrity_hash", "created_at", "updated_at")
    ordering = ("-priority", "network", "name")

    fieldsets = (
        (None, {"fields": ("id", "network", "name", "is_active", "priority")}),
        (_("IP Configuration"), {"fields": (
            "ip_address", "description"
        )}),
        (_("Usage Tracking"), {"fields": (
            "usage_count", "last_used_at"
        ), "classes": ("collapse",)}),
        (_("Integrity"), {"fields": (
            "integrity_hash",
        ), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def ip_type(self, obj):
        import ipaddress
        try:
            ipaddress.ip_network(obj.ip_address, strict=False)
            return "CIDR" if '/' in obj.ip_address else "Single IP"
        except ValueError:
            return "Invalid"
    ip_type.short_description = _("IP Type")

    @admin.action(description=_("Activate selected rules"))
    def activate_rules(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} rule(s).")

    @admin.action(description=_("Deactivate selected rules"))
    def deactivate_rules(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} rule(s).")

    actions = ["activate_rules", "deactivate_rules"]


@admin.register(PostbackRateLimit)
class PostbackRateLimitAdmin(admin.ModelAdmin):
    list_display = (
        "name", "network", "max_per_minute", "current_count",
        "utilization_bar", "is_active", "is_blocked", "total_violations"
    )
    list_filter = ("network", "is_active", "is_blocked")
    search_fields = ("name", "description", "network__name")
    readonly_fields = ("id", "current_count", "total_violations", "last_violation_at", "last_reset_at", "window_start", "integrity_hash", "created_at", "updated_at")
    ordering = ("network", "name")

    fieldsets = (
        (None, {"fields": ("id", "network", "name", "is_active")}),
        (_("Rate Configuration"), {"fields": (
            "max_per_minute", "max_per_hour", "max_per_day"
        )}),
        (_("Current State"), {"fields": (
            "current_count", "is_blocked", "blocked_until"
        )}),
        (_("Tracking"), {"fields": (
            "total_violations", "last_violation_at",
            "last_reset_at", "window_start"
        ), "classes": ("collapse",)}),
        (_("Integrity"), {"fields": (
            "integrity_hash",
        ), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def utilization_bar(self, obj):
        if obj.max_per_minute == 0:
            return "N/A"
        
        utilization = (obj.current_count / obj.max_per_minute) * 100
        if utilization >= 90:
            color = "red"
        elif utilization >= 70:
            color = "orange"
        else:
            color = "green"
        
        return format_html(
            '<div style="width:100px; background:#eee; border-radius:3px;">'
            '<div style="width:{}%; background:{}; height:20px; border-radius:3px; text-align:center; line-height:20px; color:white; font-size:11px;">'
            '{}%</div></div>',
            min(100, utilization), color, round(utilization, 1)
        )
    utilization_bar.short_description = _("Utilization")

    @admin.action(description=_("Reset windows for selected limits"))
    def reset_windows(self, request, queryset):
        reset_count = 0
        for rate_limit in queryset:
            try:
                rate_limit.reset_window()
                reset_count += 1
            except Exception as e:
                pass
        self.message_user(request, f"Reset windows for {reset_count} rate limit(s).")

    @admin.action(description=_("Unblock selected limits"))
    def unblock_limits(self, request, queryset):
        updated = queryset.filter(is_blocked=True).update(
            is_blocked=False, blocked_until=None
        )
        self.message_user(request, f"Unblocked {updated} rate limit(s).")

    actions = ["reset_windows", "unblock_limits"]


def _force_register_postback():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (NetworkPostbackConfig, NetworkPostbackConfigAdmin), 
            (PostbackLog, PostbackLogAdmin), 
            (DuplicateLeadCheck, DuplicateLeadCheckAdmin), 
            (LeadValidator, LeadValidatorAdmin),
            (PostbackInsight, PostbackInsightAdmin),
            (PostbackTemplate, PostbackTemplateAdmin),
            (PostbackIPWhitelist, PostbackIPWhitelistAdmin),
            (PostbackRateLimit, PostbackRateLimitAdmin),
        ]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] postback registered {registered} models")
    except Exception as e:
        print(f"[WARN] postback: {e}")


@admin.register(PostbackS2SLog)
class PostbackS2SLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "postback_log", "http_status", "success",
        "attempt_number", "fired_at",
    )
    list_filter = ("success",)
    search_fields = ("callback_url", "error_message")
    readonly_fields = (
        "id", "postback_log", "callback_url", "http_status",
        "response_body", "success", "attempt_number", "error_message", "fired_at",
    )
    ordering = ("-fired_at",)

    def has_add_permission(self, request):
        return False  # Audit log — created only by the S2S sender

    def has_change_permission(self, request, obj=None):
        return False  # Immutable


# ── New earning-platform admin registrations ──────────────────────────────────

from .models import (
    OfferCategory, Offer, OfferClick, UserOfferCompletion,
    PaymentMethod, WithdrawalRequest,
    ReferralProgram, UserReferral,
    UserTier, UserTierMembership,
    DailyBonusConfig, UserLoginStreak,
    LeaderboardEntry, GeoTargetingRule,
    SurveyRouter, OfferwallSDKConfig,
)


@admin.register(OfferCategory)
class OfferCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "network", "category", "points_reward", "device_target", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "difficulty", "device_target", "network")
    search_fields = ("name", "external_offer_id", "description")
    list_editable = ("is_active", "is_featured")
    readonly_fields = ("id", "created_at", "updated_at")
    filter_horizontal = ()


@admin.register(OfferClick)
class OfferClickAdmin(admin.ModelAdmin):
    list_display = ("click_id", "offer", "user", "country_code", "device_type", "converted", "clicked_at")
    list_filter = ("converted", "device_type", "country_code")
    search_fields = ("click_id", "user__username")
    readonly_fields = ("id", "clicked_at")
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False


@admin.register(UserOfferCompletion)
class UserOfferCompletionAdmin(admin.ModelAdmin):
    list_display = ("user", "offer", "points_awarded", "is_reversed", "completed_at")
    list_filter = ("is_reversed",)
    readonly_fields = ("id", "completed_at")
    def has_add_permission(self, r): return False


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("user", "method_type", "is_verified", "is_default", "created_at")
    list_filter = ("method_type", "is_verified")
    search_fields = ("user__username",)
    readonly_fields = ("id", "account_identifier")


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "points_requested", "amount_bdt", "status", "payment_method", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "transaction_reference")
    readonly_fields = ("id", "user", "points_requested", "amount_bdt", "created_at")
    list_editable = ("status",)


@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "commission_type", "commission_value", "is_active")
    list_filter = ("is_active", "commission_type")


@admin.register(UserReferral)
class UserReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referee", "referral_code", "total_commission_earned", "is_active")
    list_filter = ("is_active",)
    readonly_fields = ("id",)


@admin.register(UserTier)
class UserTierAdmin(admin.ModelAdmin):
    list_display = ("name", "min_lifetime_points", "earnings_multiplier", "withdrawal_priority", "sort_order")
    list_editable = ("sort_order",)


@admin.register(UserTierMembership)
class UserTierMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tier", "lifetime_points", "tier_entered_at")
    list_filter = ("tier",)
    readonly_fields = ("user", "tier_entered_at")


@admin.register(DailyBonusConfig)
class DailyBonusConfigAdmin(admin.ModelAdmin):
    list_display = ("day_number", "points_reward", "is_milestone", "label")
    list_editable = ("points_reward", "is_milestone")


@admin.register(UserLoginStreak)
class UserLoginStreakAdmin(admin.ModelAdmin):
    list_display = ("user", "current_streak", "longest_streak", "last_claim_date", "total_points_from_bonus")
    readonly_fields = ("user",)
    def has_add_permission(self, r): return False


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("rank", "display_name", "period", "period_start", "points_earned", "offers_completed")
    list_filter = ("period",)
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False


@admin.register(GeoTargetingRule)
class GeoTargetingRuleAdmin(admin.ModelAdmin):
    list_display = ("network", "country_code", "action", "payout_multiplier", "priority", "is_active")
    list_filter = ("action", "is_active")
    search_fields = ("country_code", "network__network_key")


@admin.register(SurveyRouter)
class SurveyRouterAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_key", "device_support", "priority", "is_active")
    list_filter = ("is_active", "device_support", "provider_key")
    search_fields = ("name", "provider_key")


@admin.register(OfferwallSDKConfig)
class OfferwallSDKConfigAdmin(admin.ModelAdmin):
    list_display = ("publisher_name", "sdk_key", "network", "theme", "is_active")
    list_filter = ("is_active", "theme")
    readonly_fields = ("sdk_key", "sdk_secret")


# ── Round-2 admin ─────────────────────────────────────────────────────────────

from .models import (
    SiteConfig, CurrencyRate, ManualPointAdjustment,
    FCMDevice, OfferImpression, OfferDailyCapCounter,
)


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Economy", {"fields": (
            "points_to_bdt_rate", "points_to_usd_rate",
            "min_withdrawal_points", "max_withdrawal_points_per_day",
        )}),
        ("Features", {"fields": (
            "maintenance_mode",
            "referral_program_enabled", "daily_bonus_enabled",
            "leaderboard_enabled", "survey_router_enabled", "offerwall_enabled",
        )}),
        ("Fraud Limits", {"fields": (
            "max_completions_per_user_per_day",
            "max_withdrawal_requests_per_day",
            "withdrawal_fraud_hold_hours",
        )}),
        ("Audit", {"fields": ("updated_at", "updated_by")}),
    )
    readonly_fields = ("updated_at", "updated_by")

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("points_to_bdt", "points_to_usd", "effective_from", "set_by")
    readonly_fields = ("id", "effective_from", "set_by")
    ordering = ["-effective_from"]

    def save_model(self, request, obj, form, change):
        obj.set_by = request.user
        super().save_model(request, obj, form, change)
        cfg = SiteConfig.get()
        cfg.points_to_bdt_rate = obj.points_to_bdt
        cfg.points_to_usd_rate = obj.points_to_usd
        cfg.updated_by = request.user
        cfg.save()


@admin.register(ManualPointAdjustment)
class ManualPointAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("user", "adjustment_type", "points", "reason", "performed_by", "created_at")
    list_filter = ("adjustment_type", "reason")
    search_fields = ("user__username", "note")
    readonly_fields = ("id", "performed_by", "created_at")

    def save_model(self, request, obj, form, change):
        obj.performed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_id", "is_active", "last_used_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "device_id")
    readonly_fields = ("id", "registration_id", "last_used_at", "created_at")


@admin.register(OfferImpression)
class OfferImpressionAdmin(admin.ModelAdmin):
    list_display = ("offer", "user", "country_code", "device_type", "shown_at")
    list_filter = ("country_code", "device_type")
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False


@admin.register(OfferDailyCapCounter)
class OfferDailyCapCounterAdmin(admin.ModelAdmin):
    list_display = ("offer", "user", "date", "user_count")
    list_filter = ("date",)
    readonly_fields = ("offer", "user", "date")
