# =============================================================================
# auto_mod/filters.py
# =============================================================================

import django_filters

from .choices import (
    BotStatus,
    FlagReason,
    ModerationStatus,
    RiskLevel,
    RuleAction,
    ScanType,
    SubmissionType,
)
from .models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot


class AutoApprovalRuleFilter(django_filters.FilterSet):
    submission_type = django_filters.MultipleChoiceFilter(choices=SubmissionType.choices)
    action          = django_filters.MultipleChoiceFilter(choices=RuleAction.choices)
    is_active       = django_filters.BooleanFilter()
    is_system       = django_filters.BooleanFilter()
    name_contains   = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    created_after   = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before  = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    min_confidence  = django_filters.NumberFilter(
        field_name="confidence_threshold", lookup_expr="gte"
    )

    class Meta:
        model  = AutoApprovalRule
        fields = ["submission_type", "action", "is_active", "is_system"]


class SuspiciousSubmissionFilter(django_filters.FilterSet):
    status          = django_filters.MultipleChoiceFilter(choices=ModerationStatus.choices)
    risk_level      = django_filters.MultipleChoiceFilter(choices=RiskLevel.choices)
    flag_reason     = django_filters.MultipleChoiceFilter(choices=FlagReason.choices)
    submission_type = django_filters.MultipleChoiceFilter(choices=SubmissionType.choices)
    submitted_by    = django_filters.UUIDFilter(field_name="submitted_by__id")
    reviewed        = django_filters.BooleanFilter(
        method="filter_reviewed", label="Has been reviewed"
    )
    min_risk_score  = django_filters.NumberFilter(field_name="risk_score", lookup_expr="gte")
    max_risk_score  = django_filters.NumberFilter(field_name="risk_score", lookup_expr="lte")
    min_confidence  = django_filters.NumberFilter(field_name="ai_confidence", lookup_expr="gte")
    created_after   = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before  = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    content_type    = django_filters.CharFilter(lookup_expr="exact")

    class Meta:
        model  = SuspiciousSubmission
        fields = ["status", "risk_level", "flag_reason", "submission_type"]

    def filter_reviewed(self, queryset, name, value):
        if value:
            return queryset.filter(reviewed_by__isnull=False)
        return queryset.filter(reviewed_by__isnull=True)


class ProofScannerFilter(django_filters.FilterSet):
    scan_type   = django_filters.MultipleChoiceFilter(choices=ScanType.choices)
    is_flagged  = django_filters.BooleanFilter()
    has_error   = django_filters.BooleanFilter(method="filter_has_error")
    min_conf    = django_filters.NumberFilter(field_name="confidence", lookup_expr="gte")

    class Meta:
        model  = ProofScanner
        fields = ["scan_type", "is_flagged"]

    def filter_has_error(self, queryset, name, value):
        if value:
            return queryset.exclude(error_message="")
        return queryset.filter(error_message="")


class TaskBotFilter(django_filters.FilterSet):
    status          = django_filters.MultipleChoiceFilter(choices=BotStatus.choices)
    submission_type = django_filters.MultipleChoiceFilter(choices=SubmissionType.choices)
    is_healthy      = django_filters.BooleanFilter(method="filter_healthy")

    class Meta:
        model  = TaskBot
        fields = ["status", "submission_type"]

    def filter_healthy(self, queryset, name, value):
        from django.utils import timezone
        from datetime import timedelta
        from .constants import BOT_HEARTBEAT_INTERVAL_SEC
        cutoff = timezone.now() - timedelta(seconds=BOT_HEARTBEAT_INTERVAL_SEC * 3)
        if value:
            return queryset.filter(last_heartbeat__gte=cutoff)
        return queryset.filter(last_heartbeat__lt=cutoff) | queryset.filter(last_heartbeat__isnull=True)
