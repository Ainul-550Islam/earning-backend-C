"""
Incident Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)

User = get_user_model()


class IncidentSerializer(serializers.ModelSerializer):
    """Incident serializer"""
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    business_hours_duration = serializers.SerializerMethodField()
    severity_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Incident
        fields = [
            'id', 'title', 'description', 'severity', 'impact', 'urgency', 'status',
            'detected_at', 'acknowledged_at', 'identified_at', 'resolved_at', 'closed_at',
            'response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes',
            'root_cause', 'contributing_factors', 'affected_services', 'affected_users_count',
            'affected_regions', 'business_impact', 'financial_impact', 'customer_impact',
            'communication_plan', 'stakeholder_notifications', 'resolution_summary',
            'resolution_actions', 'preventive_measures', 'related_alerts', 'assigned_to',
            'assigned_to_name', 'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'created_at', 'updated_at', 'duration_minutes', 'business_hours_duration',
            'severity_score'
        ]
        read_only_fields = ['detected_at', 'acknowledged_at', 'identified_at', 'resolved_at', 'closed_at',
                          'response_time_minutes', 'resolution_time_minutes', 'total_downtime_minutes',
                          'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_duration_minutes(self, obj):
        return obj.get_duration_minutes()
    
    def get_business_hours_duration(self, obj):
        return obj.get_business_hours_duration()
    
    def get_severity_score(self, obj):
        return obj.get_severity_score()


class IncidentTimelineSerializer(serializers.ModelSerializer):
    """IncidentTimeline serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = IncidentTimeline
        fields = [
            'id', 'incident', 'event_type', 'title', 'description', 'timestamp',
            'duration_minutes', 'created_by', 'created_by_name', 'participants',
            'event_data', 'attachments', 'users_affected', 'services_affected',
            'metrics_affected'
        ]
        read_only_fields = ['timestamp', 'created_by']


