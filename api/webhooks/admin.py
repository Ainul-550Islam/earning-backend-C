# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
admin.py: Django Admin configuration with color-coded status badges,
bulk actions, and inline delivery log viewer.
"""

import logging

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .constants import DeliveryStatus, EndpointStatus
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from .services import DispatchService

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  COLOR HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_DELIVERY_COLORS = {
    DeliveryStatus.SUCCESS:    ("#28a745", "#fff"),    # green
    DeliveryStatus.FAILED:     ("#dc3545", "#fff"),    # red
    DeliveryStatus.RETRYING:   ("#fd7e14", "#fff"),    # orange
    DeliveryStatus.EXHAUSTED:  ("#6f0000", "#fff"),    # dark red
    DeliveryStatus.PENDING:    ("#6c757d", "#fff"),    # grey
    DeliveryStatus.DISPATCHED: ("#007bff", "#fff"),    # blue
    DeliveryStatus.CANCELLED:  ("#343a40", "#fff"),    # charcoal
}

_ENDPOINT_COLORS = {
    EndpointStatus.ACTIVE:    ("#28a745", "#fff"),
    EndpointStatus.PAUSED:    ("#ffc107", "#000"),
    EndpointStatus.DISABLED:  ("#6c757d", "#fff"),
    EndpointStatus.SUSPENDED: ("#dc3545", "#fff"),
}


def _badge(text: str, bg: str, fg: str) -> str:
    return format_html(
        '<span style="'
        "background:{bg};color:{fg};"
        "padding:3px 10px;border-radius:12px;"
        'font-size:11px;font-weight:700;letter-spacing:.5px;">'
        "{text}</span>",
        bg=bg, fg=fg, text=text.upper(),
    )


def _delivery_badge(status_val: str) -> str:
    bg, fg = _DELIVERY_COLORS.get(status_val, ("#6c757d", "#fff"))
    return _badge(status_val, bg, fg)


def _endpoint_badge(status_val: str) -> str:
    bg, fg = _ENDPOINT_COLORS.get(status_val, ("#6c757d", "#fff"))
    return _badge(status_val, bg, fg)


# ─────────────────────────────────────────────────────────────────────────────
#  SUBSCRIPTION INLINE
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscriptionInline(admin.TabularInline):
    """
    Ainul Enterprise Engine — Subscription inline inside Endpoint admin.
    """
    model          = WebhookSubscription
    extra          = 0
    fields         = ("event_type", "is_active", "filters")
    show_change_link = True


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY LOG INLINE
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryLogInline(admin.TabularInline):
    """
    Ainul Enterprise Engine — Last 10 delivery logs inside Endpoint admin.
    """
    model          = WebhookDeliveryLog
    extra          = 0
    max_num        = 10
    can_delete     = False
    show_change_link = True
    readonly_fields = (
        "delivery_id", "event_type", "colored_status",
        "http_status_code", "attempt_number", "dispatched_at",
    )
    fields = readonly_fields

    def colored_status(self, obj):
        return format_html(_delivery_badge(obj.status))
    colored_status.short_description = "Status"

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-created_at")[:10]


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK ENDPOINT ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    """
    Ainul Enterprise Engine — Webhook Endpoint Admin.
    Full management with inline subscriptions, delivery logs, and actions.
    """

    list_display = (
        "label",
        "owner",
        "short_url",
        "colored_status",
        "success_rate_display",
        "total_deliveries",
        "last_triggered_at",
        "created_at",
    )
    list_filter  = ("status", "http_method", "verify_ssl", "created_at")
    search_fields = ("label", "target_url", "owner__email", "owner__username")
    readonly_fields = (
        "id",
        "secret_key",
        "total_deliveries",
        "success_deliveries",
        "failed_deliveries",
        "last_triggered_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        ("🎯 Identity", {
            "fields": ("id", "label", "owner", "tenant", "description"),
        }),
        ("🔗 Target", {
            "fields": ("target_url", "http_method", "custom_headers", "verify_ssl", "version"),
        }),
        ("🔐 Security", {
            "fields": ("secret_key",),
            "classes": ("collapse",),
        }),
        ("⚙️ Configuration", {
            "fields": ("status", "max_retries"),
        }),
        ("📊 Statistics", {
            "fields": (
                "total_deliveries",
                "success_deliveries",
                "failed_deliveries",
                "last_triggered_at",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )
    inlines      = [WebhookSubscriptionInline, WebhookDeliveryLogInline]
    actions      = [
        "action_pause_endpoints",
        "action_resume_endpoints",
        "action_rotate_secrets",
    ]
    ordering     = ["-created_at"]
    list_per_page = 30

    # ── Display helpers ───────────────────────────────────────────────────────

    def colored_status(self, obj):
        return format_html(_endpoint_badge(obj.status))
    colored_status.short_description = "Status"
    colored_status.admin_order_field = "status"

    def short_url(self, obj):
        url = obj.target_url
        display = url if len(url) <= 55 else url[:52] + "…"
        return format_html(
            '<a href="{url}" target="_blank" title="{url}">{display}</a>',
            url=url, display=display,
        )
    short_url.short_description = "Target URL"

    def success_rate_display(self, obj):
        rate = obj.success_rate
        if rate >= 90:
            colour = "#28a745"
        elif rate >= 60:
            colour = "#ffc107"
        else:
            colour = "#dc3545"
        return format_html(
            '<span style="color:{c};font-weight:700;">{r}%</span>',
            c=colour, r=rate,
        )
    success_rate_display.short_description = "Success Rate"

    # ── Bulk Actions ──────────────────────────────────────────────────────────

    @admin.action(description="⏸️  Pause selected endpoints")
    def action_pause_endpoints(self, request, queryset):
        updated = queryset.exclude(status=EndpointStatus.PAUSED).update(
            status=EndpointStatus.PAUSED
        )
        self.message_user(request, f"Paused {updated} endpoint(s).", messages.WARNING)

    @admin.action(description="▶️  Resume selected endpoints (set ACTIVE)")
    def action_resume_endpoints(self, request, queryset):
        updated = queryset.update(status=EndpointStatus.ACTIVE)
        self.message_user(request, f"Activated {updated} endpoint(s).", messages.SUCCESS)

    @admin.action(description="🔄 Rotate secrets for selected endpoints")
    def action_rotate_secrets(self, request, queryset):
        count = 0
        for endpoint in queryset:
            endpoint.rotate_secret()
            endpoint.save(update_fields=["secret_key", "updated_at"])
            count += 1
        self.message_user(
            request,
            f"Rotated secrets for {count} endpoint(s). "
            "Ensure consumers are updated immediately.",
            messages.WARNING,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SUBSCRIPTION ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    """
    Ainul Enterprise Engine — Webhook Subscription Admin.
    """
    list_display  = (
        "endpoint",
        "event_type",
        "active_badge",
        "created_at",
    )
    list_filter   = ("is_active", "event_type")
    search_fields = ("endpoint__label", "endpoint__target_url", "event_type")
    readonly_fields = ("id", "created_at", "updated_at")
    actions       = ["activate_subscriptions", "deactivate_subscriptions"]

    def active_badge(self, obj):
        if obj.is_active:
            return format_html(_badge("Active", "#28a745", "#fff"))
        return format_html(_badge("Inactive", "#6c757d", "#fff"))
    active_badge.short_description = "Active"

    @admin.action(description="✅ Activate selected subscriptions")
    def activate_subscriptions(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Subscriptions activated.", messages.SUCCESS)

    @admin.action(description="❌ Deactivate selected subscriptions")
    def deactivate_subscriptions(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Subscriptions deactivated.", messages.WARNING)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK DELIVERY LOG ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    """
    Ainul Enterprise Engine — Delivery Log Admin with retry actions,
    color-coded status badges, and full audit trail visibility.
    """

    list_display = (
        "delivery_id_short",
        "endpoint_label",
        "event_type",
        "colored_status",
        "http_badge",
        "attempt_number",
        "response_time_ms",
        "dispatched_at",
    )
    list_filter  = ("status", "event_type", "http_status_code", "created_at")
    search_fields = (
        "delivery_id",
        "endpoint__label",
        "endpoint__target_url",
        "event_type",
        "error_message",
    )
    readonly_fields = (
        "id",
        "delivery_id",
        "endpoint",
        "event_type",
        "status",
        "payload_pretty",
        "request_headers",
        "signature",
        "http_status_code",
        "response_body",
        "response_time_ms",
        "error_message",
        "attempt_number",
        "max_attempts",
        "next_retry_at",
        "dispatched_at",
        "completed_at",
        "created_at",
    )
    fieldsets = (
        ("📦 Delivery Identity", {
            "fields": ("id", "delivery_id", "endpoint", "event_type"),
        }),
        ("📊 Status", {
            "fields": ("status", "attempt_number", "max_attempts", "next_retry_at"),
        }),
        ("📤 Request", {
            "fields": ("payload_pretty", "request_headers", "signature"),
            "classes": ("collapse",),
        }),
        ("📥 Response", {
            "fields": (
                "http_status_code", "response_body",
                "response_time_ms", "error_message",
            ),
        }),
        ("🕒 Timeline", {
            "fields": ("dispatched_at", "completed_at", "created_at"),
        }),
    )
    actions = ["action_retry_failed", "action_cancel_retrying"]
    ordering = ["-created_at"]
    list_per_page = 50

    # ── Display helpers ───────────────────────────────────────────────────────

    def colored_status(self, obj):
        return format_html(_delivery_badge(obj.status))
    colored_status.short_description = "Status"
    colored_status.admin_order_field = "status"

    def delivery_id_short(self, obj):
        return str(obj.delivery_id)[:8] + "…"
    delivery_id_short.short_description = "Delivery ID"

    def endpoint_label(self, obj):
        return obj.endpoint.label
    endpoint_label.short_description = "Endpoint"
    endpoint_label.admin_order_field = "endpoint__label"

    def http_badge(self, obj):
        code = obj.http_status_code
        if code is None:
            return format_html(_badge("N/A", "#6c757d", "#fff"))
        if 200 <= code < 300:
            return format_html(_badge(str(code), "#28a745", "#fff"))
        if 400 <= code < 500:
            return format_html(_badge(str(code), "#ffc107", "#000"))
        return format_html(_badge(str(code), "#dc3545", "#fff"))
    http_badge.short_description = "HTTP"
    http_badge.admin_order_field = "http_status_code"

    def payload_pretty(self, obj):
        import json
        try:
            pretty = json.dumps(obj.payload, indent=2, default=str)
            return format_html(
                '<pre style="font-size:12px;max-height:300px;overflow:auto;">{}</pre>',
                pretty,
            )
        except Exception:
            return str(obj.payload)
    payload_pretty.short_description = "Payload"

    # ── Bulk Actions ──────────────────────────────────────────────────────────

    @admin.action(description="🔁 Retry selected failed deliveries")
    def action_retry_failed(self, request, queryset):
        retried = 0
        skipped = 0
        for log in queryset.filter(
            status__in=[DeliveryStatus.FAILED, DeliveryStatus.RETRYING]
        ):
            if log.is_retryable:
                DispatchService.retry_delivery(log)
                retried += 1
            else:
                skipped += 1

        self.message_user(
            request,
            f"Queued {retried} retry(s). Skipped {skipped} (not retryable).",
            messages.SUCCESS if retried else messages.WARNING,
        )

    @admin.action(description="🚫 Cancel retrying deliveries")
    def action_cancel_retrying(self, request, queryset):
        updated = queryset.filter(status=DeliveryStatus.RETRYING).update(
            status=DeliveryStatus.CANCELLED
        )
        self.message_user(request, f"Cancelled {updated} retrying delivery(s).", messages.WARNING)


def _force_register_webhooks():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(WebhookEndpoint, WebhookEndpointAdmin), (WebhookSubscription, WebhookSubscriptionAdmin), (WebhookDeliveryLog, WebhookDeliveryLogAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] webhooks registered {registered} models")
    except Exception as e:
        print(f"[WARN] webhooks: {e}")
