# =============================================================================
# auto_mod/serializers.py
# =============================================================================

from __future__ import annotations

from rest_framework import serializers

from .choices import ModerationStatus, RuleAction, SubmissionType
from .constants import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    MAX_CONDITIONS_PER_RULE,
    RULE_PRIORITY_MAX,
    RULE_PRIORITY_MIN,
)
from .models import AutoApprovalRule, ProofScanner, SuspiciousSubmission, TaskBot
from .utils.ai_validator import validate_confidence, validate_labels


# ---------------------------------------------------------------------------
# AutoApprovalRule
# ---------------------------------------------------------------------------

class AutoApprovalRuleSerializer(serializers.ModelSerializer):
    condition_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = AutoApprovalRule
        fields = [
            "id", "name", "description", "submission_type",
            "priority", "conditions", "action",
            "confidence_threshold", "is_active", "is_system",
            "condition_count", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_system", "condition_count", "created_at", "updated_at"]

    def get_condition_count(self, obj: AutoApprovalRule) -> int:
        return obj.condition_count

    def validate_conditions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("conditions must be a JSON list.")
        if len(value) > MAX_CONDITIONS_PER_RULE:
            raise serializers.ValidationError(
                f"conditions may not exceed {MAX_CONDITIONS_PER_RULE} items."
            )
        required_keys = {"field", "operator", "value"}
        for i, cond in enumerate(value):
            if not isinstance(cond, dict):
                raise serializers.ValidationError(
                    f"conditions[{i}] must be an object."
                )
            missing = required_keys - cond.keys()
            if missing:
                raise serializers.ValidationError(
                    f"conditions[{i}] is missing keys: {missing}"
                )
        return value

    def validate_confidence_threshold(self, value):
        try:
            return validate_confidence(value, "confidence_threshold")
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

    def validate_priority(self, value):
        if not (RULE_PRIORITY_MIN <= value <= RULE_PRIORITY_MAX):
            raise serializers.ValidationError(
                f"Priority must be between {RULE_PRIORITY_MIN} and {RULE_PRIORITY_MAX}."
            )
        return value

    def validate(self, attrs):
        # System rules cannot be modified via API
        if self.instance and self.instance.is_system:
            raise serializers.ValidationError(
                "System rules cannot be modified via the API."
            )
        return attrs


class AutoApprovalRuleCreateSerializer(AutoApprovalRuleSerializer):
    class Meta(AutoApprovalRuleSerializer.Meta):
        read_only_fields = ["id", "is_system", "condition_count", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# ProofScanner (read-only inline)
# ---------------------------------------------------------------------------

class ProofScannerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProofScanner
        fields = [
            "id", "scan_type", "file_url",
            "confidence", "is_flagged", "labels",
            "ocr_text", "error_message",
            "duration_ms", "model_version",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# SuspiciousSubmission
# ---------------------------------------------------------------------------

class SuspiciousSubmissionSerializer(serializers.ModelSerializer):
    scans             = ProofScannerSerializer(many=True, read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name  = serializers.SerializerMethodField()
    is_resolved       = serializers.SerializerMethodField()

    class Meta:
        model  = SuspiciousSubmission
        fields = [
            "id", "content_type", "content_id",
            "submission_type", "status",
            "ai_confidence", "risk_score", "risk_level",
            "flag_reason", "ai_explanation",
            "matched_rule",
            "submitted_by", "submitted_by_name",
            "reviewed_by", "reviewed_by_name",
            "reviewed_at", "reviewer_note",
            "final_status", "escalated_to",
            "is_resolved", "scans",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "ai_confidence", "risk_score", "risk_level",
            "flag_reason", "ai_explanation", "matched_rule",
            "submitted_by_name", "reviewed_by_name",
            "is_resolved", "scans",
            "created_at", "updated_at",
        ]

    def get_submitted_by_name(self, obj: SuspiciousSubmission) -> str | None:
        u = obj.submitted_by
        return getattr(u, "get_full_name", lambda: None)() or str(u) if u else None

    def get_reviewed_by_name(self, obj: SuspiciousSubmission) -> str | None:
        u = obj.reviewed_by
        return str(u) if u else None

    def get_is_resolved(self, obj: SuspiciousSubmission) -> bool:
        return obj.is_resolved


class SuspiciousSubmissionCreateSerializer(serializers.Serializer):
    """
    Used when an external service submits content for moderation.
    """
    content_type    = serializers.CharField(max_length=100)
    content_id      = serializers.CharField(max_length=128)
    submission_type = serializers.ChoiceField(choices=SubmissionType.choices)
    text_content    = serializers.CharField(required=False, default="", allow_blank=True)
    file_urls       = serializers.ListField(
        child=serializers.URLField(max_length=2048),
        required=False,
        default=list,
        max_length=10,
    )
    metadata        = serializers.DictField(required=False, default=dict)

    def validate_file_urls(self, urls):
        from .utils.ai_validator import validate_file_url
        validated = []
        for url in urls:
            try:
                validated.append(validate_file_url(url))
            except Exception as exc:
                raise serializers.ValidationError(str(exc))
        return validated


class HumanReviewSerializer(serializers.Serializer):
    """Payload for human approve/reject actions."""
    action = serializers.ChoiceField(choices=["approve", "reject", "escalate"])
    note   = serializers.CharField(required=False, default="", allow_blank=True, max_length=2000)
    escalate_to_user_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("action") == "escalate" and not attrs.get("escalate_to_user_id"):
            raise serializers.ValidationError(
                {"escalate_to_user_id": "Required when action is 'escalate'."}
            )
        return attrs


# ---------------------------------------------------------------------------
# TaskBot
# ---------------------------------------------------------------------------

class TaskBotSerializer(serializers.ModelSerializer):
    is_healthy    = serializers.SerializerMethodField()
    approval_rate = serializers.SerializerMethodField()

    class Meta:
        model  = TaskBot
        fields = [
            "id", "name", "description",
            "submission_type", "status", "config",
            "total_processed", "total_approved",
            "total_rejected", "total_escalated", "total_errors",
            "last_heartbeat", "last_error", "retry_count",
            "is_healthy", "approval_rate",
            "assigned_to",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status",
            "total_processed", "total_approved",
            "total_rejected", "total_escalated", "total_errors",
            "last_heartbeat", "last_error", "retry_count",
            "is_healthy", "approval_rate",
            "created_at", "updated_at",
        ]

    def get_is_healthy(self, obj: TaskBot) -> bool:
        return obj.is_healthy

    def get_approval_rate(self, obj: TaskBot) -> float:
        return obj.approval_rate


class TaskBotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaskBot
        fields = ["name", "description", "submission_type", "config", "assigned_to"]
