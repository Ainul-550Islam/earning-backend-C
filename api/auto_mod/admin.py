# =============================================================================
# auto_mod/admin.py
# =============================================================================

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    AutoApprovalRule, ContentSignal, MLModelVersion, 
    ModerationAppeal, ModerationDecision, ModerationQueue, 
    ProofScanner, SuspiciousSubmission, TaskBot
)


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


class ModerationDecisionInline(admin.TabularInline):
    model = ModerationDecision
    extra = 0
    max_num = 5
    readonly_fields = [
        "decision_type", "confidence", "decided_by",
        "decided_at", "is_automated", "applied_rule"
    ]
    can_delete = False


class ContentSignalInline(admin.TabularInline):
    model = ContentSignal
    extra = 0
    max_num = 10
    readonly_fields = [
        "signal_type", "value", "weight", "confidence",
        "source", "is_positive", "severity", "created_at"
    ]
    can_delete = False


class ModerationAppealInline(admin.TabularInline):
    model = ModerationAppeal
    extra = 0
    max_num = 3
    readonly_fields = [
        "user", "reason", "status", "reviewed_by",
        "reviewed_at", "final_decision"
    ]
    can_delete = False


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
    inlines        = [ProofScannerInline, ModerationDecisionInline, ContentSignalInline]

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


@admin.register(ModerationQueue)
class ModerationQueueAdmin(admin.ModelAdmin):
    list_display = [
        "submission_link", "priority_badge", "assigned_to_display",
        "queued_at", "due_at", "escalation_level", "is_overdue_display"
    ]
    list_filter = [
        "priority", "assigned_to", "escalation_level", "queued_at"
    ]
    search_fields = [
        "submission__content_id", "submission__content_type",
        "processing_notes"
    ]
    raw_id_fields = ["submission", "assigned_to"]
    readonly_fields = [
        "id", "submission", "queued_at", "processing_time_elapsed",
        "is_overdue_display", "should_auto_escalate_display"
    ]
    date_hierarchy = "queued_at"
    
    fieldsets = [
        (_("Queue Item"), {
            "fields": ["id", "submission", "priority", "assigned_to", "assigned_at"]
        }),
        (_("Timing"), {
            "fields": ["queued_at", "due_at", "estimated_processing_time", "auto_escalate_at"]
        }),
        (_("Escalation"), {
            "fields": ["escalation_level", "processing_notes"]
        }),
        (_("Metadata"), {
            "fields": ["metadata"]
        })
    ]

    @admin.display(description="Submission")
    def submission_link(self, obj: ModerationQueue) -> str:
        if obj.submission:
            return format_html(
                '<a href="/admin/auto_mod/suspicioussubmission/{}/">{}</a>',
                obj.submission.pk,
                obj.submission.content_id[:16] + "…"
            )
        return "—"

    @admin.display(description="Priority")
    def priority_badge(self, obj: ModerationQueue) -> str:
        colors = {
            "low": "#27ae60", "medium": "#f39c12", "high": "#e67e22",
            "urgent": "#e74c3c", "critical": "#8e44ad"
        }
        color = colors.get(obj.priority, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.priority.upper()
        )

    @admin.display(description="Assigned To")
    def assigned_to_display(self, obj: ModerationQueue) -> str:
        return obj.assigned_to.username if obj.assigned_to else "Unassigned"

    @admin.display(description="Overdue?", boolean=True)
    def is_overdue_display(self, obj: ModerationQueue) -> bool:
        return obj.is_overdue

    @admin.display(description="Should Escalate?", boolean=True)
    def should_auto_escalate_display(self, obj: ModerationQueue) -> bool:
        return obj.should_auto_escalate


