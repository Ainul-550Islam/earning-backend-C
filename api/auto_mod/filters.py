# =============================================================================
# auto_mod/filters.py
# =============================================================================

import django_filters

from django.db import models

from .choices import (
    AppealStatus, BotStatus, DecisionType, FlagReason, ModelTrainingStatus, ModelType,
    ModerationStatus, QueuePriority, RiskLevel, RuleAction, ScanType, SignalType, SubmissionType,
)
from .models import (
    AutoApprovalRule, ContentSignal, MLModelVersion, 
    ModerationAppeal, ModerationDecision, ModerationQueue, 
    ProofScanner, SuspiciousSubmission, TaskBot
)


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


# =============================================================================
# New Filter Classes for Enhanced Moderation System
# =============================================================================

class ModerationQueueFilter(django_filters.FilterSet):
    """Filter for ModerationQueue model."""
    priority = django_filters.MultipleChoiceFilter(choices=QueuePriority.choices)
    assigned_to = django_filters.UUIDFilter(field_name="assigned_to__id")
    is_assigned = django_filters.BooleanFilter(method="filter_assigned")
    is_overdue = django_filters.BooleanFilter(method="filter_overdue")
    should_escalate = django_filters.BooleanFilter(method="filter_should_escalate")
    escalation_level = django_filters.NumberFilter(field_name="escalation_level", lookup_expr="gte")
    queued_after = django_filters.IsoDateTimeFilter(field_name="queued_at", lookup_expr="gte")
    queued_before = django_filters.IsoDateTimeFilter(field_name="queued_at", lookup_expr="lte")
    due_after = django_filters.IsoDateTimeFilter(field_name="due_at", lookup_expr="gte")
    due_before = django_filters.IsoDateTimeFilter(field_name="due_at", lookup_expr="lte")
    submission_type = django_filters.MultipleChoiceFilter(
        field_name="submission__submission_type", 
        choices=SubmissionType.choices
    )

    class Meta:
        model = ModerationQueue
        fields = ["priority", "assigned_to", "escalation_level"]

    def filter_assigned(self, queryset, name, value):
        if value:
            return queryset.filter(assigned_to__isnull=False)
        return queryset.filter(assigned_to__isnull=True)

    def filter_overdue(self, queryset, name, value):
        from django.utils import timezone
        if value:
            return queryset.filter(due_at__lt=timezone.now())
        return queryset.filter(
            models.Q(due_at__gte=timezone.now()) | models.Q(due_at__isnull=True)
        )

    def filter_should_escalate(self, queryset, name, value):
        from django.utils import timezone
        if value:
            return queryset.filter(auto_escalate_at__lt=timezone.now())
        return queryset.filter(
            models.Q(auto_escalate_at__gte=timezone.now()) | models.Q(auto_escalate_at__isnull=True)
        )


class ModerationDecisionFilter(django_filters.FilterSet):
    """Filter for ModerationDecision model."""
    decision_type = django_filters.MultipleChoiceFilter(choices=DecisionType.choices)
    is_automated = django_filters.BooleanFilter()
    decided_by = django_filters.UUIDFilter(field_name="decided_by__id")
    is_final = django_filters.BooleanFilter(method="filter_is_final")
    requires_follow_up = django_filters.BooleanFilter(method="filter_requires_follow_up")
    min_confidence = django_filters.NumberFilter(field_name="confidence", lookup_expr="gte")
    max_confidence = django_filters.NumberFilter(field_name="confidence", lookup_expr="lte")
    decided_after = django_filters.IsoDateTimeFilter(field_name="decided_at", lookup_expr="gte")
    decided_before = django_filters.IsoDateTimeFilter(field_name="decided_at", lookup_expr="lte")
    submission_type = django_filters.MultipleChoiceFilter(
        field_name="submission__submission_type", 
        choices=SubmissionType.choices
    )
    applied_rule = django_filters.UUIDFilter(field_name="applied_rule__id")

    class Meta:
        model = ModerationDecision
        fields = ["decision_type", "is_automated", "decided_by"]

    def filter_is_final(self, queryset, name, value):
        if value:
            return queryset.filter(decision_type__in=["approve", "reject"])
        return queryset.exclude(decision_type__in=["approve", "reject"])

    def filter_requires_follow_up(self, queryset, name, value):
        if value:
            return queryset.filter(decision_type__in=["escalate", "request_info"])
        return queryset.exclude(decision_type__in=["escalate", "request_info"])


