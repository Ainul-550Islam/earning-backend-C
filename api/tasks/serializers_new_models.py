"""
tasks/serializers_new_models.py
Missing serializers for 10 models that have no API representation.
Append to or import from serializers.py
"""
from rest_framework import serializers
from .models import (
    TaskLock, UserTaskCompletion, ProofSubmission, ProofAttachment,
    TaskDispute, TaskEventLog, TaskDependency, UserTaskDependencyStatus,
    TaskInventory, FraudSignal,
)


class TaskLockSerializer(serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField()
    time_remaining_seconds = serializers.ReadOnlyField()

    class Meta:
        model = TaskLock
        fields = [
            'id', 'task', 'user', 'lock_type',
            'acquired_at', 'expires_at', 'released_at',
            'lock_holder_worker', 'version',
            'is_active', 'time_remaining_seconds',
        ]
        read_only_fields = ['id', 'acquired_at', 'version']


class UserTaskCompletionSerializer(serializers.ModelSerializer):
    """Full UserTaskCompletion serializer — all 13 model fields."""
    class Meta:
        model = UserTaskCompletion
        fields = [
            'id', 'user', 'task', 'task_lock', 'status',
            'reward_amount', 'rewards_awarded',
            'started_at', 'completed_at', 'verified_at',
            'proof_data', 'ip_address', 'device_info',
        ]
        read_only_fields = ['id', 'started_at', 'completed_at', 'verified_at',
                            'reward_amount', 'rewards_awarded', 'task_lock']


class ProofAttachmentSerializer(serializers.ModelSerializer):
    """Full ProofAttachment serializer including virus scan and hash fields."""
    class Meta:
        model = ProofAttachment
        fields = [
            'id', 'proof_submission', 'file_type', 'file_url',
            'file_size_bytes', 'file_hash', 'mime_type',
            'virus_scan_status', 'virus_scan_result',
            'uploaded_at',
        ]
        read_only_fields = ['id', 'uploaded_at', 'file_hash',
                            'virus_scan_status', 'virus_scan_result']


class ProofSubmissionSerializer(serializers.ModelSerializer):
    attachments = ProofAttachmentSerializer(many=True, read_only=True)
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = ProofSubmission
        fields = [
            'id', 'user_task_completion', 'task', 'user',
            'submission_type', 'data_schema', 'proof_data',
            'hash_signature', 'verification_status',
            'submitted_at', 'verified_at', 'rejected_reason',
            'manual_review_required', 'reviewed_by',
            'review_notes', 'reviewed_at',
            'attachments', 'is_verified',
        ]
        read_only_fields = ['id', 'hash_signature', 'submitted_at', 'verified_at', 'reviewed_at']

    def get_is_verified(self, obj) -> bool:
        return obj.verification_status == ProofSubmission.VerificationStatus.VERIFIED


class TaskDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDispute
        fields = [
            'id', 'user_task_completion', 'dispute_type', 'status',
            'severity', 'reported_by', 'reported_at',
            'reason_text', 'assigned_to',
        ]
        read_only_fields = ['id', 'reported_at', 'status']


class TaskEventLogSerializer(serializers.ModelSerializer):
    """Full audit log serializer — all 11 model fields including security fields."""
    class Meta:
        model = TaskEventLog
        fields = [
            'id', 'event_type', 'task', 'user',
            'actor_type', 'actor_id',
            'event_data',
            'ip_address', 'user_agent', 'signature',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'signature']


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = [
            'id', 'dependent_task', 'prerequisite_task',
            'dependency_type', 'config', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserTaskDependencyStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTaskDependencyStatus
        fields = [
            'id', 'user', 'dependency', 'is_satisfied',
            'checked_at', 'expires_at',
            'prerequisite_completed_at', 'computed_at',
        ]
        read_only_fields = ['id', 'checked_at']


class TaskInventorySerializer(serializers.ModelSerializer):
    """Full TaskInventory serializer covering all 18 model fields."""
    budget_utilization_pct = serializers.SerializerMethodField()
    is_exhausted = serializers.SerializerMethodField()

    class Meta:
        model = TaskInventory
        fields = [
            'id', 'task',
            # Budget fields
            'daily_budget', 'weekly_budget', 'monthly_budget', 'total_budget',
            'current_daily_spend', 'current_weekly_spend',
            'current_monthly_spend', 'current_total_spend',
            # Reset timestamps
            'last_reset_daily', 'last_reset_weekly', 'last_reset_monthly',
            # Status
            'inventory_status',
            'alert_80_percent_sent', 'alert_100_percent_sent',
            # Computed
            'budget_utilization_pct', 'is_exhausted',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'current_daily_spend', 'current_weekly_spend',
            'current_monthly_spend', 'current_total_spend',
            'last_reset_daily', 'last_reset_weekly', 'last_reset_monthly',
            'alert_80_percent_sent', 'alert_100_percent_sent',
            'created_at', 'updated_at',
        ]

    def get_budget_utilization_pct(self, obj) -> float:
        """Daily utilization as a percentage of daily_budget."""
        try:
            if not obj.daily_budget:
                return 0.0
            return round(float(obj.current_daily_spend) / float(obj.daily_budget) * 100, 1)
        except Exception:
            return 0.0

    def get_is_exhausted(self, obj) -> bool:
        return obj.inventory_status == 'exhausted' 


class FraudSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudSignal
        fields = [
            'id', 'user', 'signal_type', 'score_contribution',
            'reason', 'is_appealed', 'appeal_notes',
            'appeal_resolved', 'resolution_notes', 'triggered_at',
        ]
        read_only_fields = ['id', 'triggered_at', 'score_contribution']
