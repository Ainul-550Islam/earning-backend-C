"""admin.py – Django admin for the postback module."""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .choices import PostbackStatus, RejectionReason, ValidatorStatus
from .models import DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog


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