@admin.register(ModerationDecision)
class ModerationDecisionAdmin(admin.ModelAdmin):
    list_display = [
        "submission_link", "decision_type_badge", "decider_display",
        "confidence", "is_automated_display", "decided_at"
    ]
    list_filter = [
        "decision_type", "is_automated", "decided_by", "decided_at"
    ]
    search_fields = [
        "submission__content_id", "reason", "reviewer_notes"
    ]
    raw_id_fields = ["submission", "decided_by", "applied_rule", "previous_decision"]
    readonly_fields = [
        "id", "submission", "decided_at", "is_final_display",
        "requires_follow_up_display"
    ]
    date_hierarchy = "decided_at"
    inlines = [ModerationAppealInline]
    
    fieldsets = [
        (_("Decision"), {
            "fields": ["id", "submission", "decision_type", "reason", "confidence"]
        }),
        (_("Decider"), {
            "fields": ["decided_by", "is_automated", "applied_rule", "previous_decision"]
        }),
        (_("Details"), {
            "fields": ["decision_data", "reviewer_notes"]
        }),
        (_("Metadata"), {
            "fields": ["metadata"]
        })
    ]

    @admin.display(description="Submission")
    def submission_link(self, obj: ModerationDecision) -> str:
        if obj.submission:
            return format_html(
                '<a href="/admin/auto_mod/suspicioussubmission/{}/">{}</a>',
                obj.submission.pk,
                obj.submission.content_id[:16] + "…"
            )
        return "—"

    @admin.display(description="Decision")
    def decision_type_badge(self, obj: ModerationDecision) -> str:
        colors = {
            "approve": "#27ae60", "reject": "#e74c3c",
            "escalate": "#8e44ad", "request_info": "#3498db"
        }
        color = colors.get(obj.decision_type, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.decision_type.replace("_", " ").upper()
        )

    @admin.display(description="Decider")
    def decider_display(self, obj: ModerationDecision) -> str:
        if obj.is_automated:
            return '<span style="color:#3498db;font-weight:bold">AI</span>'
        return obj.decided_by.username if obj.decided_by else "Unknown"

    @admin.display(description="Automated?", boolean=True)
    def is_automated_display(self, obj: ModerationDecision) -> bool:
        return obj.is_automated

    @admin.display(description="Final?", boolean=True)
    def is_final_display(self, obj: ModerationDecision) -> bool:
        return obj.is_final

    @admin.display(description="Follow-up?", boolean=True)
    def requires_follow_up_display(self, obj: ModerationDecision) -> bool:
        return obj.requires_follow_up


@admin.register(ModerationAppeal)
class ModerationAppealAdmin(admin.ModelAdmin):
    list_display = [
        "submission_link", "user_link", "status_badge",
        "original_decision_link", "reviewed_by_display", "created_at"
    ]
    list_filter = [
        "status", "reviewed_by", "created_at", "reviewed_at"
    ]
    search_fields = [
        "submission__content_id", "user__username", "reason",
        "review_notes", "final_reason"
    ]
    raw_id_fields = [
        "submission", "user", "original_decision", "reviewed_by"
    ]
    readonly_fields = [
        "id", "submission", "user", "original_decision",
        "created_at", "is_pending_review_display", "is_resolved_display",
        "was_successful_display"
    ]
    date_hierarchy = "created_at"
    
    fieldsets = [
        (_("Appeal"), {
            "fields": ["id", "submission", "user", "original_decision", "reason"]
        }),
        (_("Review"), {
            "fields": ["status", "reviewed_by", "reviewed_at", "review_notes"]
        }),
        (_("Resolution"), {
            "fields": ["final_decision", "final_reason"]
        }),
        (_("Data"), {
            "fields": ["appeal_data", "metadata"]
        })
    ]

    @admin.display(description="Submission")
    def submission_link(self, obj: ModerationAppeal) -> str:
        if obj.submission:
            return format_html(
                '<a href="/admin/auto_mod/suspicioussubmission/{}/">{}</a>',
                obj.submission.pk,
                obj.submission.content_id[:16] + "…"
            )
        return "—"

    @admin.display(description="User")
    def user_link(self, obj: ModerationAppeal) -> str:
        if obj.user:
            return format_html(
                '<a href="/admin/auth/user/{}/">{}</a>',
                obj.user.pk,
                obj.user.username
            )
        return "—"

    @admin.display(description="Status")
    def status_badge(self, obj: ModerationAppeal) -> str:
        colors = {
            "pending": "#95a5a6", "under_review": "#3498db",
            "approved": "#27ae60", "rejected": "#e74c3c", "closed": "#bdc3c7"
        }
        color = colors.get(obj.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.status.replace("_", " ").upper()
        )

    @admin.display(description="Original Decision")
    def original_decision_link(self, obj: ModerationAppeal) -> str:
        if obj.original_decision:
            return format_html(
                '<a href="/admin/auto_mod/moderationdecision/{}">{}</a>',
                obj.original_decision.pk,
                obj.original_decision.decision_type.upper()
            )
        return "—"

    @admin.display(description="Reviewed By")
    def reviewed_by_display(self, obj: ModerationAppeal) -> str:
        return obj.reviewed_by.username if obj.reviewed_by else "Not reviewed"

    @admin.display(description="Pending Review?", boolean=True)
    def is_pending_review_display(self, obj: ModerationAppeal) -> bool:
        return obj.is_pending_review

    @admin.display(description="Resolved?", boolean=True)
    def is_resolved_display(self, obj: ModerationAppeal) -> bool:
        return obj.is_resolved

    @admin.display(description="Successful?", boolean=True)
    def was_successful_display(self, obj: ModerationAppeal) -> bool:
        return obj.was_successful