class ModerationAppealFilter(django_filters.FilterSet):
    """Filter for ModerationAppeal model."""
    status = django_filters.MultipleChoiceFilter(choices=AppealStatus.choices)
    user = django_filters.UUIDFilter(field_name="user__id")
    reviewed_by = django_filters.UUIDFilter(field_name="reviewed_by__id")
    is_pending_review = django_filters.BooleanFilter(method="filter_is_pending_review")
    is_resolved = django_filters.BooleanFilter(method="filter_is_resolved")
    was_successful = django_filters.BooleanFilter(method="filter_was_successful")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    reviewed_after = django_filters.IsoDateTimeFilter(field_name="reviewed_at", lookup_expr="gte")
    reviewed_before = django_filters.IsoDateTimeFilter(field_name="reviewed_at", lookup_expr="lte")
    submission_type = django_filters.MultipleChoiceFilter(
        field_name="submission__submission_type", 
        choices=SubmissionType.choices
    )
    original_decision_type = django_filters.MultipleChoiceFilter(
        field_name="original_decision__decision_type", 
        choices=DecisionType.choices
    )

    class Meta:
        model = ModerationAppeal
        fields = ["status", "user", "reviewed_by"]

    def filter_is_pending_review(self, queryset, name, value):
        if value:
            return queryset.filter(status__in=["pending", "under_review"])
        return queryset.exclude(status__in=["pending", "under_review"])

    def filter_is_resolved(self, queryset, name, value):
        if value:
            return queryset.filter(status__in=["approved", "rejected", "closed"])
        return queryset.exclude(status__in=["approved", "rejected", "closed"])

    def filter_was_successful(self, queryset, name, value):
        if value:
            return queryset.filter(status="approved")
        return queryset.exclude(status="approved")


class MLModelVersionFilter(django_filters.FilterSet):
    """Filter for MLModelVersion model."""
    model_type = django_filters.MultipleChoiceFilter(choices=ModelType.choices)
    status = django_filters.MultipleChoiceFilter(choices=ModelTrainingStatus.choices)
    is_active = django_filters.BooleanFilter()
    is_deployed = django_filters.BooleanFilter(method="filter_is_deployed")
    min_accuracy = django_filters.NumberFilter(field_name="accuracy", lookup_expr="gte")
    max_accuracy = django_filters.NumberFilter(field_name="accuracy", lookup_expr="lte")
    min_precision = django_filters.NumberFilter(field_name="precision", lookup_expr="gte")
    max_precision = django_filters.NumberFilter(field_name="precision", lookup_expr="lte")
    min_recall = django_filters.NumberFilter(field_name="recall", lookup_expr="gte")
    max_recall = django_filters.NumberFilter(field_name="recall", lookup_expr="lte")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    deployed_after = django_filters.IsoDateTimeFilter(field_name="deployed_at", lookup_expr="gte")
    deployed_before = django_filters.IsoDateTimeFilter(field_name="deployed_at", lookup_expr="lte")
    created_by = django_filters.UUIDFilter(field_name="created_by__id")
    version_contains = django_filters.CharFilter(field_name="version", lookup_expr="icontains")
    display_name_contains = django_filters.CharFilter(field_name="display_name", lookup_expr="icontains")

    class Meta:
        model = MLModelVersion
        fields = ["model_type", "status", "is_active"]

    def filter_is_deployed(self, queryset, name, value):
        if value:
            return queryset.exclude(deployed_at__isnull=True)
        return queryset.filter(deployed_at__isnull=True)


class ContentSignalFilter(django_filters.FilterSet):
    """Filter for ContentSignal model."""
    signal_type = django_filters.MultipleChoiceFilter(choices=SignalType.choices)
    is_positive = django_filters.BooleanFilter()
    is_processed = django_filters.BooleanFilter()
    severity = django_filters.MultipleChoiceFilter(choices=RiskLevel.choices)
    source = django_filters.CharFilter(lookup_expr="icontains")
    min_weight = django_filters.NumberFilter(field_name="weight", lookup_expr="gte")
    max_weight = django_filters.NumberFilter(field_name="weight", lookup_expr="lte")
    min_confidence = django_filters.NumberFilter(field_name="confidence", lookup_expr="gte")
    max_confidence = django_filters.NumberFilter(field_name="confidence", lookup_expr="lte")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    processed_after = django_filters.IsoDateTimeFilter(field_name="processed_at", lookup_expr="gte")
    processed_before = django_filters.IsoDateTimeFilter(field_name="processed_at", lookup_expr="lte")
    submission_type = django_filters.MultipleChoiceFilter(
        field_name="submission__submission_type", 
        choices=SubmissionType.choices
    )
    value_contains = django_filters.CharFilter(field_name="value", lookup_expr="icontains")

    class Meta:
        model = ContentSignal
        fields = ["signal_type", "is_positive", "severity", "is_processed"]

    def filter_queryset(self, queryset):
        """Custom queryset filtering for impact score."""
        queryset = super().filter_queryset(queryset)
        
        # Add custom filtering for impact score if provided
        min_impact = self.data.get('min_impact')
        max_impact = self.data.get('max_impact')
        
        if min_impact:
            # Filter by calculated impact score (weight * confidence * severity multiplier)
            from django.db.models import F, Case, When
            severity_multipliers = Case(
                When(severity='low', then=1.0),
                When(severity='medium', then=1.5),
                When(severity='high', then=2.0),
                When(severity='critical', then=3.0),
                default=1.0,
            )
            queryset = queryset.annotate(
                impact_score=F('weight') * F('confidence') * severity_multipliers
            ).filter(impact_score__gte=float(min_impact))
        
        if max_impact:
            from django.db.models import F, Case, When
            severity_multipliers = Case(
                When(severity='low', then=1.0),
                When(severity='medium', then=1.5),
                When(severity='high', then=2.0),
                When(severity='critical', then=3.0),
                default=1.0,
            )
            queryset = queryset.annotate(
                impact_score=F('weight') * F('confidence') * severity_multipliers
            ).filter(impact_score__lte=float(max_impact))
        
        return queryset
