# =============================================================================
# auto_mod/admin.py
# =============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot


class ProofScannerInline(admin.TabularInline):
    model         = ProofScanner
    extra         = 0
    max_num       = 10
    readonly_fields = [
        "scan_type", "confidence", "is_flagged",
        "labels", "ocr_text", "error_message",
        "duration_ms", "model_version", "created_at",
    ]
    can_delete    = False


@admin.register(AutoApprovalRule)
class AutoApprovalRuleAdmin(admin.ModelAdmin):
    list_display  = [
        "name", "submission_type", "priority", "action_badge",
        "confidence_threshold", "is_active", "is_system", "condition_count_display",
    ]
    list_filter   = ["submission_type", "action", "is_active", "is_system"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "condition_count_display"]
    ordering      = ["priority"]

    fieldsets = [
        (_("Identity"),  {"fields": ["id", "name", "description", "is_system"]}),
        (_("Rule"),      {"fields": ["submission_type", "priority", "conditions", "action", "confidence_threshold"]}),
        (_("Status"),    {"fields": ["is_active", "created_by", "metadata"]}),
        (_("Timestamps"),{"fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="Action")
    def action_badge(self, obj: AutoApprovalRule) -> str:
        color = {
            "approve":      "#27ae60",
            "reject":       "#e74c3c",
            "flag":         "#f39c12",
            "escalate":     "#8e44ad",
            "notify_admin": "#2980b9",
        }.get(obj.action, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.action.upper(),
        )

    @admin.display(description="Conditions")
    def condition_count_display(self, obj: AutoApprovalRule) -> str:
        return f"{obj.condition_count} condition(s)"


@admin.register(SuspiciousSubmission)
class SuspiciousSubmissionAdmin(admin.ModelAdmin):
    list_display  = [
        "content_id_short", "submission_type", "status_badge",
        "risk_badge", "ai_confidence", "flag_reason",
        "submitted_by", "created_at",
    ]
    list_filter   = ["status", "risk_level", "submission_type", "flag_reason"]
    search_fields = ["content_id", "content_type", "ai_explanation"]
    raw_id_fields = ["submitted_by", "reviewed_by", "escalated_to", "matched_rule"]
    readonly_fields = [
        "id", "ai_confidence", "risk_score", "ai_explanation",
        "scan_metadata", "created_at", "updated_at",
    ]
    date_hierarchy = "created_at"
    inlines        = [ProofScannerInline]

    @admin.display(description="Content ID")
    def content_id_short(self, obj: SuspiciousSubmission) -> str:
        return obj.content_id[:16] + "…" if len(obj.content_id) > 16 else obj.content_id

    @admin.display(description="Status")
    def status_badge(self, obj: SuspiciousSubmission) -> str:
        color = {
            "pending":        "#95a5a6",
            "scanning":       "#3498db",
            "auto_approved":  "#27ae60",
            "auto_rejected":  "#e74c3c",
            "human_review":   "#f39c12",
            "human_approved": "#2ecc71",
            "human_rejected": "#c0392b",
            "escalated":      "#8e44ad",
            "expired":        "#bdc3c7",
        }.get(obj.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description="Risk")
    def risk_badge(self, obj: SuspiciousSubmission) -> str:
        color = {
            "low":      "#27ae60",
            "medium":   "#f39c12",
            "high":     "#e74c3c",
            "critical": "#8e44ad",
        }.get(obj.risk_level, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.risk_level.upper(),
        )


@admin.register(ProofScanner)
class ProofScannerAdmin(admin.ModelAdmin):
    list_display  = [
        "id_short", "submission", "scan_type",
        "confidence", "is_flagged", "duration_ms", "model_version",
    ]
    list_filter   = ["scan_type", "is_flagged"]
    readonly_fields = [
        "id", "submission", "scan_type", "confidence",
        "is_flagged", "labels", "ocr_text", "raw_result",
        "error_message", "duration_ms", "model_version", "created_at",
    ]

    @admin.display(description="ID")
    def id_short(self, obj: ProofScanner) -> str:
        return str(obj.pk)[:8] + "…"


@admin.register(TaskBot)
class TaskBotAdmin(admin.ModelAdmin):
    list_display  = [
        "name", "submission_type", "status_badge",
        "total_processed", "approval_rate_display",
        "is_healthy_display", "last_heartbeat",
    ]
    list_filter   = ["status", "submission_type"]
    search_fields = ["name"]
    readonly_fields = [
        "id", "status",
        "total_processed", "total_approved",
        "total_rejected", "total_escalated", "total_errors",
        "last_heartbeat", "last_error", "retry_count",
        "created_at", "updated_at",
    ]

    @admin.display(description="Status")
    def status_badge(self, obj: TaskBot) -> str:
        color = {
            "idle":     "#3498db",
            "running":  "#27ae60",
            "paused":   "#f39c12",
            "error":    "#e74c3c",
            "disabled": "#bdc3c7",
        }.get(obj.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description="Approval Rate", boolean=False)
    def approval_rate_display(self, obj: TaskBot) -> str:
        return f"{obj.approval_rate:.1f}%"

    @admin.display(description="Healthy?", boolean=True)
    def is_healthy_display(self, obj: TaskBot) -> bool:
        return obj.is_healthy


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