@admin.register(MLModelVersion)
class MLModelVersionAdmin(admin.ModelAdmin):
    list_display = [
        "model_type_badge", "version", "display_name",
        "status_badge", "is_active_display", "accuracy_display",
        "deployed_at", "created_by_display"
    ]
    list_filter = [
        "model_type", "status", "is_active", "deployed_at", "created_at"
    ]
    search_fields = [
        "version", "display_name", "description", "file_path"
    ]
    raw_id_fields = ["created_by"]
    readonly_fields = [
        "id", "model_type", "version", "file_size_mb", "checksum",
        "performance_summary_display", "is_deployed_display",
        "created_at", "updated_at"
    ]
    date_hierarchy = "created_at"
    
    fieldsets = [
        (_("Model Info"), {
            "fields": ["id", "model_type", "version", "display_name", "description"]
        }),
        (_("File"), {
            "fields": ["file_path", "file_size_mb", "checksum"]
        }),
        (_("Performance"), {
            "fields": [
                "accuracy", "precision", "recall", "f1_score", "auc_score"
            ]
        }),
        (_("Training"), {
            "fields": [
                "training_data_version", "training_samples", "validation_samples",
                "training_duration_hours", "hyperparameters", "feature_importance"
            ]
        }),
        (_("Deployment"), {
            "fields": ["status", "is_active", "deployed_at", "deployment_config"]
        }),
        (_("Details"), {
            "fields": ["training_log", "created_by", "metadata"]
        })
    ]

    @admin.display(description="Model Type")
    def model_type_badge(self, obj: MLModelVersion) -> str:
        colors = {
            "text": "#3498db", "image": "#27ae60", "ocr": "#f39c12", "combined": "#8e44ad"
        }
        color = colors.get(obj.model_type, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.model_type.upper()
        )

    @admin.display(description="Status")
    def status_badge(self, obj: MLModelVersion) -> str:
        colors = {
            "idle": "#95a5a6", "training": "#3498db", "validating": "#f39c12",
            "deployed": "#27ae60", "failed": "#e74c3c"
        }
        color = colors.get(obj.status, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.status.upper()
        )

    @admin.display(description="Active?", boolean=True)
    def is_active_display(self, obj: MLModelVersion) -> bool:
        return obj.is_active

    @admin.display(description="Accuracy")
    def accuracy_display(self, obj: MLModelVersion) -> str:
        if obj.accuracy is not None:
            return f"{obj.accuracy:.3f}"
        return "—"

    @admin.display(description="Deployed?", boolean=True)
    def is_deployed_display(self, obj: MLModelVersion) -> bool:
        return obj.is_deployed

    @admin.display(description="Performance Summary")
    def performance_summary_display(self, obj: MLModelVersion) -> str:
        summary = obj.performance_summary
        metrics = []
        for key, value in summary.items():
            if value is not None:
                metrics.append(f"{key}: {value:.3f}")
        return ", ".join(metrics) if metrics else "No metrics"

    @admin.display(description="Created By")
    def created_by_display(self, obj: MLModelVersion) -> str:
        return obj.created_by.username if obj.created_by else "System"


