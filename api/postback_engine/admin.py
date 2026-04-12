"""
admin.py – Django Admin for Postback Engine.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    AdNetworkConfig, NetworkAdapterMapping, OfferPostback,
    ClickLog, PostbackRawLog, Conversion, Impression,
    FraudAttemptLog, IPBlacklist, ConversionDeduplication,
    PostbackQueue, RetryLog, NetworkPerformance, HourlyStat,
)


# ── AdNetworkConfig ───────────────────────────────────────────────────────────

@admin.register(AdNetworkConfig)
class AdNetworkConfigAdmin(admin.ModelAdmin):
    list_display = [
        "name", "network_key", "network_type", "status",
        "is_test_mode", "rate_limit_per_minute", "created_at",
    ]
    list_filter = ["status", "network_type", "is_test_mode"]
    search_fields = ["name", "network_key"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        ("Identity", {
            "fields": ("id", "name", "network_key", "network_type", "status", "is_test_mode", "logo_url"),
        }),
        ("Security", {
            "fields": ("secret_key", "api_key", "signature_algorithm", "require_nonce",
                       "ip_whitelist", "trust_x_forwarded_for"),
            "classes": ("collapse",),
        }),
        ("Field Mapping", {
            "fields": ("field_mapping", "required_fields"),
            "classes": ("collapse",),
        }),
        ("Rewards", {
            "fields": ("reward_rules", "default_reward_points", "default_reward_usd"),
        }),
        ("Deduplication & Attribution", {
            "fields": ("dedup_window", "attribution_model", "conversion_window_hours"),
        }),
        ("Rate Limiting", {
            "fields": ("rate_limit_per_minute",),
        }),
        ("Postback URL", {
            "fields": ("postback_url_template",),
            "classes": ("collapse",),
        }),
        ("Meta", {
            "fields": ("contact_email", "notes", "metadata", "created_at", "updated_at"),
        }),
    )


# ── PostbackRawLog ────────────────────────────────────────────────────────────

@admin.register(PostbackRawLog)
class PostbackRawLogAdmin(admin.ModelAdmin):
    list_display = [
        "id", "network_link", "status", "lead_id", "offer_id",
        "payout", "source_ip", "signature_verified",
        "rejection_reason", "received_at",
    ]
    list_filter = ["status", "rejection_reason", "signature_verified", "ip_whitelisted"]
    search_fields = ["lead_id", "click_id", "offer_id", "transaction_id", "source_ip"]
    readonly_fields = [
        "id", "raw_payload", "request_headers", "received_at",
        "processed_at", "retry_count",
    ]
    date_hierarchy = "received_at"
    list_select_related = ["network", "resolved_user"]

    def network_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f"/admin/postback_engine/adnetworkconfig/{obj.network_id}/change/",
            obj.network.network_key if obj.network else "—",
        )
    network_link.short_description = "Network"

    actions = ["replay_selected"]

    def replay_selected(self, request, queryset):
        from .tasks import process_postback_task
        count = 0
        for raw_log in queryset:
            process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
            count += 1
        self.message_user(request, f"Queued {count} postbacks for replay.")
    replay_selected.short_description = "Replay selected postbacks"


# ── Conversion ────────────────────────────────────────────────────────────────

@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = [
        "id", "user", "network", "offer_id",
        "status", "actual_payout", "points_awarded",
        "wallet_credited", "is_reversed", "converted_at",
    ]
    list_filter = ["status", "wallet_credited", "is_reversed"]
    search_fields = ["lead_id", "click_id", "offer_id", "transaction_id", "user__username"]
    readonly_fields = ["id", "converted_at", "approved_at", "wallet_credited_at"]
    date_hierarchy = "converted_at"
    list_select_related = ["user", "network"]

    actions = ["approve_selected", "reverse_selected"]

    def approve_selected(self, request, queryset):
        count = queryset.filter(status="pending").count()
        queryset.filter(status="pending").update(status="approved")
        self.message_user(request, f"Approved {count} conversions.")
    approve_selected.short_description = "Approve selected (pending)"

    def reverse_selected(self, request, queryset):
        from .conversion_tracking.conversion_manager import conversion_manager
        count = 0
        for conv in queryset:
            try:
                conversion_manager.reverse_conversion(conv, reason="Admin reversal")
                count += 1
            except Exception:
                pass
        self.message_user(request, f"Reversed {count} conversions.")
    reverse_selected.short_description = "Reverse selected conversions"


# ── ClickLog ──────────────────────────────────────────────────────────────────

@admin.register(ClickLog)
class ClickLogAdmin(admin.ModelAdmin):
    list_display = [
        "click_id", "user", "network", "offer_id",
        "status", "ip_address", "country", "device_type",
        "converted", "is_fraud", "fraud_score", "clicked_at",
    ]
    list_filter = ["status", "device_type", "converted", "is_fraud"]
    search_fields = ["click_id", "user__username", "ip_address", "offer_id"]
    readonly_fields = ["id", "click_id", "clicked_at", "converted_at"]
    date_hierarchy = "clicked_at"


# ── FraudAttemptLog ───────────────────────────────────────────────────────────

@admin.register(FraudAttemptLog)
class FraudAttemptLogAdmin(admin.ModelAdmin):
    list_display = [
        "id", "fraud_type", "fraud_score",
        "source_ip", "country",
        "is_auto_blocked", "is_reviewed", "detected_at",
    ]
    list_filter = ["fraud_type", "is_auto_blocked", "is_reviewed"]
    search_fields = ["source_ip", "device_fingerprint"]
    readonly_fields = ["id", "detected_at"]
    date_hierarchy = "detected_at"

    actions = ["mark_reviewed_confirmed", "mark_reviewed_dismissed"]

    def mark_reviewed_confirmed(self, request, queryset):
        queryset.update(is_reviewed=True, review_action="confirmed", reviewed_by=request.user)
        self.message_user(request, "Marked as confirmed fraud.")
    mark_reviewed_confirmed.short_description = "Mark as confirmed fraud"

    def mark_reviewed_dismissed(self, request, queryset):
        queryset.update(is_reviewed=True, review_action="dismissed", reviewed_by=request.user)
        self.message_user(request, "Marked as dismissed (false positive).")
    mark_reviewed_dismissed.short_description = "Dismiss (false positive)"


# ── IPBlacklist ───────────────────────────────────────────────────────────────

@admin.register(IPBlacklist)
class IPBlacklistAdmin(admin.ModelAdmin):
    list_display = [
        "blacklist_type", "value", "reason", "is_active",
        "added_by_system", "hit_count", "expires_at", "created_at",
    ]
    list_filter = ["blacklist_type", "reason", "is_active", "added_by_system"]
    search_fields = ["value", "notes"]

    actions = ["deactivate_selected"]

    def deactivate_selected(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} entries.")
    deactivate_selected.short_description = "Deactivate selected entries"


# ── NetworkPerformance ────────────────────────────────────────────────────────

@admin.register(NetworkPerformance)
class NetworkPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        "network", "date", "total_clicks", "approved_conversions",
        "conversion_rate", "total_payout_usd", "fraud_rate",
    ]
    list_filter = ["network"]
    date_hierarchy = "date"
    readonly_fields = ["computed_at"]


# ── HourlyStat ────────────────────────────────────────────────────────────────

@admin.register(HourlyStat)
class HourlyStatAdmin(admin.ModelAdmin):
    list_display = [
        "network", "date", "hour", "clicks", "conversions",
        "payout_usd", "fraud", "conversion_rate",
    ]
    list_filter = ["network"]
    date_hierarchy = "date"


# ── PostbackQueue ─────────────────────────────────────────────────────────────

@admin.register(PostbackQueue)
class PostbackQueueAdmin(admin.ModelAdmin):
    list_display = [
        "id", "raw_log", "priority", "status",
        "worker_id", "enqueued_at", "processing_started_at",
    ]
    list_filter = ["status", "priority"]
    readonly_fields = ["id", "enqueued_at", "processing_started_at", "processing_finished_at"]


# ── Other models ──────────────────────────────────────────────────────────────

admin.site.register(NetworkAdapterMapping)
admin.site.register(OfferPostback)
admin.site.register(ConversionDeduplication)
admin.site.register(RetryLog)
admin.site.register(Impression)


def _force_register_postback_engine():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (AdNetworkConfig, AdNetworkConfigAdmin),
            (PostbackRawLog, PostbackRawLogAdmin),
            (Conversion, ConversionAdmin),
            (ClickLog, ClickLogAdmin),
            (FraudAttemptLog, FraudAttemptLogAdmin),
            (IPBlacklist, IPBlacklistAdmin),
            (NetworkPerformance, NetworkPerformanceAdmin),
            (HourlyStat, HourlyStatAdmin),
            (PostbackQueue, PostbackQueueAdmin),
        ]
        registered=0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered+=1
            except Exception as ex:
                print(f"[WARN] {model.__name__}: {ex}")
        print(f"[OK] Postback Engine registered {registered} models")
    except Exception as e:
        print(f"[WARN] Postback Engine force-register: {e}")
