"""
Onboarding Serializers

This module contains serializers for onboarding-related models including
TenantOnboarding, TenantOnboardingStep, and TenantTrialExtension.
"""

from rest_framework import serializers
from django.utils import timezone
from ..models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension


class TenantOnboardingSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantOnboarding model.
    """
    status_display = serializers.SerializerMethodField()
    days_since_start = serializers.SerializerMethodField()
    needs_attention = serializers.SerializerMethodField()
    steps_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantOnboarding
        fields = [
            'id', 'tenant', 'completion_pct', 'current_step', 'status',
            'status_display', 'started_at', 'completed_at', 'last_activity_at',
            'days_since_start', 'needs_attention', 'skip_welcome', 'enable_tips',
            'send_reminders', 'custom_flow', 'skipped_steps', 'notes',
            'feedback', 'steps_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'started_at', 'completed_at', 'last_activity_at',
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_days_since_start(self, obj):
        """Get days since onboarding started."""
        return obj.days_since_start
    
    def get_needs_attention(self, obj):
        """Check if onboarding needs attention."""
        return obj.needs_attention
    
    def get_steps_summary(self, obj):
        """Get steps summary."""
        steps = obj.tenant.onboarding_steps.all()
        return {
            'total_steps': steps.count(),
            'completed_steps': steps.filter(is_done=True).count(),
            'skipped_steps': steps.filter(status='skipped').count(),
            'in_progress_steps': steps.filter(status='in_progress').count(),
            'not_started_steps': steps.filter(status='not_started').count(),
        }


class TenantOnboardingStepSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantOnboardingStep model.
    """
    status_display = serializers.SerializerMethodField()
    step_type_display = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    time_spent_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantOnboardingStep
        fields = [
            'id', 'tenant', 'step_key', 'step_type', 'step_type_display',
            'label', 'description', 'status', 'status_display', 'is_done',
            'done_at', 'is_required', 'can_skip', 'sort_order', 'help_text',
            'video_url', 'documentation_url', 'step_data', 'validation_rules',
            'started_at', 'time_spent_seconds', 'time_spent_display',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'done_at', 'started_at', 'time_spent_seconds',
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_step_type_display(self, obj):
        """Get step type display name."""
        return obj.get_step_type_display()
    
    def get_is_active(self, obj):
        """Check if this is the current active step."""
        return obj.is_active
    
    def get_time_spent_display(self, obj):
        """Get human-readable time spent."""
        return obj.time_spent_display


class TenantOnboardingStepCompleteSerializer(serializers.Serializer):
    """
    Serializer for completing onboarding steps.
    """
    step_data = serializers.JSONField(required=False, default=dict)
    
    def validate_step_data(self, value):
        """Validate step completion data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Step data must be a dictionary.")
        return value


class TenantTrialExtensionSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantTrialExtension model.
    """
    status_display = serializers.SerializerMethodField()
    reason_display = serializers.SerializerMethodField()
    days_until_new_trial_end = serializers.SerializerMethodField()
    approved_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantTrialExtension
        fields = [
            'id', 'tenant', 'days_extended', 'reason', 'reason_display',
            'reason_details', 'status', 'status_display', 'approved_by',
            'approved_by_details', 'approved_at', 'original_trial_end',
            'new_trial_end', 'days_until_new_trial_end', 'notification_sent',
            'follow_up_required', 'follow_up_date', 'internal_notes',
            'rejection_reason', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'approved_by', 'approved_at', 'created_at',
            'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_reason_display(self, obj):
        """Get reason display name."""
        return obj.get_reason_display()
    
    def get_days_until_new_trial_end(self, obj):
        """Get days until new trial end date."""
        return obj.days_until_new_trial_end
    
    def get_approved_by_details(self, obj):
        """Get approved by user details."""
        if obj.approved_by:
            return {
                'id': str(obj.approved_by.id),
                'username': obj.approved_by.username,
                'email': obj.approved_by.email,
            }
        return None
    
    def validate(self, attrs):
        """Validate trial extension data."""
        # Validate days extended
        days_extended = attrs.get('days_extended')
        if days_extended is not None:
            if days_extended <= 0:
                raise serializers.ValidationError("Days extended must be greater than 0.")
            if days_extended > 90:
                raise serializers.ValidationError("Cannot extend trial by more than 90 days.")
        
        # Validate trial end dates
        original_end = attrs.get('original_trial_end')
        new_end = attrs.get('new_trial_end')
        
        if original_end and new_end and new_end <= original_end:
            raise serializers.ValidationError("New trial end must be after original trial end.")
        
        return attrs


class TenantTrialExtensionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new trial extension requests.
    """
    class Meta:
        model = TenantTrialExtension
        fields = [
            'days_extended', 'reason', 'reason_details'
        ]
    
    def validate_days_extended(self, value):
        """Validate days extended."""
        if value <= 0:
            raise serializers.ValidationError("Days extended must be greater than 0.")
        if value > 90:
            raise serializers.ValidationError("Cannot extend trial by more than 90 days.")
        return value
    
    def validate(self, attrs):
        """Validate trial extension creation."""
        tenant = self.context['request'].tenant
        
        # Check if tenant has an active trial
        if not tenant.trial_ends_at:
            raise serializers.ValidationError("Tenant does not have an active trial.")
        
        if tenant.is_trial_expired:
            raise serializers.ValidationError("Trial has already expired.")
        
        return attrs