@admin.register(ContentSignal)
class ContentSignalAdmin(admin.ModelAdmin):
    list_display = [
        "submission_link", "signal_type_badge", "value_short",
        "weight_confidence_display", "is_positive_display", "severity_badge",
        "processed_display", "created_at"
    ]
    list_filter = [
        "signal_type", "is_positive", "severity", "processed", "created_at"
    ]
    search_fields = [
        "submission__content_id", "value", "source"
    ]
    raw_id_fields = ["submission"]
    readonly_fields = [
        "id", "submission", "impact_score_display", "created_at", "updated_at"
    ]
    date_hierarchy = "created_at"
    
    fieldsets = [
        (_("Signal"), {
            "fields": ["id", "submission", "signal_type", "value", "weight", "confidence"]
        }),
        (_("Classification"), {
            "fields": ["is_positive", "severity", "source"]
        }),
        (_("Processing"), {
            "fields": ["processed", "processed_at"]
        }),
        (_("Data"), {
            "fields": ["metadata"]
        })
    ]

    @admin.display(description="Submission")
    def submission_link(self, obj: ContentSignal) -> str:
        if obj.submission:
            return format_html(
                '<a href="/admin/auto_mod/suspicioussubmission/{}/">{}</a>',
                obj.submission.pk,
                obj.submission.content_id[:16] + "…"
            )
        return "—"

    @admin.display(description="Signal Type")
    def signal_type_badge(self, obj: ContentSignal) -> str:
        colors = {
            "user_report": "#3498db", "ai_detection": "#27ae60",
            "pattern_match": "#f39c12", "manual_flag": "#e74c3c",
            "system_alert": "#8e44ad", "content_analysis": "#16a085"
        }
        color = colors.get(obj.signal_type, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.signal_type.replace("_", " ").title()
        )

    @admin.display(description="Value")
    def value_short(self, obj: ContentSignal) -> str:
        return obj.value[:30] + "…" if len(obj.value) > 30 else obj.value

    @admin.display(description="Weight/Confidence")
    def weight_confidence_display(self, obj: ContentSignal) -> str:
        parts = [f"w:{obj.weight}"]
        if obj.confidence is not None:
            parts.append(f"c:{obj.confidence:.2f}")
        return " ".join(parts)

    @admin.display(description="Positive?", boolean=True)
    def is_positive_display(self, obj: ContentSignal) -> bool:
        return obj.is_positive

    @admin.display(description="Severity")
    def severity_badge(self, obj: ContentSignal) -> str:
        colors = {
            "low": "#27ae60", "medium": "#f39c12", "high": "#e74c3c", "critical": "#8e44ad"
        }
        color = colors.get(obj.severity, "#999")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.severity.upper()
        )

    @admin.display(description="Processed?", boolean=True)
    def processed_display(self, obj: ContentSignal) -> bool:
        return obj.processed

    @admin.display(description="Impact Score")
    def impact_score_display(self, obj: ContentSignal) -> str:
        return f"{obj.impact_score:.2f}"


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass


def _force_register_auto_mod():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
    (AutoApprovalRule, AutoApprovalRuleAdmin), 
    (SuspiciousSubmission, SuspiciousSubmissionAdmin), 
    (ProofScanner, ProofScannerAdmin), 
    (TaskBot, TaskBotAdmin),
    (ModerationQueue, ModerationQueueAdmin),
    (ModerationDecision, ModerationDecisionAdmin),
    (ModerationAppeal, ModerationAppealAdmin),
    (MLModelVersion, MLModelVersionAdmin),
    (ContentSignal, ContentSignalAdmin)
]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] auto_mod registered {registered} models")
    except Exception as e:
        print(f"[WARN] auto_mod: {e}")


# =============================================================================
# Compliance model admin
# =============================================================================

from .models import (
    ModerationRule, ModerationAction, ModerationLog,
    ContentFlag, AutoModerationQueue, ModerationStats,
)


@admin.register(ModerationRule)
class ModerationRuleAdmin(admin.ModelAdmin):
    list_display   = ('name', 'rule_type', 'action', 'severity', 'is_active', 'created_at')
    list_filter    = ('rule_type', 'action', 'severity', 'is_active', 'automated')
    search_fields  = ('name', 'rule_type')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display   = ('action_type', 'content_id', 'moderator', 'automated', 'created_at')
    list_filter    = ('action_type', 'automated', 'human_reviewed')
    search_fields  = ('content_id', 'reason')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display   = ('action', 'content_id', 'moderator', 'automated', 'created_at')
    list_filter    = ('action', 'automated')
    search_fields  = ('content_id', 'reason')
    readonly_fields = ('created_at',)


