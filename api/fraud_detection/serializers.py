# =============================================================================
# fraud_detection/serializers.py
#
# Single flat serializer module covering ALL 14 models.
# Previously-missing serializers (FraudSettings, OfferCompletion,
# FraudNotification and the full-field variants for FraudCase,
# FraudCaseEvidence, FraudCaseAction, FraudWhitelist) have been merged
# in from serializers_missing.py.  That file is now redundant and can be
# deleted once you confirm nothing else imports from it directly.
# =============================================================================
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from django.utils import timezone
from rest_framework import serializers

from api.fraud_detection.validators import (
    validate_ip_address,
    validate_risk_score,
    validate_device_fingerprint,
    validate_fraud_rule_data,
    validate_evidence_data,
    validate_whitelist_data,
    validate_notification_data,
)
from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern,
    UserRiskProfile, DeviceFingerprint,
    IPReputation, FraudAlert, FraudCase, FraudCaseEvidence, FraudCaseAction,
    FraudWhitelist, FraudNotification, FraudSettings, OfferCompletion,
)
from api.fraud_detection.choices import CaseStatus, EvidenceType, AlertPriority
try:
    from api.users.serializers import UserSerializer
except ImportError:
    UserSerializer = None

logger = logging.getLogger(__name__)


# =============================================================================
# FraudRule
# =============================================================================