class IncidentResponderSerializer(serializers.ModelSerializer):
    """IncidentResponder serializer"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    is_available_now = serializers.SerializerMethodField()
    
    class Meta:
        model = IncidentResponder
        fields = [
            'id', 'incident', 'user', 'user_name', 'role', 'status', 'assigned_at',
            'active_at', 'completed_at', 'contact_method', 'contact_details',
            'available_from', 'available_to', 'timezone', 'responsibilities',
            'skills', 'notes', 'is_available_now'
        ]
        read_only_fields = ['assigned_at', 'active_at', 'completed_at']
    
    def get_is_available_now(self, obj):
        return obj.is_available_now()


class IncidentPostMortemSerializer(serializers.ModelSerializer):
    """IncidentPostMortem serializer"""
    incident_title = serializers.CharField(source='incident.title', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    completion_score = serializers.SerializerMethodField()
    
    class Meta:
        model = IncidentPostMortem
        fields = [
            'id', 'incident', 'incident_title', 'title', 'summary', 'timeline_summary',
            'key_events', 'root_cause_analysis', 'contributing_factors',
            'what_went_well', 'what_could_be_improved', 'business_impact',
            'technical_impact', 'customer_impact', 'financial_impact',
            'lessons_learned', 'action_items', 'preventive_measures',
            'process_changes', 'tool_improvements', 'training_needs',
            'status', 'reviewed_by', 'reviewed_by_name', 'approved_by',
            'approved_by_name', 'published_at', 'internal_only',
            'external_summary', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'completed_at', 'completion_score'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'completed_at']
    
    def get_completion_score(self, obj):
        return obj.get_completion_score()


class OnCallScheduleSerializer(serializers.ModelSerializer):
    """OnCallSchedule serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    current_on_call = serializers.SerializerMethodField()
    
    class Meta:
        model = OnCallSchedule
        fields = [
            'id', 'name', 'description', 'schedule_type', 'is_active',
            'rotation_period_days', 'rotation_start_date', 'timezone',
            'start_time', 'end_time', 'days_of_week', 'primary_users',
            'backup_users', 'escalation_minutes', 'escalation_users',
            'notification_channels', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'current_on_call'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_current_on_call(self, obj):
        current_on_call = obj.get_current_on_call()
        if current_on_call:
            return {
                'id': current_on_call.id,
                'username': current_on_call.username,
                'full_name': current_on_call.get_full_name(),
                'email': current_on_call.email
            }
        return None


# Simplified serializers for list views
class IncidentListSerializer(serializers.ModelSerializer):
    """Simplified Incident serializer for list views"""
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = Incident
        fields = [
            'id', 'title', 'severity', 'impact', 'status', 'detected_at',
            'assigned_to', 'assigned_to_name', 'duration_minutes'
        ]
    
    def get_duration_minutes(self, obj):
        return obj.get_duration_minutes()


class IncidentTimelineListSerializer(serializers.ModelSerializer):
    """Simplified IncidentTimeline serializer for list views"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = IncidentTimeline
        fields = [
            'id', 'event_type', 'title', 'timestamp', 'created_by_name'
        ]


class IncidentResponderListSerializer(serializers.ModelSerializer):
    """Simplified IncidentResponder serializer for list views"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = IncidentResponder
        fields = [
            'id', 'user', 'user_name', 'role', 'status', 'assigned_at'
        ]


class IncidentPostMortemListSerializer(serializers.ModelSerializer):
    """Simplified IncidentPostMortem serializer for list views"""
    incident_title = serializers.CharField(source='incident.title', read_only=True)
    
    class Meta:
        model = IncidentPostMortem
        fields = [
            'id', 'incident', 'incident_title', 'title', 'status', 'created_at'
        ]


class OnCallScheduleListSerializer(serializers.ModelSerializer):
    """Simplified OnCallSchedule serializer for list views"""
    
    class Meta:
        model = OnCallSchedule
        fields = [
            'id', 'name', 'schedule_type', 'is_active', 'timezone',
            'created_at', 'updated_at'
        ]


# Action serializers
class IncidentAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging incidents (no additional fields needed)"""
    pass


class IncidentIdentifySerializer(serializers.Serializer):
    """Serializer for identifying incidents"""
    root_cause = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class IncidentResolveSerializer(serializers.Serializer):
    """Serializer for resolving incidents"""
    resolution_summary = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class IncidentCloseSerializer(serializers.Serializer):
    """Serializer for closing incidents (no additional fields needed)"""
    pass


class IncidentTimelineAddEventSerializer(serializers.ModelSerializer):
    """Serializer for adding timeline events"""
    
    class Meta:
        model = IncidentTimeline
        fields = [
            'event_type', 'title', 'description', 'participants',
            'event_data', 'attachments', 'users_affected', 'services_affected',
            'metrics_affected'
        ]


class IncidentResponderActivateSerializer(serializers.Serializer):
    """Serializer for activating responders (no additional fields needed)"""
    pass


class IncidentResponderCompleteSerializer(serializers.Serializer):
    """Serializer for completing responders (no additional fields needed)"""
    pass


class IncidentPostMortemSubmitReviewSerializer(serializers.Serializer):
    """Serializer for submitting post-mortem for review (no additional fields needed)"""
    pass


class IncidentPostMortemApproveSerializer(serializers.Serializer):
    """Serializer for approving post-mortem (no additional fields needed)"""
    pass


class IncidentPostMortemPublishSerializer(serializers.Serializer):
    """Serializer for publishing post-mortem"""
    internal_only = serializers.BooleanField(default=True)


class OnCallScheduleCurrentOnCallSerializer(serializers.Serializer):
    """Serializer for getting current on-call (no additional fields needed)"""
    pass


class OnCallScheduleEscalationChainSerializer(serializers.Serializer):
    """Serializer for getting escalation chain (no additional fields needed)"""
    pass


class OnCallScheduleUpcomingSerializer(serializers.Serializer):
    """Serializer for getting upcoming schedule"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class OnCallScheduleIsOnCallSerializer(serializers.Serializer):
    """Serializer for checking if user is on call"""
    user_id = serializers.IntegerField(required=True)
    
    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value


class IncidentCreateFromAlertSerializer(serializers.Serializer):
    """Serializer for creating incident from alert"""
    title = serializers.CharField(max_length=200, required=False)
    severity = serializers.CharField(max_length=20, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_severity(self, value):
        valid_severities = ['low', 'medium', 'high', 'critical']
        if value and value not in valid_severities:
            raise serializers.ValidationError(f"Severity must be one of: {valid_severities}")
        return value