@admin.register(ContentFlag)
class ContentFlagAdmin(admin.ModelAdmin):
    list_display   = ('flag_type', 'content_id', 'user', 'status', 'created_at')
    list_filter    = ('flag_type', 'status')
    search_fields  = ('content_id', 'reason')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AutoModerationQueue)
class AutoModerationQueueAdmin(admin.ModelAdmin):
    list_display   = ('content_id', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter    = ('status',)
    search_fields  = ('content_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ModerationStats)
class ModerationStatsAdmin(admin.ModelAdmin):
    list_display   = ('period_start', 'period_end', 'total_actions', 'auto_actions',
                       'human_actions', 'appeals_filed')
    readonly_fields = ('created_at',)


# =============================================================================
# Offerwall / Monlix admin
# =============================================================================
from .offerwall import (
    VirtualCurrencyConfig, OfferwallOfferType, OfferwallConfig,
    PostbackLog, SiteApproval, PerformanceReport,
    PaymentSchedule, OfferwallPromotion,
)


@admin.register(VirtualCurrencyConfig)
class VirtualCurrencyConfigAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'currency_name', 'currency_multiplier',
                     'award_on_completion', 'updated_at')
    search_fields = ('publisher_id', 'currency_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OfferwallOfferType)
class OfferwallOfferTypeAdmin(admin.ModelAdmin):
    list_display  = ('name', 'offer_type', 'publisher_id', 'payout_usd',
                     'is_active', 'os_target')
    list_filter   = ('offer_type', 'is_active', 'os_target')
    search_fields = ('name', 'publisher_id', 'advertiser_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OfferwallConfig)
class OfferwallConfigAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'theme', 'offer_sorting', 'is_active',
                     'approved_at')
    list_filter   = ('theme', 'is_active')
    search_fields = ('publisher_id',)
    readonly_fields = ('created_at', 'updated_at', 'approved_at', 'postback_secret')


@admin.register(PostbackLog)
class PostbackLogAdmin(admin.ModelAdmin):
    list_display  = ('transaction_id', 'publisher_id', 'user_id', 'reward_value',
                     'currency_awarded', 'status', 'received_at')
    list_filter   = ('status',)
    search_fields = ('transaction_id', 'publisher_id', 'user_id')
    readonly_fields = ('received_at', 'processed_at')


@admin.register(SiteApproval)
class SiteApprovalAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'site_url', 'status', 'submitted_at', 'reviewed_at')
    list_filter   = ('status',)
    search_fields = ('publisher_id', 'site_url')
    readonly_fields = ('submitted_at', 'reviewed_at')
    actions = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        from .offerwall import SiteApprovalService
        for obj in queryset.filter(status=SiteApproval.STATUS_PENDING):
            SiteApprovalService.approve(obj, request.user)
    approve_selected.short_description = "Approve selected sites"

    def reject_selected(self, request, queryset):
        from .offerwall import SiteApprovalService
        for obj in queryset.filter(status=SiteApproval.STATUS_PENDING):
            SiteApprovalService.reject(obj, request.user, "Bulk rejected via admin")
    reject_selected.short_description = "Reject selected sites"


@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'report_date', 'period', 'impressions',
                     'completions', 'revenue_usd', 'ecpm')
    list_filter   = ('period', 'report_date')
    search_fields = ('publisher_id',)
    readonly_fields = ('created_at',)


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display  = ('publisher_id', 'schedule_type', 'min_payout_usd',
                     'payout_method', 'is_active')
    list_filter   = ('schedule_type', 'payout_method', 'is_active')
    search_fields = ('publisher_id', 'payout_email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OfferwallPromotion)
class OfferwallPromotionAdmin(admin.ModelAdmin):
    list_display  = ('name', 'publisher_id', 'multiplier', 'starts_at',
                     'ends_at', 'promo_type', 'is_active', 'is_currently_active')
    list_filter   = ('promo_type', 'is_active')
    search_fields = ('name', 'publisher_id')
    readonly_fields = ('created_at',)
    list_editable = ('is_active',)

    def is_currently_active(self, obj):
        return obj.is_currently_active
    is_currently_active.boolean = True
    is_currently_active.short_description = "Active Now?"