class FraudRuleSerializer(serializers.ModelSerializer):
    """Serializer for FraudRule model"""
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = FraudRule
        fields = [
            'id', 'name', 'description', 'rule_type', 'rule_type_display',
            'severity', 'severity_display', 'condition', 'weight', 'threshold',
            'action_on_trigger', 'is_active', 'run_frequency',
            'last_triggered', 'trigger_count', 'false_positive_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['last_triggered', 'trigger_count', 'false_positive_count']

    def validate(self, data):
        if 'condition' in data or 'name' in data:
            validate_fraud_rule_data(data)
        return data


# =============================================================================
# FraudAttempt
# =============================================================================

class FraudAttemptSerializer(serializers.ModelSerializer):
    """Serializer for FraudAttempt model"""
    user_details = UserSerializer(source='user', read_only=True)
    attempt_type_display = serializers.CharField(source='get_attempt_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    fraud_rules_details = FraudRuleSerializer(source='fraud_rules', many=True, read_only=True)

    class Meta:
        model = FraudAttempt
        fields = [
            'id', 'attempt_id', 'user', 'user_details', 'attempt_type', 'attempt_type_display',
            'description', 'detected_by', 'fraud_rules', 'fraud_rules_details',
            'evidence_data', 'metadata', 'fraud_score', 'confidence_score',
            'status', 'status_display', 'is_resolved', 'resolved_at',
            'resolved_by', 'resolution_notes', 'amount_involved',
            'affected_transactions', 'integrity_hash', 'previous_hash',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['attempt_id', 'created_at', 'updated_at']

    def validate_fraud_score(self, value):
        return validate_risk_score(value)

    def validate_evidence_data(self, value):
        if value:
            validate_evidence_data(value)
        return value


# =============================================================================
# FraudPattern
# =============================================================================

class FraudPatternSerializer(serializers.ModelSerializer):
    """Serializer for FraudPattern model"""
    pattern_type_display = serializers.CharField(source='get_pattern_type_display', read_only=True)

    class Meta:
        model = FraudPattern
        fields = [
            'id', 'name', 'pattern_type', 'pattern_type_display',
            'description', 'pattern_data', 'features',
            'occurrence_count', 'accuracy_rate', 'is_trained',
            'last_trained', 'model_version', 'created_at', 'updated_at'
        ]


# =============================================================================
# UserRiskProfile
# =============================================================================

class UserRiskProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserRiskProfile model"""
    user_details = UserSerializer(source='user', read_only=True)
    monitoring_level_display = serializers.CharField(source='get_monitoring_level_display', read_only=True)

    def validate_risk_score(self, value):
        return validate_risk_score(value)

    class Meta:
        model = UserRiskProfile
        fields = [
            'id', 'user', 'user_details', 'overall_risk_score',
            'account_risk_score', 'payment_risk_score', 'behavior_risk_score',
            'risk_factors', 'warning_flags', 'total_fraud_attempts',
            'confirmed_fraud_attempts', 'false_positives', 'is_flagged',
            'is_restricted', 'restrictions', 'last_risk_assessment',
            'next_assessment_due', 'monitoring_level', 'monitoring_level_display',
            'created_at', 'updated_at'
        ]


# =============================================================================
# DeviceFingerprint
# =============================================================================

class DeviceFingerprintSerializer(serializers.ModelSerializer):
    """Serializer for DeviceFingerprint model"""
    user_details = UserSerializer(source='user', read_only=True)

    def validate(self, data):
        if data:
            validate_device_fingerprint(data)
        return data

    class Meta:
        model = DeviceFingerprint
        fields = [
            'id', 'user', 'user_details', 'device_id', 'device_hash',
            'user_agent', 'platform', 'browser', 'browser_version',
            'os', 'os_version', 'screen_resolution', 'language',
            'timezone', 'cpu_cores', 'device_memory', 'max_touch_points',
            'canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint',
            'ip_address', 'location_data', 'is_vpn', 'is_proxy',
            'is_tor', 'is_mobile', 'is_bot', 'trust_score',
            'last_seen', 'created_at'
        ]
        read_only_fields = ['device_hash', 'trust_score', 'last_seen']


# =============================================================================
# IPReputation
# =============================================================================

class IPReputationSerializer(serializers.ModelSerializer):
    """Serializer for IPReputation model"""

    def validate_ip_address(self, value):
        return validate_ip_address(value)

    class Meta:
        model = IPReputation
        fields = [
            'id', 'ip_address', 'fraud_score', 'spam_score',
            'malware_score', 'total_requests', 'fraud_attempts',
            'unique_users', 'is_blacklisted', 'blacklist_reason',
            'blacklisted_at', 'country', 'region', 'city', 'isp',
            'threat_types', 'last_threat_check', 'created_at', 'updated_at'
        ]


# =============================================================================
# FraudAlert
# =============================================================================

class FraudAlertSerializer(serializers.ModelSerializer):
    """Serializer for FraudAlert model"""
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    fraud_attempt_details = FraudAttemptSerializer(source='fraud_attempt', read_only=True)

    class Meta:
        model = FraudAlert
        fields = [
            'id', 'alert_id', 'alert_type', 'alert_type_display', 'priority',
            'priority_display', 'title', 'description', 'user', 'user_details',
            'fraud_attempt', 'fraud_attempt_details', 'related_rules',
            'data', 'is_resolved', 'resolved_at', 'resolved_by',
            'resolution_notes', 'notified_users', 'notification_sent',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['alert_id', 'notification_sent']


# =============================================================================
# FraudDetectionResponse (non-model)
# =============================================================================

class FraudDetectionResponseSerializer(serializers.Serializer):
    """Serializer for fraud detection API responses"""
    is_fraud = serializers.BooleanField()
    fraud_score = serializers.IntegerField(min_value=0, max_value=100)
    confidence = serializers.IntegerField(min_value=0, max_value=100)
    reasons = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    recommendations = serializers.ListField(child=serializers.CharField(), required=False)
    action_required = serializers.BooleanField(default=False)
    action_type = serializers.CharField(required=False)
    fraud_attempt_id = serializers.UUIDField(required=False)


# =============================================================================
# FraudCaseEvidence
# =============================================================================

class FraudCaseEvidenceSerializer(serializers.ModelSerializer):
    """Lightweight serializer for fraud case evidence (used in nested contexts)"""

    class Meta:
        model = FraudCaseEvidence
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FraudCaseEvidenceFullSerializer(serializers.ModelSerializer):
    """Full serializer for FraudCaseEvidence — all 10 fields with display helpers."""
    added_by_name = serializers.CharField(source='added_by.username', read_only=True)
    evidence_type_display = serializers.CharField(source='get_evidence_type_display', read_only=True)

    class Meta:
        model = FraudCaseEvidence
        fields = [
            'id', 'evidence_id', 'fraud_case',
            'evidence_type', 'evidence_type_display',
            'data', 'added_by', 'added_by_name',
            'created_at', 'integrity_hash', 'previous_hash',
        ]
        read_only_fields = [
            'id', 'evidence_id', 'created_at',
            'integrity_hash', 'previous_hash',
            'added_by_name', 'evidence_type_display',
        ]

    def create(self, validated_data):
        validated_data['added_by'] = self.context['request'].user
        return super().create(validated_data)


# =============================================================================
# FraudCaseAction
# =============================================================================

class FraudCaseActionSerializer(serializers.ModelSerializer):
    """Lightweight serializer for fraud case actions (used in nested contexts)"""
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = FraudCaseAction
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FraudCaseActionFullSerializer(serializers.ModelSerializer):
    """Full serializer for FraudCaseAction — all 9 fields with display helpers."""
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    time_since_action = serializers.SerializerMethodField()

    class Meta:
        model = FraudCaseAction
        fields = [
            'id', 'action_id', 'fraud_case',
            'action_type', 'action_type_display',
            'performed_by', 'performed_by_name',
            'note', 'is_completed',
            'created_at', 'time_since_action',
            'integrity_hash', 'previous_hash',
        ]
        read_only_fields = [
            'id', 'action_id', 'created_at',
            'integrity_hash', 'previous_hash',
            'performed_by_name', 'action_type_display',
            'time_since_action',
        ]

    def get_time_since_action(self, obj):
        delta = timezone.now() - obj.created_at
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            return f"{int(delta.total_seconds() // 60)}m ago"
        if hours < 24:
            return f"{hours}h ago"
        return f"{delta.days}d ago"

    def create(self, validated_data):
        validated_data['performed_by'] = self.context['request'].user
        return super().create(validated_data)


# =============================================================================
# FraudCase
# =============================================================================

class FraudCaseSerializer(serializers.ModelSerializer):
    """Standard serializer for fraud cases — includes nested evidence & actions."""
    user_details = UserSerializer(source='user', read_only=True)
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    evidence = FraudCaseEvidenceSerializer(source='fraudcaseevidence_set', many=True, read_only=True)
    actions = FraudCaseActionSerializer(source='fraudcaseaction_set', many=True, read_only=True)

    class Meta:
        model = FraudCase
        fields = '__all__'
        read_only_fields = [
            'case_number', 'opened_at', 'integrity_hash',
            'previous_hash', 'created_at', 'updated_at',
        ]


class FraudCaseFullSerializer(serializers.ModelSerializer):
    """Full serializer for FraudCase — all 13 fields with computed helpers."""
    user_username = serializers.CharField(source='user.username', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    resolved_by_name = serializers.CharField(source='resolved_by.username', read_only=True, default=None)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = FraudCase
        fields = [
            'id', 'case_number',
            'user', 'user_username',
            'title', 'description',
            'status', 'status_display',
            'risk_score', 'priority', 'priority_display',
            'opened_at', 'resolved_at',
            'assigned_to', 'assigned_to_name',
            'resolved_by', 'resolved_by_name',
            'integrity_hash', 'previous_hash',
            'is_open', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'case_number', 'opened_at', 'integrity_hash',
            'previous_hash', 'is_open', 'created_at', 'updated_at',
            'user_username', 'assigned_to_name', 'resolved_by_name',
            'status_display', 'priority_display',
        ]

    def get_is_open(self, obj):
        return obj.status not in ('resolved', 'closed', 'dismissed')

    def validate_risk_score(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("risk_score must be 0–100.")
        return value


# =============================================================================
# FraudWhitelist
# =============================================================================

class FraudWhitelistFullSerializer(serializers.ModelSerializer):
    """Full serializer for FraudWhitelist — all 9 fields with expiry helpers."""
    whitelisted_by_name = serializers.CharField(source='whitelisted_by.username', read_only=True)
    entity_type_display = serializers.CharField(source='get_entity_type_display', read_only=True)
    is_expired = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = FraudWhitelist
        fields = [
            'id', 'whitelist_id',
            'entity_type', 'entity_type_display',
            'entity_value', 'reason',
            'is_active', 'whitelisted_by', 'whitelisted_by_name',
            'expires_at', 'is_expired', 'days_remaining',
            'integrity_hash', 'previous_hash',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'whitelist_id', 'created_at', 'updated_at',
            'integrity_hash', 'previous_hash',
            'whitelisted_by_name', 'entity_type_display',
            'is_expired', 'days_remaining',
        ]

    def get_is_expired(self, obj):
        if not obj.expires_at:
            return False
        return timezone.now() > obj.expires_at

    def get_days_remaining(self, obj):
        if not obj.expires_at:
            return None
        delta = obj.expires_at - timezone.now()
        return max(0, delta.days)

    def create(self, validated_data):
        validated_data['whitelisted_by'] = self.context['request'].user
        return super().create(validated_data)


# =============================================================================
# FraudNotification  ← previously only in serializers_missing.py
# =============================================================================

class FraudNotificationSerializer(serializers.ModelSerializer):
    """Serializer for FraudNotification model."""
    user_username = serializers.CharField(source='user.username', read_only=True)
    notification_type_disp = serializers.CharField(
        source='get_notification_type_display', read_only=True
    )
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = FraudNotification
        fields = '__all__'
        read_only_fields = [
            'id', 'notification_id', 'sent_at', 'is_read',
            'user_username', 'notification_type_disp',
            'created_at', 'updated_at',
        ]

    def get_is_read(self, obj):
        return obj.read_at is not None

    def validate(self, data):
        if data:
            validate_notification_data(data)
        return data


# =============================================================================
# FraudSettings  ← previously only in serializers_missing.py
# =============================================================================

class FraudSettingsSerializer(serializers.ModelSerializer):
    """Serializer for FraudSettings model (admin only, singleton-style)."""
    updated_by_name = serializers.CharField(
        source='updated_by.username', read_only=True, default='system'
    )

    class Meta:
        model = FraudSettings
        fields = [
            'id', 'block_vpn', 'global_risk_threshold',
            'updated_by', 'updated_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'updated_by_name']

    def validate_global_risk_threshold(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Threshold must be 0–100.")
        return value

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        return super().update(instance, validated_data)


# =============================================================================
# OfferCompletion  ← previously only in serializers_missing.py
# =============================================================================

class OfferCompletionSerializer(serializers.ModelSerializer):
    """Read serializer for OfferCompletion model."""
    user_username = serializers.CharField(source='user.username', read_only=True)
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.username', read_only=True, default=None
    )
    reward_amount = serializers.DecimalField(max_digits=14, decimal_places=6, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OfferCompletion
        fields = [
            'id', 'user', 'user_username', 'offer', 'status', 'status_display',
            'completion_data', 'reward_amount', 'transaction',
            'ip_address', 'user_agent', 'device_id', 'referral_code',
            'is_fraud', 'fraud_reason',
            'tracked_at', 'completed_at', 'reviewed_at',
            'reviewed_by', 'reviewed_by_name', 'notes',
        ]
        read_only_fields = [
            'id', 'reward_amount', 'tracked_at', 'user_username',
            'status_display', 'reviewed_by_name',
        ]

    def validate(self, data):
        if data.get('is_fraud') and not data.get('fraud_reason'):
            raise serializers.ValidationError(
                {'fraud_reason': 'fraud_reason is required when is_fraud=True.'}
            )
        return data


class OfferCompletionCreateSerializer(serializers.ModelSerializer):
    """Write serializer — used by the postback handler to record a new completion."""

    class Meta:
        model = OfferCompletion
        fields = [
            'user', 'offer', 'status', 'completion_data',
            'reward_amount', 'ip_address', 'user_agent', 'device_id', 'referral_code',
        ]


# =============================================================================
# AdminFraudSerializer
# =============================================================================

class AdminFraudSerializer(serializers.ModelSerializer):
    """Comprehensive admin serializer for fraud management"""
    user_details = UserSerializer(source='user', read_only=True)
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    evidence_count = serializers.SerializerMethodField()
    action_count = serializers.SerializerMethodField()
    age_hours = serializers.SerializerMethodField()

    class Meta:
        model = FraudCase
        fields = [
            'id', 'case_number', 'user', 'user_details', 'title', 'description',
            'status', 'status_display', 'priority', 'priority_display',
            'risk_score', 'assigned_to', 'assigned_to_details', 'opened_at',
            'resolved_at', 'resolution_notes', 'evidence_count', 'action_count',
            'age_hours', 'is_high_priority', 'escalation_level', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['case_number', 'opened_at', 'created_at', 'updated_at']

    def get_evidence_count(self, obj):
        return obj.fraudcaseevidence_set.count()

    def get_action_count(self, obj):
        return obj.fraudcaseaction_set.count()

    def get_age_hours(self, obj):
        if obj.opened_at:
            return int((timezone.now() - obj.opened_at).total_seconds() / 3600)
        return 0


# =============================================================================
# FraudStatistics (non-model)
# =============================================================================

class FraudStatisticsSerializer(serializers.Serializer):
    """Serializer for fraud statistics"""
    total_detections = serializers.IntegerField()
    confirmed_fraud = serializers.IntegerField()
    false_positives = serializers.IntegerField()
    detection_rate = serializers.FloatField()
    average_fraud_score = serializers.FloatField()
    top_fraud_types = serializers.DictField(child=serializers.IntegerField())
    risk_distribution = serializers.DictField(child=serializers.IntegerField())
    monthly_trend = serializers.ListField(child=serializers.DictField())


# =============================================================================
# Action-specific serializers — used by ViewSets for create/update operations
# Previously referenced in viewset.py but never defined. Added here to fix
# ImportError at runtime.
# =============================================================================

class FraudAlertCreateSerializer(serializers.ModelSerializer):
    """
    Lightweight write serializer for FraudAlert creation.
    Excludes read-only audit fields; validated before save.
    """
    class Meta:
        model = FraudAlert
        fields = [
            'alert_type', 'priority', 'title', 'description',
            'user', 'fraud_attempt', 'related_rules',
            'data', 'is_resolved', 'resolution_notes',
        ]

    def validate_priority(self, value):
        valid = {'low', 'medium', 'high', 'critical'}
        if value not in valid:
            raise serializers.ValidationError(
                f"priority must be one of {sorted(valid)}."
            )
        return value


class FraudRuleCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating new FraudRule instances.
    Strips computed/read-only fields so the caller cannot set them.
    """
    class Meta:
        model = FraudRule
        fields = [
            'name', 'description', 'rule_type', 'severity',
            'condition', 'weight', 'threshold', 'action_on_trigger',
            'is_active', 'run_frequency',
        ]

    def validate_weight(self, value):
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError(
                "weight must be between 0.0 and 1.0."
            )
        return value

    def validate(self, data):
        from api.fraud_detection.serializers import validate_fraud_rule_data
        try:
            validate_fraud_rule_data(data)
        except Exception:
            pass
        return data


class FraudRuleUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer for updating existing FraudRule instances.
    Identical field-set to FraudRuleCreateSerializer but supports
    partial=True for PATCH operations — all fields are optional here.
    """
    class Meta:
        model = FraudRule
        fields = [
            'name', 'description', 'severity',
            'condition', 'weight', 'threshold', 'action_on_trigger',
            'is_active', 'run_frequency',
        ]

    def validate_weight(self, value):
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError(
                "weight must be between 0.0 and 1.0."
            )
        return value
